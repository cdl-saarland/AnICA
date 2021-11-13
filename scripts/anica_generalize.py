#!/usr/bin/env python3

"""AnICA: Analyzing Inconsistencies of Code Analyzers
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

from anica.abstractioncontext import AbstractionContext
from anica.abstractblock import AbstractBlock
from anica.configurable import load_json_config
import anica.discovery as discovery
from anica.random_exploration import explore


import logging
logger = logging.getLogger(__name__)


def main():
    HERE = Path(__file__).parent

    default_seed = 424242

    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-c', '--config', metavar="CONFIG", default=None,
            help='abstraction context configuration file in json format')

    argparser.add_argument('-s', '--seed', type=int, default=default_seed, metavar="N",
            help='seed for the rng')

    argparser.add_argument('--no-minimize', action='store_true', help='do not minimize the basic block before generalization')

    argparser.add_argument('--trace-output', metavar='trace file', default=None, help='path to a file where the generalization trace should be saved to')

    argparser.add_argument('--json-output', metavar='gen file', default=None, help='path to a file where the generalized abstract basic block should be dumped to')

    argparser.add_argument('generalize', metavar='asm file', help='path to a file containing the assembly of a basic block to generalize')

    argparser.add_argument('predictors', nargs="+", metavar="PREDICTOR_ID", help='one or more identifiers of predictors specified in the config')

    args = parse_args_with_logging(argparser, "info")

    random.seed(args.seed)

    actx_config = load_json_config(args.config)

    actx = AbstractionContext(config=actx_config)
    actx.predmanager.set_predictors(args.predictors)

    iwho_ctx = actx.iwho_ctx

    with open(args.generalize, 'r') as f:
        asm_str = f.read()
    bb = iwho.BasicBlock(iwho_ctx, iwho_ctx.parse_asm(asm_str))

    if not args.no_minimize:
        min_bb = discovery.minimize(actx, bb)
        print("Pruned {} instructions in the minimization step:".format(len(bb) - len(min_bb)))
        print(textwrap.indent(min_bb.get_asm(), '  '))
        bb = min_bb

    abb = AbstractBlock(actx, bb)
    strategy = actx.discovery_cfg.generalization_strategy[0][0]
    res_abb, trace, result_ref = discovery.generalize(actx, abb, strategy=strategy)
    print("Generalization Result:\n" + textwrap.indent(str(res_abb), '  '))

    if args.json_output is not None:
        filename = args.json_output
        res_abb.dump_json(filename)
        print(f"generalization result written to: {filename}")

    if args.trace_output is not None:
        filename = args.trace_output
        trace.dump_json(filename)
        print(f"witness trace written to: {filename}")

    sys.exit(0)


if __name__ == "__main__":
    main()
