#!/usr/bin/env python3

""" Evaluate the csv result of anica_overview_coverage.py
"""


import argparse
from collections import Counter
import csv
from pathlib import Path
import textwrap

import os
import sys

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from anica.configurable import pretty_print


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("infile", metavar="CSVFILE", help="csv file containing the coverage results")

    args = ap.parse_args()

    infile = args.infile

    data = []
    with open(infile, 'r') as f:
        reader = csv.DictReader(f)
        for line in reader:
            data.append(line)

    print("## Campaigns where less 50% of the interesting blocks were covered:")
    predictors = Counter()
    entries = []
    for r in data:
        if float(r['percent_covered_interesting']) < 50:
            entries.append(r)
            predictors.update(r['predictors'].split('_X_'))
            print(pretty_print(r))
    print(f"In total: {len(entries)} offending campaigns with these predictors:")
    print(predictors)

    print("\n## Absolute numbers of bbs covered vs percent interesting covered:")
    pred_column = []
    num_column = []
    percent_column = []
    for r in data:
        pred_column.append(r['predictors'])
        covered = int(r['num_covered_interesting']) + int(r['num_covered_boring'])
        num_column.append(covered)
        percent_column.append(float(r['percent_covered_interesting']))

    pred_width = max(map(len, pred_column)) + 2
    num_width = max(map(lambda x: len(str(x)), num_column)) + 2
    percent_width = 5
    for pred, num, percent in zip(pred_column, num_column, percent_column):
        print((" - {:" + str(pred_width) + "}: {:" + str(num_width) + "} ({:" + str(percent_width) + ".1f}%)").format(pred, num, percent))

    print("\n## Latex csv table:")

    all_predictors = set()

    entries = dict()
    for r in data:
        r_preds = tuple(sorted(r['predictors'].split('_X_')))
        entries[r_preds] = "{:.0f}\% / \\textbf{{{:.0f}}}\%".format(100 * float(r['ratio_interesting_bbs']), float(r['percent_covered_interesting']))
        all_predictors.update(r_preds)
    order = list(sorted(all_predictors))

    def split_junk(x):
        return x.split('.')[0]

    lines = []
    col_names = list(map(split_junk , order))
    lines.append(','.join([''] + col_names))
    for i1, p1 in list(enumerate(order))[1:]:
        line = [split_junk(p1)]
        for i2, p2 in list(enumerate(order))[:-1]:
            if i2 >= i1:
                line.append('---')
                continue
            line.append(entries[tuple(sorted([p1, p2]))])
        lines.append(",".join(line))
    print("\n".join(lines))





if __name__ == "__main__":
    main()
