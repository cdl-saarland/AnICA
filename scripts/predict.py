#!/usr/bin/env python3

""" Run one or more predictors on a basic block
"""

import argparse
from collections import defaultdict
import os
import sys
import textwrap

import iwho
from iwho.utils import parse_args_with_logging


import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from anica.abstractioncontext import AbstractionContext
from anica.configurable import load_json_config, pretty_print

import logging
logger = logging.getLogger(__name__)

def main():
    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-c', '--config', metavar="CONFIG", default=None,
            help='abstraction context configuration file in json format')

    argparser.add_argument('-i', '--infile', nargs="+", required=True, metavar='ASM file', help='path(s) to a file containing the assembly of a basic block to evaluate')

    argparser.add_argument('-p', '--predictors', nargs="+", required=True, metavar="PREDICTOR_ID", help='one or more identifiers of predictors specified in the config')

    argparser.add_argument('-s', '--same', action='store_true', help='arrange the output to ease checking whether each predictor predicts only one value for all basic blocks')

    args = parse_args_with_logging(argparser, "info")


    if args.config is None:
        actx_config = {
                "iwho": { "filters": [], }, # no filters
                "measurement_db": None,     # no database
                "predmanager": {
                    "num_processes": 1,     # sequential execution
                },
            }
    else:
        actx_config = load_json_config(args.config)

    actx = AbstractionContext(config=actx_config)
    actx.predmanager.set_predictors(args.predictors)

    iwho_ctx = actx.iwho_ctx

    bbs = []
    for path in args.infile:
        with open(path, 'r') as f:
            asm_str = f.read()
        bbs.append(iwho.BasicBlock(iwho_ctx, iwho_ctx.parse_asm(asm_str)))

    results = list(actx.predmanager.eval_with_all(bbs))

    for bb, res in results:
        print("Basic Block:")
        print(textwrap.indent(str(bb), "    "))
        print("  Result:")
        print(textwrap.indent(pretty_print(res), "    "))

    if args.same:
        per_pred = defaultdict(list)

        for bb, res in results:
            for k, v in res.items():
                per_pred[k].append(v.get('TP', None))

        for k, vs in per_pred.items():
            v = vs[0]
            if all(map(lambda x: x == v, vs)):
                print(f"  {k}: same - {v}")
            else:
                print(f"  {k}: different - {', '.join(map(str, vs))}")


if __name__ == "__main__":
    main()
