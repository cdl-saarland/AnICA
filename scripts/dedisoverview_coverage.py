#!/usr/bin/env python3

"""Get the ratio of concrete blocks in a set of benchmarks covered by the discoveries of 
"""

import argparse
import csv
from pathlib import Path
import textwrap

import os
import sys

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.configurable import load_json_config
from devidisc.abstractblock import AbstractBlock
from devidisc.abstractioncontext import AbstractionContext
from devidisc.satsumption import check_subsumed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-c", "--campaigndir", required=True, metavar="PATH", help="path of the campaign directory whose discoveries should be used.")
    ap.add_argument('--threshold', default=0.5, type=float, metavar='V',
            help='only check input bbs with a deviation of at least this value')

    ap.add_argument("infile", metavar="CSVFILE", help="csv file containing the overview results")


    args = ap.parse_args()

    threshold = args.threshold

    base_dir = Path(args.campaigndir)

    discovery_dir = base_dir / "discoveries"

    # find out about which pair of predictors this campaign is
    campaign_config = load_json_config(base_dir / "campaign_config.json")
    predictors = campaign_config['predictors']

    assert len(predictors) == 2, "the campaign comparse an unexpected number of predictors: {}".format(", ".join(map(str, predictors)))

    print(predictors)

    all_discovery_paths = discovery_dir.glob("*.json")

    all_abs = []

    actx = None
    for p in all_discovery_paths:
        ab = AbstractBlock.load_json_dump(p, actx=actx)
        if actx is None:
            actx = ab.actx
        all_abs.append(ab)

    # sort by ascending number of abstract instructions, as ones with fewer instructions will probably be more helpful
    all_abs.sort(key=lambda x: len(x.abs_insns))

    print("num of abstract blocks: {}".format(len(all_abs)))

    iwho_ctx = actx.iwho_ctx

    full_bb_num = 0
    all_bbs = []
    with open(args.infile, 'r') as f:
        reader = csv.DictReader(f)
        for idx, line in enumerate(reader):
            full_bb_num +=1
            bb = line['bb']
            eval_res = {}
            for k in predictors:
                eval_res[k] = { 'TP': float(line[k])}
            interestingness = actx.interestingness_metric.compute_interestingness(eval_res)
            if interestingness >= threshold:
                all_bbs.append(iwho_ctx.make_bb(iwho_ctx.decode_insns(bb)))

    print("interesting: {} out of {} ({:.1f}%)".format(len(all_bbs), full_bb_num, (len(all_bbs) * 100) / full_bb_num))

    covered = []
    not_covered = []
    # It might be possible to speed this up by interchanging these loops and precomputing the feasible schemes for the abs.
    for bb in all_bbs:
        for ab in all_abs:
            if check_subsumed(bb, ab):
                covered.append(bb)
                break
        else:
            not_covered.append(bb)

    total_num = len(all_bbs)
    num_covered = len(covered)
    num_not_covered = len(not_covered)

    percent_covered = (num_covered * 100) / total_num
    percent_not_covered = (num_not_covered * 100) / total_num

    print(f"covered: {num_covered} ({percent_covered:.1f}%)")
    print(f"not covered: {num_not_covered} ({percent_not_covered:.1f}%)")



if __name__ == "__main__":
    main()
