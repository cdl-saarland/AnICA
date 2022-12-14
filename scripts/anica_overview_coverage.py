#!/usr/bin/env python3

"""Get the ratio of concrete blocks in a set of benchmarks covered by the
discoveries of AnICA campaigns.
"""

import argparse
import csv
import json
from pathlib import Path
import textwrap

import os
import sys

import multiprocessing
from multiprocessing import Pool
from functools import partial

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from iwho.configurable import load_json_config
from anica.abstractblock import AbstractBlock

from anica.bbset_coverage import get_coverage_metrics, compute_optimal_covering_set


def handle_campaign(campaign_dir, infile, threshold):
    base_dir = Path(campaign_dir)
    discovery_dir = base_dir / "discoveries"

    metrics_path = base_dir / 'metrics.json'
    if metrics_path.exists():
        with open(metrics_path, 'r') as f:
            metrics_dict = json.load(f)
    else:
        metrics_dict = {}

    # find out about which pair of predictors this campaign is
    campaign_config = load_json_config(base_dir / "campaign_config.json")
    predictors = campaign_config['predictors']

    assert len(predictors) == 2, "the campaign compares an unexpected number of predictors: {}".format(", ".join(map(str, predictors)))

    report_path = base_dir / "report.json"
    with open(report_path, 'r') as f:
        report = json.load(f)
        seconds_passed = report['seconds_passed']
        del report

    res_str = str(predictors)
    res_str += "\n"

    all_discovery_paths = discovery_dir.glob("*.json")

    all_abs = []

    actx = None
    for p in all_discovery_paths:
        ab = AbstractBlock.load_json_dump(p, actx=actx)
        if actx is None:
            actx = ab.actx
        gen_id = str(p).split('/')[-1].split('.')[0]
        ab_metrics = metrics_dict.get(gen_id, None)
        if ab_metrics is None:
            print(f"Warning: no metrics found for discovery {gen_id}!")
        else:
            subsumed_by = ab_metrics['subsumed_by']
            if subsumed_by is not None:
                continue
        all_abs.append(ab)

    # sort by ascending number of abstract instructions, as those with fewer instructions will probably be more helpful
    all_abs.sort(key=lambda x: len(x.abs_insns))

    res_str += "num of abstract blocks: {}\n\n".format(len(all_abs))

    iwho_ctx = actx.iwho_ctx

    num_decoding_fails = 0
    full_bb_num = 0
    interesting_bbs = []
    boring_bbs = []
    with open(infile, 'r') as f:
        reader = csv.DictReader(f)
        for idx, line in enumerate(reader):
            full_bb_num +=1
            bb = line['bb']
            try:
                decoded = iwho_ctx.make_bb(iwho_ctx.decode_insns(bb))
            except:
                num_decoding_fails += 1

            if threshold <= 0.0:
                interesting_bbs.append(decoded)
                continue

            eval_res = {}
            for k in predictors:
                eval_res[k] = { 'TP': float(line[k])}
            interestingness = actx.interestingness_metric.compute_interestingness(eval_res)
            if interestingness >= threshold:
                interesting_bbs.append(decoded)
            else:
                boring_bbs.append(decoded)

    res_str += "decoding fails: {}\n".format(num_decoding_fails)

    if full_bb_num == 0:
        return res_str, {}

    num_interesting_covered_top10, top10_abs = compute_optimal_covering_set(actx, all_abs, interesting_bbs, 10)

    res_str += "interesting: {} out of {} ({:.1f}%)\n".format(len(interesting_bbs), full_bb_num, (len(interesting_bbs) * 100) / full_bb_num)
    interesting_str, interesting_dict, interesting_covered_per_ab = get_coverage_metrics(actx=actx, all_abs=all_abs, all_bbs=interesting_bbs)
    res_str += textwrap.indent(interesting_str, '  ')
    res_str += "\n"

    coverage_table = list(sorted(interesting_covered_per_ab.items(), key=lambda x: x[1], reverse=True))

    covered_by_10 = None
    covered_by_20 = None
    covered_so_far = 0
    idx = 0
    bound = 1
    while True:
        while idx < len(coverage_table):
            if idx >= bound:
                break
            covered_so_far += coverage_table[idx][1]
            idx += 1
            if idx == 10:
                covered_by_10 = covered_so_far
            if idx == 20:
                covered_by_20 = covered_so_far

        else:
            break
        percentage = (100 * covered_so_far) / len(interesting_bbs)
        res_str += f"    covered with {bound} discoveries: {covered_so_far} ({percentage:.1f}%)\n"
        bound *= 2

    num_used = 0
    for k, v in coverage_table:
        if v != 0:
            num_used += 1

    res_str += f"    number of abstract blocks actually used for covering bbs: {num_used} out of {len(all_abs)}\n"


    res_str += "\n"

    res_str += "boring: {} out of {} ({:.1f}%)\n".format(len(boring_bbs), full_bb_num, (len(boring_bbs) * 100) / full_bb_num)
    boring_str, boring_dict, boring_covered_per_ab = get_coverage_metrics(actx=actx, all_abs=all_abs, all_bbs=boring_bbs)
    res_str += textwrap.indent(boring_str, '  ')
    res_str += "\n"

    res_dict = {
            'predictors': "_X_".join(map(str, predictors)),
            'campaign_seconds': seconds_passed,
            'num_abstract_blocks': len(all_abs),
            'num_bbs': full_bb_num,
            'covered_by_10_optimal': num_interesting_covered_top10,
            'covered_by_10': covered_by_10,
            'covered_by_20': covered_by_20,
            'num_interesting_bbs': len(interesting_bbs),
            'ratio_interesting_bbs': len(interesting_bbs) / full_bb_num,
            'num_boring_bbs': len(boring_bbs),
            'ratio_boring_bbs': len(boring_bbs) / full_bb_num,
        }
    for k, v in interesting_dict.items():
        res_dict[k + '_interesting'] = v

    for k, v in boring_dict.items():
        res_dict[k + '_boring'] = v

    return res_str, res_dict

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-c", "--campaigndirs", required=True, nargs='+', metavar="PATH", help="path of the campaign directory whose discoveries should be used.")
    ap.add_argument('--threshold', default=0.5, type=float, metavar='V',
            help='only check input bbs with a deviation of at least this value')

    ap.add_argument('-o', "--output", metavar="CSVFILE", required=True, help="csv file for writing the coverage results to")
    ap.add_argument("infile", metavar="CSVFILE", help="csv file containing the overview results")


    args = ap.parse_args()

    threshold = args.threshold

    infile = args.infile

    num_processes = multiprocessing.cpu_count()
    proc_pool = Pool(num_processes)

    results = proc_pool.imap(partial(handle_campaign, infile=infile, threshold=threshold), args.campaigndirs)

    records = []
    for res_str, res_dict in results:
        print(res_str)
        records.append(res_dict)

    proc_pool.close()

    with open(args.output, 'w') as f:
        keys = list(records[0].keys())
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    main()
