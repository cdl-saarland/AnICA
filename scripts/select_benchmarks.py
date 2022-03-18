#!/usr/bin/env python3

""" Select a number of basic blocks that that satisfy filters randomly from a
set of existing benchmarks.
"""

import argparse
import csv
import random

import os
import sys

from progress.bar import Bar as ProgressBar

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

import iwho
from iwho.configurable import load_json_config
from iwho.utils import parse_args_with_logging

import logging
logger = logging.getLogger(__name__)

def main():
    default_seed = 424242

    argparser = argparse.ArgumentParser(description=__doc__)

    argparser.add_argument('-s', '--seed', type=int, default=default_seed, metavar="N",
            help='seed for the rng')

    argparser.add_argument('-o', '--output', metavar="OUTFILE", default="selected_bbs.csv",
        help='the output csv file')

    argparser.add_argument('-c', '--config', metavar="CONFIG", default=None,
        help='path to an iwho config (or a config including an iwho config at top-level) to use')

    argparser.add_argument('-n', '--num', metavar="N", type=int, default=10,
        help='the number of basic blocks to take from the input file')

    argparser.add_argument('input', metavar="INFILE",
        help='the input csv file, containing hex basic blocks to choose from in their first column')

    args = parse_args_with_logging(argparser, "info")

    random.seed(args.seed)

    json_cfg = load_json_config(args.config)
    cfg = iwho.Config(json_cfg)
    ctx = cfg.context

    all_bbs = []

    with open(args.input, 'r') as f:
        r = csv.reader(f)
        for row in r:
            bb = row[0]
            if len(bb) == 0 or bb == 'bb':
                continue
            all_bbs.append(bb)

    logger.info(f"found {len(all_bbs)} input basic blocks")
    random.shuffle(all_bbs)

    target_number = args.num
    selected_bbs = []

    filtered_schemes = set(ctx.filtered_insn_schemes)

    idx = 0
    with ProgressBar(f"selecting basic blocks",
            suffix = '%(percent).1f%%',
            max=target_number) as pb:
        while len(selected_bbs) < target_number:
            if idx >= len(all_bbs):
                logger.warning(f"Not enough suitable basic blocks in the input!")
                break
            bb_hex = all_bbs[idx]
            try:
                bb = ctx.decode_insns_bb(bb_hex)
                for i in bb:
                    if i.scheme not in filtered_schemes:
                        # we don't take this BB
                        break
                else:
                    pb.next()
                    selected_bbs.append(bb_hex)
            except iwho.IWHOError:
                # we don't take this BB
                pass

            idx += 1

    logger.info(f"selected {len(selected_bbs)} basic blocks")

    with open(args.output, 'w') as f:
        w = csv.writer(f)
        w.writerows(( (x,) for x in selected_bbs))

    return 0

if __name__ == "__main__":
    sys.exit(main())
