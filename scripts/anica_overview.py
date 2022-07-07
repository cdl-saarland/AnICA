#!/usr/bin/env python3

"""A small script with tools to get an overview of the number of
inconsistencies between several BB instruction throughput predictors.
"""

import argparse
from collections import defaultdict
import csv

import os
import random
import re
import sys

from iwho.utils import parse_args_with_logging

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from anica.abstractblock import AbstractBlock, SamplingError
from anica.abstractioncontext import AbstractionContext
from anica.bbset_coverage import make_heatmap
from iwho.configurable import load_json_config

import logging
logger = logging.getLogger(__name__)


def main():
    default_seed = 424242

    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-c', '--config', metavar="CONFIG", default=None,
            help='abstraction context configuration file in json format')

    argparser.add_argument('-s', '--seed', type=int, default=default_seed, metavar="N",
            help='seed for the rng')

    argparser.add_argument('-o', '--output', default=None, metavar="OUTFILE",
            help='filename to write the results to (in csv format)')

    argparser.add_argument('-i', '--input', default=None, metavar="INFILE",
            help='filename to read basic blocks (and, optionally, previous measurements) from (in csv format)')

    argparser.add_argument('-x', '--num-experiments', type=int, default=None, metavar="N",
            help='number of random experiments to sample if no input is given')

    argparser.add_argument('--heatmap', default=None, metavar='IMGFILE',
            help='if this is specified, just make a heatmap from the input data and safe it to the specified file')

    argparser.add_argument('--threshold', default=0.5, type=float, metavar='V',
            help='if creating a heatmap, only count cases with a deviation of at least this value')

    argparser.add_argument('predictors', nargs='*', metavar="PREDICTOR_ID",
            help='identifier(s) from the predictor registry of the predictors to use')

    args = parse_args_with_logging(argparser, "info")


    random.seed(args.seed)

    rest_keys = args.predictors

    actx_config = load_json_config(args.config)
    actx = AbstractionContext(config=actx_config, restrict_to_insns_for=rest_keys)

    if args.input is None and args.output is None:
        print("Error: Cannot infer output file name, please specify one via -o or --out(put)", file=sys.stderr)
        sys.exit(1)
    elif args.output is not None:
        outname = args.output
    else:
        mat = re.fullmatch(r'\(.*_eval\)\(\d+\)\.csv', args.input)
        if mat:
            main_part = mat.group(1)
            num_str = mat.group(2)
            num = int(num_str)
            num_len = len(num_str)
            outname = ("{}{:0" + num_len + "}.csv").format(main_part, num + 1)
        else:
            path, ext = os.path.splitext(args.input)
            outname = path + "_eval00" + ext

    data = []
    keys = []

    if args.input is not None:
        # read basic blocks and previous data from the input
        with open(args.input, 'r') as f:
            reader = csv.DictReader(f)
            for line in reader:
                data.append(line)
            keys = list(reader.fieldnames)

        if len(data) == 0:
            print("Error: Specified empty input file!", file=sys.stderr)
            sys.exit(1)
    else:
        # sample new basic blocks
        keys = ['bb']
        if args.num_experiments is None:
            print("Error: Neither input nor number and length of blocks to sample are given!", file=sys.stderr)
            sys.exit(1)
        logger.info(f"start sampling {args.num_experiments} experiments")
        x = 0
        while len(data) < args.num_experiments:
            assert x < 10 * args.num_experiments, "too many samples are failing!"
            x += 1
            try:
                curr_num_insns = random.choice(actx.discovery_cfg.discovery_possible_block_lengths)
                top = AbstractBlock.make_top(actx, curr_num_insns)
                sample_bb = top.sample()
                sample_hex = sample_bb.get_hex()
                data.append({'bb': sample_hex})
            except SamplingError as e:
                logger.info("a sample failed: {e}")
        logger.info(f"done sampling {args.num_experiments} experiments")

    if args.heatmap is not None:
        if args.input is None:
            print("Error: Asking for a heatmap without input!", file=sys.stderr)
            sys.exit(1)
        fig = make_heatmap(keys, data, err_threshold=args.threshold, paper_mode=True)
        fig.savefig(args.heatmap)

        sys.exit(0)

    # set the predictors we need
    predman = actx.predmanager
    predman.set_predictors(args.predictors)

    already_found = set(keys)
    matching_predictors = predman.predictor_map.keys()
    for p in matching_predictors:
        if p in already_found:
            del predman.predictor_map[p]
        else:
            keys.append(p)

    iwho_ctx = actx.iwho_ctx

    # perform the measurements
    logger.info(f"start decoding {len(data)} experiments")
    bbs = []
    filtered_data = [] # we should only use blocks that we can actually decode
    for r in data:
        try:
            bbs.append( iwho_ctx.make_bb( iwho_ctx.decode_insns(r['bb']) ) )
            filtered_data.append(r)
        except Exception as e:
            logger.info("decoding a basic block failed: {}".format(e))

    logger.info(f"successfully decoded {len(bbs)} of {len(data)} experiments")

    logger.info(f"start evaluating {len(bbs)} experiments")
    for record, (bb, result) in zip(filtered_data, predman.eval_with_all(bbs)):
        for k, v in result.items():
            tp = v.get('TP', None)
            if tp is None:
                tp = -1.0
            if tp <= 0.0:
                logger.warning(f"prediction error for block '{bb}' with {k}: {v}")
            record[k] = tp
    logger.info(f"done evaluating {len(bbs)} experiments")

    # write the results
    with open(outname, 'w') as f:
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        writer.writerows(filtered_data)


if __name__ == "__main__":
    main()

