#!/usr/bin/env python3

""" Produce a plot for the coverage ratios of AnICA campaigns over their lifetime.
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
from anica.abstractioncontext import AbstractionContext
from anica.satsumption import check_subsumed


import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


def compute_series(actx, all_abs, all_bbs):
    total = len(all_bbs)
    covered = []

    not_covered = all_bbs

    covered_per_ab = dict()

    series = []

    for gen_id, ab in all_abs:
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

        series.append(len(covered) / total)

        not_covered = next_not_covered

    return series


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
        all_abs.append((gen_id, ab))

    # sort by gen_id, this coincides with the discovery order
    all_abs.sort(key=lambda x: x[0])

    iwho_ctx = actx.iwho_ctx

    full_bb_num = 0
    interesting_bbs = []
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

    series = compute_series(actx, all_abs, interesting_bbs)

    res_dict = {
            'predictors': predictors,
            'series': series,
        }
    return res_dict

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-c", "--campaigndirs", required=True, nargs='+', metavar="PATH", help="path of the campaign directory whose discoveries should be used.")
    ap.add_argument('--threshold', default=0.5, type=float, metavar='V',
            help='only check input bbs with a deviation of at least this value')

    ap.add_argument('-o', "--output", metavar="PLOT", required=True, help="file to write the plot to")
    ap.add_argument("infile", metavar="CSVFILE", help="csv file containing the overview results")


    args = ap.parse_args()

    load = False

    if not load:
        threshold = args.threshold

        infile = args.infile

        num_processes = multiprocessing.cpu_count()
        proc_pool = Pool(num_processes)

        results = proc_pool.imap(partial(handle_campaign, infile=infile, threshold=threshold), args.campaigndirs)

        records = []
        for res_dict in results:
            records.append(res_dict)

        proc_pool.close()

        # TODO records

        data = { 'preds': [], 'idx': [], 'num_covered': []}
        for r in records:
            preds = r['predictors']
            for idx, entry in enumerate(r['series']):
                if bin(idx).count('1') != 1:
                    continue
                data['preds'].append(preds)
                data['idx'].append(idx)
                data['num_covered'].append(entry)

        df = pd.DataFrame(data)

        df.to_pickle('./data.df')
    else:
        df = pd.read_pickle('./data.df')


    f, ax = plt.subplots(figsize=(7, 7))
    # ax.set(xscale="exp")

    p = sns.pointplot(data=df, x="idx", y="num_covered", hue="preds", ax=ax);

    # plt.title(f"Percentage of blocks with a rel. error >= {err_threshold} on a set of {len(data)} blocks")

    # locs, labels = plt.xticks()
    # plt.setp(labels, rotation=30)
    # p.set_xticklabels(p.get_xticklabels(), rotation=30, horizontalalignment='right')

    # plt.tight_layout()
    f.savefig(args.output)


if __name__ == "__main__":
    main()
