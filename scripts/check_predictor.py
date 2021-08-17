#!/usr/bin/env python3

""" A small script to test whether predictors can handle all instructions.
"""

import argparse
import random
import textwrap

import os
import sys

from iwho.utils import parse_args_with_logging

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractioncontext import AbstractionContext
from devidisc.abstractblock import AbstractBlock, SamplingError
from devidisc.configurable import load_json_config

import logging
logger = logging.getLogger(__name__)

def main():
    default_seed = 424242

    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-c', '--config', default=None, metavar="CONFIG",
            help='abstraction context config file in json format')

    argparser.add_argument('-s', '--seed', type=int, default=default_seed, metavar="N",
            help='seed for the rng')

    argparser.add_argument('predictors', nargs='+', metavar="PREDICTOR_ID",
            help='ids of predictor(s) to test')

    args = parse_args_with_logging(argparser, "info")

    random.seed(args.seed)

    if args.config is None:
        config = {}
    else:
        config = load_json_config(args.config)

    actx = AbstractionContext(config=config)

    batch_size = 10
    # batch_size = actx.discovery_cfg.generalization_batch_size


    for pred_key in args.predictors:
        error_schemes = []
        logger.info(f"checking predictor '{pred_key}'")
        for ischeme in actx.iwho_ctx.filtered_insn_schemes:
            ab = AbstractBlock.make_top(actx, num_insns=1)
            ab.abs_insns[0].features['exact_scheme'].val = ischeme
            sampler = ab.precompute_sampler()
            sampled_bbs = []

            num_sampling_errors = 0
            for i in range(batch_size):
                try:
                    sampled_bbs.append(sampler.sample())
                except SamplingError as e:
                    num_sampling_errors += 1

            results = actx.predmanager.do(pred_key, sampled_bbs)

            num_prediction_errors = 0
            all_results = dict()
            for bb, r in zip(sampled_bbs, results):
                cycles = r.get('TP', None)
                if cycles is None or cycles <= 0:
                    num_prediction_errors += 1
                    error_schemes.append(ischeme)
                else:
                    all_results[cycles] = str(bb).strip()

            logger.info(f"sampling errors: {num_sampling_errors}")
            logger.info(f"prediction errors: {num_prediction_errors} (in {len(sampled_bbs)} samples)")

            if len(all_results) > 1:
                logger.info("got several different predictions:\n" +
                        textwrap.indent("\n".join(sorted(map(lambda x: f"{x[0]}: {x[1]}", all_results.items()))), '  '))

        with open(f'error_schemes_{pred_key}.csv', 'w') as f:
            for ischeme in error_schemes:
                print(str(ischeme), file=f)




if __name__ == "__main__":
    main()
