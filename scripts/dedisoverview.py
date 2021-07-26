#!/usr/bin/env python3

"""A small script with tools to get an overview of the number of deviations
between several BB instruction throughput predictors.

TODO mode of operation
"""

import argparse
import csv

import os
import random
import re
import sys

from iwho.utils import parse_args_with_logging

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractblock import AbstractBlock
from devidisc.abstractioncontext import AbstractionContext
from devidisc.configurable import load_json_config

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

    argparser.add_argument('-n', '--num-insns', type=int, default=None, metavar="N",
            help='maximal number of instructions per sampled basic block (if no input is given)')

    argparser.add_argument('predictors', nargs='*', metavar="PREDICTOR_ID",
            help='identifier(s) from the predictor registry of the predictors to use')

    args = parse_args_with_logging(argparser, "info")


    random.seed(args.seed)

    actx_config = load_json_config(args.config)
    actx = AbstractionContext(config=actx_config)

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
        if args.num_experiments is None or args.num_insns is None:
            print("Error: Neither input nor number and length of blocks to sample are given!", file=sys.stderr)
            sys.exit(1)
        top = AbstractBlock.make_top(actx, args.num_insns)
        x = 0
        while len(data) < args.num_experiments:
            assert x < 10 * args.num_experiments, "too many samples are failing!"
            x += 1
            try:
                sample_bb = top.sample()
                sample_hex = sample_bb.get_hex()
                data.append({'bb': sample_hex})
            except SamplingError as e:
                logger.info("a sample failed: {e}")

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
    bbs = [ iwho_ctx.make_bb( iwho_ctx.decode_insns(r['bb']) ) for r in data ]
    for record, (bb, result) in zip(data, predman.eval_with_all(bbs)):
        for k, v in result.items():
            tp = v.get('TP', None)
            if tp is None:
                tp = -1.0
            record[k] = tp

    # write the results
    with open(outname, 'w') as f:
        writer = csv.DictWriter(f, keys)
        writer.writeheader()
        writer.writerows(data)



if __name__ == "__main__":
    main()

