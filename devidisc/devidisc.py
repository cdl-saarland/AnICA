#!/usr/bin/env python3

"""DeviDisc: the deviation discovery tool for basic block throughput predictors.
"""

import argparse
import json
import multiprocessing
import pathlib
import random
import sys

import iwho
from iwho.predictors import Predictor
from iwho.utils import parse_args_with_logging

from predmanager import PredictorManager
from random_exploration import explore

import logging
logger = logging.getLogger(__name__)


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

    argparser.add_argument('--explore', action='store_true', help='just randomly explore basic blocks')

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

    if args.explore:
        # get an iwho context with appropriate schemes
        ctx = iwho.get_context("x86")
        schemes = ctx.insn_schemes
        schemes = list(filter(lambda x: not x.affects_control_flow and
            ctx.get_features(x) is not None and "SKL" in ctx.get_features(x)[0], schemes))

        result_base_path = pathlib.Path("./results/")

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
