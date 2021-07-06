#!/usr/bin/env python3

"""DeviDisc: the deviation discovery tool for basic block throughput predictors.
"""

import argparse
import json
import multiprocessing
from pathlib import Path
import random
import sys
import textwrap

from datetime import datetime

import iwho
from iwho.predictors import Predictor
from iwho.utils import parse_args_with_logging

from abstractionconfig import AbstractionConfig
from abstractblock import AbstractBlock
import discovery
from predmanager import PredictorManager
from random_exploration import explore


import logging
logger = logging.getLogger(__name__)


def main():
    HERE = Path(__file__).parent

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

    argparser.add_argument('--explore', action='store_true', help='just randomly explore basic blocks')

    argparser.add_argument('-g', '--generalize', metavar='asm file', default=None, help='path to a file containing the assembly of a basic block to generalize')

    argparser.add_argument('predictors', nargs=2, metavar="PREDICTOR_ID", help='two identifiers of predictors specified in the config')

    args = parse_args_with_logging(argparser, "info")

    random.seed(args.seed)

    with open(args.config, 'r') as config_file:
        config = json.load(config_file)

    # The predman keeps track of all the predictors and interacts with them
    num_processes = args.jobs
    predman = PredictorManager(num_processes)

    for pkey in args.predictors:
        pred_entry = config[pkey]
        pred_config = pred_entry['config']

        predman.register_predictor(key=pkey,
                predictor = Predictor.get(pred_config),
                toolname = pred_entry['tool'],
                version = pred_entry['version'],
                uarch = pred_entry['uarch']
            )

    ctx = iwho.get_context("x86")

    if args.generalize is not None:
        with open(args.generalize, 'r') as f:
            asm_str = f.read()
        bb = iwho.BasicBlock(ctx, ctx.parse_asm(asm_str))
        max_block_len = len(bb)
        # TODO things need to be configurable here, and this code should probably be somewhere else
        acfg = AbstractionConfig(ctx, max_block_len, predmanager=predman)
        abb = AbstractBlock(acfg, bb)
        res_abb, trace = discovery.generalize(acfg, abb)
        print("Generalization Result:\n" + textwrap.indent(str(res_abb), '  '))

        timestamp = datetime.now().replace(microsecond=0).isoformat()
        filename = f"traces/trace_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(acfg.introduce_json_references(trace.to_json_dict()), f, indent=2)
        print(f"witness trace written to: {filename}")

        sys.exit(0)

    if args.explore:
        # only use appropriate schemes
        schemes = ctx.insn_schemes
        schemes = list(filter(lambda x: not x.affects_control_flow and
            ctx.get_features(x) is not None and "SKL" in ctx.get_features(x)[0], schemes))

        result_base_path = Path("./results/")

        # TODO configurable?
        num_batches = 10
        max_num_insns = 10
        batch_size = 10

        explore(ctx, schemes, predman, result_base_path,
                max_num_insns=max_num_insns,
                num_batches=num_batches,
                batch_size=batch_size)
        sys.exit(0)


if __name__ == "__main__":
    main()
