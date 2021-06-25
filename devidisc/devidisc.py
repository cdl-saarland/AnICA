#!/usr/bin/env python3

"""DeviDisc: the deviation discovery tool for basic block throughput predictors.
"""

import argparse
from collections import defaultdict
from datetime import datetime
from functools import partial
import json
import multiprocessing
from multiprocessing import Pool
import os
import pathlib
import random
import socket
from timeit import default_timer as timer


import iwho
from iwho.predictors import Predictor
from iwho.utils import parse_args_with_logging
import iwho.x86 as x86


import logging
logger = logging.getLogger(__name__)


def evaluate_bb(bb, pred):
    try:
        result = pred.evaluate(bb, disable_logging=True)
    except Exception as e:
        result = "an exception occured: " + str(e)
    return result


class LightBBWrapper:
    """ Light-weight wrapper of all things necessary to get the hex
    representation of a BasicBlock.

    The key is the execution time distribution:
    Creating this wrapper is fast, serializing it is efficient (since nothing
    unnecessary from the iwho context is present), and `get_hex()` does the
    heavy lifting (i.e. calls to the coder, which might require expensive
    subprocesses).

    This makes this very effective to use as a task for a PredictorManager,
    since all expensive things can be done by the process pool.

    This could be considered a hack.
    """
    def __init__(self, bb):
        self.asm_str = bb.get_asm()
        self.coder = bb.context.coder
        self.hex = None

    def get_hex(self):
        if self.hex is None:
            self.hex = self.coder.asm2hex(self.asm_str)
        return self.hex

    def get_asm(self):
        return self.asm_str


class PredictorManager:
    def __init__(self, num_threads=None):
        if num_threads is None:
            num_threads = multiprocessing.cpu_count()
        self.pool = Pool(num_threads)

    def do(self, pred, bbs, lazy=True):
        """ Use the given predictor to predict inverse throughputs for all
        basic blocks in the given list.

        If lazy is true, return an asynchronous iterator for the results and
        return before they are all predicted.
        If lazy is false, return a complete list of predictions (awaiting all
        results).
        """
        tasks = map(lambda x: LightBBWrapper(x), bbs)
        results = self.pool.imap(partial(evaluate_bb, pred=pred), tasks)
        if not lazy:
            results = list(results)
        return results


def main():
    HERE = pathlib.Path(__file__).parent

    default_config = HERE.parent / "config.json"
    default_jobs = multiprocessing.cpu_count()
    default_seed = 424242

    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    argparser.add_argument('-c', '--config', default=default_config, metavar="CONFIG",
            help='configuration file in json format')

    argparser.add_argument('-j', '--jobs', type=int, default=default_jobs, metavar="N",
            help='number of worker processes to use at most for running predictors')

    argparser.add_argument('-s', '--seed', type=int, default=default_seed, metavar="N",
            help='seed for the rng')

    argparser.add_argument('predictors', nargs=2, metavar="PREDICTOR_ID", help='two identifiers of predictors specified in the config')

    args = parse_args_with_logging(argparser, "info")

    with open(args.config, 'r') as config_file:
        config = json.load(config_file)

    # get a list of throughput predictors
    predictor_info = dict()

    predictors = []
    for pkey in args.predictors:
        pred_entry = config[pkey]
        pred_config = pred_entry['config']
        res = dict(**pred_entry)
        res['key'] = pkey
        res['pred'] = Predictor.get(pred_config)
        predictors.append(res)
        predictor_info[pkey] = {
                'predictor': (pred_entry['tool'], pred_entry['version']),
                'uarch': pred_entry['uarch'],
            }

    random.seed(args.seed)
    num_processes = args.jobs

    # TODO configurable?
    num_batches = 10
    # num_experiments = 100
    max_num_insns = 10

    batch_size = 100

    # get an iwho context with appropriate schemes
    ctx = iwho.get_context("x86")
    schemes = ctx.insn_schemes
    schemes = list(filter(lambda x: not x.affects_control_flow and
        ctx.get_features(x) is not None and "SKL" in ctx.get_features(x)[0], schemes))

    instor = x86.RandomRegisterInstantiator(ctx)

    predman = PredictorManager(num_processes)

    base_dir = pathlib.Path("./results/")
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    curr_result_dir = base_dir / "results_{}".format(timestamp)
    os.makedirs(curr_result_dir, exist_ok=True)

    source_computer = socket.gethostname()
    print(f"Running on source machine {source_computer}")

    for batch_idx in range(num_batches):
        print(f"batch no. {batch_idx}")

        series_date = datetime.now().isoformat()

        # sample basic blocks and run them through the predictors
        start = timer()
        bbs = []
        for x in range(batch_size):
            num_insns = random.randrange(2, max_num_insns + 1)
            bb = ctx.make_bb()
            for n in range(num_insns):
                ischeme = random.choice(schemes)
                bb.append(instor(ischeme))
            bbs.append(bb)

        end = timer()
        diff = end - start
        print(f"generated {len(bbs)} blocks in {diff:.2f} seconds")

        results = dict()
        for p in predictors:
            pred_name = p['key']
            start = timer()
            results[pred_name] = predman.do(p['pred'], bbs)
            end = timer()
            diff = end - start
            print(f"started all {pred_name} jobs in {diff:.2f} seconds")

        total_tool_time = defaultdict(lambda: 0.0)

        measurements = []
        start = timer()

        keys = results.keys()
        for x, (rs, bb) in enumerate(zip(zip( *(results[k] for k in keys )), bbs)):
            predictions = dict()
            for y, k in enumerate(keys):
                res = rs[y]
                predictions[k] = res
                total_tool_time[k] += res['rt']

                tp = res.get('TP', -1.0)
                if tp < 0:
                    tp = None

                remark = json.dumps(res)

                record = {
                        **predictor_info[k],
                        "input": bb.get_hex(),
                        "result": tp,
                        "remark": remark
                    }
                measurements.append(record)


        end = timer()
        diff = end - start

        measdict = {
                "series_date": series_date,
                "source_computer": source_computer,
                "measurements": measurements,
                }

        result_file_name = curr_result_dir / f"results_batch_{batch_idx}.json"
        with open(result_file_name, "w") as f:
            json.dump(measdict, f, indent=2)

        print(f"evaluation done in {diff:.2f} seconds")
        for k, v in total_tool_time.items():
            print(f"total time spent in {k}: {v:.2f} seconds")


if __name__ == "__main__":
    main()
