#!/usr/bin/env python3

""" For a list of campaigns, try to answer the question
"Which remarks did occur?".
"""

import argparse
from collections import Counter
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


def handle_campaign(campaign_dir):
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

    res_str = str(predictors)
    res_str += "\n"

    all_discovery_paths = discovery_dir.glob("*.json")

    all_abs = []
    all_remarks = []

    actx = None
    for p in all_discovery_paths:
        md = dict()
        ab = AbstractBlock.load_json_dump(p, actx=actx, metadata_res=md)
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
        all_remarks.append(md['remarks'])

    res_str += "num of abstract blocks: {}\n\n".format(len(all_abs))

    remark_counter = Counter()

    for rs in all_remarks:
        for r in rs:
            remark_counter[r] += 1

    res_str += "occuring remarks:\n"
    for k, v in remark_counter.most_common():
        res_str += f"  {k}: {v}\n"

    res_str += "\n"

    return res_str

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-c", "--campaigndirs", required=True, nargs='+', metavar="PATH", help="path of the campaign directory whose discoveries should be used.")

    # ap.add_argument('-o', "--output", metavar="CSVFILE", required=True, help="csv file for writing the coverage results to")
    # ap.add_argument("infile", metavar="CSVFILE", help="csv file containing the overview results")


    args = ap.parse_args()

    num_processes = multiprocessing.cpu_count()
    proc_pool = Pool(num_processes)

    results = proc_pool.imap(handle_campaign, args.campaigndirs)

    # records = []
    for res_str in results:
        print(res_str)
        # records.append(res_dict)

    proc_pool.close()

    # with open(args.output, 'w') as f:
    #     keys = list(records[0].keys())
    #     writer = csv.DictWriter(f, fieldnames=keys)
    #     writer.writeheader()
    #     writer.writerows(records)


if __name__ == "__main__":
    main()

