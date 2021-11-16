#!/usr/bin/env python3

""" Check how many of the BHive basic blocks are covered by our instruction
schemes.
"""

import argparse
from collections import defaultdict
import csv
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

    argparser.add_argument('bhivecsv', metavar="CSV", help='path to a csv file with hex basic blocks in its first column')

    args = parse_args_with_logging(argparser, "info")

    actx_config = load_json_config(args.config)

    actx = AbstractionContext(config=actx_config)

    iwho_ctx = actx.iwho_ctx

    scheme2num_bbs = defaultdict(lambda: 0)

    bbs = []
    with open(args.bhivecsv, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            bbs.append(row[0])

    total = len(bbs)
    print(f'total: {total}')

    coder_errors = 0
    instantiation_errors = 0
    passes = 0

    step = max(total // 1000, 10)

    for idx, hex_str in enumerate(bbs):
        if (idx % step) == 0:
            progress = 100 * idx / total
            print(f" > progress: {progress:.1f}%")

        if len(hex_str) == 0:
            continue
        total += 1
        try:
            insns = iwho_ctx.decode_insns(hex_str, skip_instantiation_errors=True)
        except iwho.ASMCoderError:
            coder_errors += 1
            continue

        no_inst_error_yet = True
        for i in insns:
            if i is None:
                if no_inst_error_yet:
                    instantiation_errors += 1
                    no_inst_error_yet = False
                continue
            scheme2num_bbs[i.scheme] += 1

        if no_inst_error_yet:
            passes += 1

    print(f" > progress: 100%")

    print(f"coder errors: {coder_errors}")
    print(f"instantiation errors: {instantiation_errors}")
    print(f"passes: {passes}")

    num_schemes = len(iwho_ctx.filtered_insn_schemes)
    num_schemes_not_covered = 0

    for scheme in iwho_ctx.filtered_insn_schemes:
        if scheme2num_bbs[scheme] == 0:
            num_schemes_not_covered += 1

    print(f"total schemes: {num_schemes}")
    percentage = 100 * num_schemes_not_covered / num_schemes
    print(f"not covered by any passing bb: {num_schemes_not_covered} ({percentage:.1f}%)")



if __name__ == "__main__":
    main()

