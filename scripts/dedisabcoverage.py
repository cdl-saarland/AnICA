#!/usr/bin/env python3

""" TODO document
"""

import argparse
import json
import os
import sys

from iwho.utils import parse_args_with_logging

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractioncontext import AbstractionContext
from devidisc.abstractblock import AbstractBlock
from devidisc.satsumption import compute_coverage


def main():
    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('abfile', metavar='ABSTRACTBLOCK', help='path to an abstract block file in json format')

    args = parse_args_with_logging(argparser, "info")

    with open(args.abfile) as f:
        json_dict = json.load(f)

    config_dict = json_dict['config']

    config_dict['predmanager'] = None # we don't need that one here

    actx = AbstractionContext(config=config_dict)

    ab_dict = actx.json_ref_manager.resolve_json_references(json_dict['ab'])

    ab = AbstractBlock.from_json_dict(actx, ab_dict)

    concrete_bbs = []
    sample_universe = AbstractBlock.make_top(actx, 5)
    for x in range(10000):
        try:
            concrete_bbs.append(sample_universe.sample())
        except SamplingError as e:
            logger.info("a sample failed: {e}")

    coverage_ratio = compute_coverage(ab, concrete_bbs)
    print(f"coverage ratio: {coverage_ratio}")

if __name__ == "__main__":
    main()
