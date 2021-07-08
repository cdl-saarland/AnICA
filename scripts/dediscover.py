#!/usr/bin/env python3

"""DeviDisc: the deviation discovery tool for basic block throughput predictors.
"""

import argparse
import json
import multiprocessing
from pathlib import Path
import random
import os
import sys
import textwrap

from datetime import datetime

import iwho
from iwho.predictors import Predictor
from iwho.utils import parse_args_with_logging


import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractionconfig import AbstractionConfig
from devidisc.abstractblock import AbstractBlock
import devidisc.discovery as discovery
from devidisc.measurementdb import MeasurementDB
from devidisc.predmanager import PredictorManager
from devidisc.random_exploration import explore


import logging
logger = logging.getLogger(__name__)


def main():
    HERE = Path(__file__).parent

    default_config = HERE.parent / "config.json"
    default_jobs = multiprocessing.cpu_count()
    default_seed = 424242
    default_db = "measurements.db"

    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    argparser.add_argument('-c', '--config', default=default_config, metavar="CONFIG",
            help='configuration file in json format')

    argparser.add_argument('-j', '--jobs', type=int, default=default_jobs, metavar="N",
            help='number of worker processes to use at most for running predictors')

    argparser.add_argument('-s', '--seed', type=int, default=default_seed, metavar="N",
            help='seed for the rng')

    argparser.add_argument('-d', '--database', metavar='database', default=default_db,
            help='path to an sqlite3 measurement database that has been initialized via dedisdb.py -c, for storing measurements to')


    argparser.add_argument('--explore', action='store_true', help='just randomly explore basic blocks')

    argparser.add_argument('-g', '--generalize', metavar='asm file', default=None, help='path to a file containing the assembly of a basic block to generalize')

    argparser.add_argument('predictors', nargs=2, metavar="PREDICTOR_ID", help='two identifiers of predictors specified in the config')

    args = parse_args_with_logging(argparser, "info")

    random.seed(args.seed)

    with open(args.config, 'r') as config_file:
        config = json.load(config_file)

    # The predman keeps track of all the predictors and interacts with them
    num_processes = args.jobs

    create_db = not os.path.isfile(args.database)

    measurement_db = MeasurementDB(args.database)

    if create_db:
        with measurement_db as m:
            m.create_tables()

    predman = PredictorManager(num_processes=num_processes, measurement_db=measurement_db)

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

    ctx.push_filter(iwho.Filters.no_control_flow)

    skl_filter = lambda scheme, ctx: (ctx.get_features(scheme) is not None and "SKL" in ctx.get_features(scheme)[0]) or "fxrstor" in str(scheme)
    ctx.push_filter(skl_filter) # only use instructions that have SKL measurements TODO that's a bit specific


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
        schemes = ctx.filtered_insn_schemes

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
