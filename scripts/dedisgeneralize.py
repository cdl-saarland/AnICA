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

from devidisc.abstractioncontext import AbstractionContext
from devidisc.abstractblock import AbstractBlock
from devidisc.configurable import load_json_config
import devidisc.discovery as discovery
from devidisc.random_exploration import explore


import logging
logger = logging.getLogger(__name__)


def main():
    HERE = Path(__file__).parent

    default_pred_registry = HERE.parent / "configs" / "predictors" / "pred_registry.json"
    default_jobs = multiprocessing.cpu_count()
    default_seed = 424242

    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-c', '--config', metavar="CONFIG", default=None,
            help='abstraction configuration file in json format')

    argparser.add_argument('-j', '--jobs', type=int, default=default_jobs, metavar="N",
            help='number of worker processes to use at most for running predictors')

    argparser.add_argument('-s', '--seed', type=int, default=default_seed, metavar="N",
            help='seed for the rng')

    argparser.add_argument('--explore', action='store_true', help='just randomly explore basic blocks')

    argparser.add_argument('-g', '--generalize', metavar='asm file', default=None, help='path to a file containing the assembly of a basic block to generalize')

    argparser.add_argument('predictors', nargs="+", metavar="PREDICTOR_ID", help='one or more identifiers of predictors specified in the config')

    args = parse_args_with_logging(argparser, "info")

    random.seed(args.seed)

    actx_config = load_json_config(args.config)

    actx = AbstractionContext(config=actx_config)
    actx.predmanager.set_predictors(args.predictors)

    iwho_ctx = actx.iwho_ctx

    if args.generalize is not None:
        with open(args.generalize, 'r') as f:
            asm_str = f.read()
        bb = iwho.BasicBlock(iwho_ctx, iwho_ctx.parse_asm(asm_str))

        abb = AbstractBlock(actx, bb)
        res_abb, trace = discovery.generalize(actx, abb)
        print("Generalization Result:\n" + textwrap.indent(str(res_abb), '  '))

        timestamp = datetime.now().replace(microsecond=0).isoformat()
        filename = f"traces/trace_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(actx.json_ref_manager.introduce_json_references(trace.to_json_dict()), f, indent=2)
        print(f"witness trace written to: {filename}")

        sys.exit(0)

    if args.explore:
        # only use appropriate schemes
        schemes = iwho_ctx.filtered_insn_schemes

        result_base_path = Path("./results/")

        # TODO configurable?
        num_batches = 10
        max_num_insns = 10
        batch_size = 10

        explore(iwho_ctx, schemes, predman, result_base_path,
                max_num_insns=max_num_insns,
                num_batches=num_batches,
                batch_size=batch_size)
        sys.exit(0)


if __name__ == "__main__":
    main()
