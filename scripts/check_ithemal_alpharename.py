#!/usr/bin/env python3

""" A small script to test how sensitive a throughput predictor is with respect
to semantics-preserving register substitution.
"""

import argparse
import csv
import random
import textwrap

import os
import sys

import iwho
from iwho.utils import parse_args_with_logging

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.predmanager import PredictorManager

import logging
logger = logging.getLogger(__name__)

def main():
    default_seed = 424242

    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-b', '--benchmarks', required=True, metavar="CONFIG",
            help='csv file containing the benchmarks that should be checked')

    argparser.add_argument('-s', '--seed', type=int, default=default_seed, metavar="N",
            help='seed for the rng')

    argparser.add_argument('predictor', metavar="PREDICTOR_ID",
            help='id of predictor to test')

    args = parse_args_with_logging(argparser, "info")

    random.seed(args.seed)

    ctx = iwho.get_context("x86")

    pred_key = args.predictor

    predman = PredictorManager(config={})
    predman.set_predictors([pred_key])

    bbs = []
    tps = []
    with open(args.benchmarks, 'r') as f:
        reader = csv.reader(f)
        for idx, row in enumerate(reader):
            if idx >= 40:
                break
            bmk = row[0]
            if len(bmk) == 0:
                continue
            expected_tp = float(row[1]) / 100.0
            bbs.append(ctx.make_bb(ctx.decode_insns(bmk)))
            tps.append(expected_tp)

    pred_res = predman.eval_with_all(bbs)

    all_errors = []

    for (bb, eval_res), expected_tp in zip(pred_res, tps):
        pred_tp = eval_res[pred_key]['TP']
        if pred_tp is None or pred_tp <= 0.0:
            print("prediction failed for block '{}'".format("; ".join(bb.insns)))
            continue
        rel_error = abs(pred_tp - expected_tp) / expected_tp
        all_errors.append(rel_error)

    if len(all_errors) == 0:
        print("All predictions failed!")
        sys.exit(1)

    mae = sum(all_errors) / len(all_errors)

    print("MAPE: {:.1f}%".format(mae*100))


if __name__ == "__main__":
    main()
