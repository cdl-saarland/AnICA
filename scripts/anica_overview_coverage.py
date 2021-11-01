#!/usr/bin/env python3

"""Get the ratio of concrete blocks in a set of benchmarks covered by the discoveries of 
"""

import argparse
import csv
from pathlib import Path
import textwrap

import os
import sys

import multiprocessing
from multiprocessing import Pool
from functools import partial

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from anica.configurable import load_json_config
from anica.abstractblock import AbstractBlock
from anica.abstractioncontext import AbstractionContext
from anica.satsumption import check_subsumed

def get_covered(actx, all_abs, all_bbs, get_metrics=False):
    covered = []

    not_covered = all_bbs

    for ab in all_abs:
        next_not_covered = []

        # precomputing schemes speeds up subsequent check_subsumed calls for this abstract block
        precomputed_schemes = []
        for ai in ab.abs_insns:
            precomputed_schemes.append(actx.insn_feature_manager.compute_feasible_schemes(ai.features))

        for bb in not_covered:
            if check_subsumed(bb, ab, precomputed_schemes=precomputed_schemes):
                covered.append(bb)
            else:
                next_not_covered.append(bb)

        not_covered = next_not_covered


    if get_metrics:
        total_num = len(all_bbs)
        num_covered = len(covered)
        num_not_covered = len(not_covered)

        percent_covered = (num_covered * 100) / total_num
        percent_not_covered = (num_not_covered * 100) / total_num

        res_str = f"covered: {num_covered} ({percent_covered:.1f}%)\n" + f"not covered: {num_not_covered} ({percent_not_covered:.1f}%)"
        return res_str
    else:
        return covered


def handle_campaign(campaign_dir, infile, threshold):
    base_dir = Path(campaign_dir)
    discovery_dir = base_dir / "discoveries"

    # find out about which pair of predictors this campaign is
    campaign_config = load_json_config(base_dir / "campaign_config.json")
    predictors = campaign_config['predictors']

    assert len(predictors) == 2, "the campaign comparse an unexpected number of predictors: {}".format(", ".join(map(str, predictors)))

    res_str = str(predictors)
    res_str += "\n"

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

    res_str += "num of abstract blocks: {}\n\n".format(len(all_abs))

    iwho_ctx = actx.iwho_ctx

    full_bb_num = 0
    interesting_bbs = []
    boring_bbs = []
    with open(infile, 'r') as f:
        reader = csv.DictReader(f)
        for idx, line in enumerate(reader):
            full_bb_num +=1
            bb = line['bb']
            eval_res = {}
            for k in predictors:
                eval_res[k] = { 'TP': float(line[k])}
            interestingness = actx.interestingness_metric.compute_interestingness(eval_res)
            if interestingness >= threshold:
                interesting_bbs.append(iwho_ctx.make_bb(iwho_ctx.decode_insns(bb)))
            else:
                boring_bbs.append(iwho_ctx.make_bb(iwho_ctx.decode_insns(bb)))

    res_str += "interesting: {} out of {} ({:.1f}%)\n".format(len(interesting_bbs), full_bb_num, (len(interesting_bbs) * 100) / full_bb_num)
    res_str += textwrap.indent(get_covered(actx=actx, all_abs=all_abs, all_bbs=interesting_bbs, get_metrics=True), '  ')
    res_str += "\n"

    res_str += "boring: {} out of {} ({:.1f}%)\n".format(len(boring_bbs), full_bb_num, (len(boring_bbs) * 100) / full_bb_num)
    res_str += textwrap.indent(get_covered(actx=actx, all_abs=all_abs, all_bbs=boring_bbs, get_metrics=True), '  ')
    res_str += "\n"
    return res_str

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-c", "--campaigndirs", required=True, nargs='+', metavar="PATH", help="path of the campaign directory whose discoveries should be used.")
    ap.add_argument('--threshold', default=0.5, type=float, metavar='V',
            help='only check input bbs with a deviation of at least this value')

    ap.add_argument("infile", metavar="CSVFILE", help="csv file containing the overview results")


    args = ap.parse_args()

    threshold = args.threshold

    infile = args.infile

    num_processes = multiprocessing.cpu_count()
    proc_pool = Pool(num_processes)

    results = proc_pool.imap(partial(handle_campaign, infile=infile, threshold=threshold), args.campaigndirs)

    for r in results:
        print(r)

    proc_pool.close()


if __name__ == "__main__":
    main()
