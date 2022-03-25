#!/usr/bin/env python3

""" Evaluate the csv result of anica_overview_coverage.py
"""


import argparse
from datetime import timedelta
from collections import Counter
import csv
from pathlib import Path
import textwrap

import os
import sys

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from iwho.configurable import pretty_print

def strfdelta(tdelta, fmt):
    d = {"days": tdelta.days}
    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    return fmt.format(**d)

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

    # print("\n## Latex csv table:")
    #
    # all_predictors = set()
    #
    # entries = dict()
    # for r in data:
    #     r_preds = tuple(sorted(r['predictors'].split('_X_')))
    #     entries[r_preds] = "{:.0f}\% / \\textbf{{{:.0f}}}\%".format(100 * float(r['ratio_interesting_bbs']), float(r['percent_covered_interesting']))
    #     all_predictors.update(r_preds)
    # order = list(sorted(all_predictors))
    #
    # def split_junk(x):
    #     return x.split('.')[0]
    #
    # lines = []
    # col_names = list(map(split_junk , order))
    # lines.append(','.join([''] + col_names))
    # for i1, p1 in list(enumerate(order))[1:]:
    #     line = [split_junk(p1)]
    #     for i2, p2 in list(enumerate(order))[:-1]:
    #         if i2 >= i1:
    #             line.append('---')
    #             continue
    #         line.append(entries[tuple(sorted([p1, p2]))])
    #     lines.append(",".join(line))
    # print("\n".join(lines))



    def latex_pred_name(x):
        components = x.split('.')
        if x.startswith('llvm-mca'):
            if components[1].startswith('13'):
                return "\\llvmmca.13"
            else:
                return "\\llvmmca." + components[1].split('-')[0]
        # elif x.startswith('difftune'):
        #     return "DT"
        else:
            return "\\" + components[0]
            # return components[0]

    print("\n## Latex horizontal table:")

    columns = []
    columns.append(["", " BBs interesting", "int. BBs covered", "\\dots by top 10", "campaign time (h:m)"])
    # columns.append(["", " BBs interesting", "int. BBs covered", "\\dots by top 10", "other BBs covered", "campaign time (h:m)"])
    # columns.append(["", " BBs interesting (\\%)", "int. BBs covered (\\%)", "other BBs covered (\\%)", "\\# Discoveries"])
    for r in sorted(data, key=lambda x: float(x['percent_covered_interesting']), reverse=True):
        r_preds = tuple(sorted(map(latex_pred_name, r['predictors'].split('_X_'))))
        if "\\llvmmca.8" in r_preds:
            continue
        column = []
        column.append(",".join(r_preds))
        # column.append("{:.1f}".format(100 * float(r["ratio_interesting_bbs"])))
        # column.append("{:.1f}".format(float(r["percent_covered_interesting"])))
        # column.append("{:.1f}".format(float(r["percent_covered_boring"])))
        column.append("{:.0f}\\%".format(100 * float(r["ratio_interesting_bbs"])))
        column.append("{:.0f}\\%".format(float(r["percent_covered_interesting"])))

        covered_percent = 100 * float(r["covered_by_10"])/float(r["num_interesting_bbs"])
        column.append("{:.0f}\\%".format(covered_percent))
        # column.append("{:.0f}\\%".format(float(r["percent_covered_boring"])))
        # column.append("{}".format(int(r["num_abstract_blocks"])))

        td = timedelta(seconds=int(float(r["campaign_seconds"])))
        assert td.days == 0
        column.append(strfdelta(td, "{hours:01d}:{minutes:02d}"))
        columns.append(column)

    # to make it vertical:
    # list(zip(*columns))

    column_str = "r|" + (len(columns) - 1) * "c|"
    res = "% start of generated table\n\\begin{tabular}{" + column_str + "}\n"
    for idx, row in enumerate(zip(*columns)):
        res += "  "
        if idx == 0:
            row = map(lambda x: "\\rot{" + x + "}" if len(x) > 0 else "", row)
        res += " & ".join(row)
        res += "\\\\\n"
        if idx == 0:
            res += "  \\hline\n"

    res += "  \\hline\n"

    res += "\\end{tabular}\n% end of generated table\n"

    print(res)


    df_data = {
            "Campaign": [],
            "BBs interesting": [],
            "int. BBs covered": [],
            "... by top 10": [],
        }
    for r in sorted(data, key=lambda x: float(x['percent_covered_interesting']), reverse=True):
        r_preds = tuple(sorted(map(latex_pred_name, r['predictors'].split('_X_'))))
        if "\\llvmmca.8" in r_preds:
            continue
        df_data['Campaign'].append(",".join(r_preds))
        ratio_interesting = float(r["ratio_interesting_bbs"])
        df_data['BBs interesting'].append(100 * ratio_interesting)
        df_data['int. BBs covered'].append(ratio_interesting * float(r["percent_covered_interesting"]))
        covered_percent = 100 * float(r["covered_by_10"])/float(r["num_interesting_bbs"])
        df_data['... by top 10'].append(ratio_interesting * covered_percent)

    df = pd.DataFrame(df_data)

    s1 = sns.barplot(x = 'Campaign', y = 'BBs interesting', data = df, color = 'red')
    s2 = sns.barplot(x = 'Campaign', y = 'int. BBs covered', data = df, color = 'blue')
    s3 = sns.barplot(x = 'Campaign', y = '... by top 10', data = df, color = 'green')

    # create stacked bar chart for monthly temperatures
    # df.plot(kind='bar', stacked=True)
    # df.plot(kind='bar', stacked=True, color=['red', 'skyblue', 'green'])
    bar1 = mpatches.Patch(color='red', label='BBs interesting')
    bar2 = mpatches.Patch(color='blue', label='int. BBs interesting')
    bar3 = mpatches.Patch(color='green', label='... by top 10')
    plt.legend(handles=[bar1, bar2, bar3])

    # labels for x & y axis
    plt.xlabel('Campaign')
    plt.ylabel('% of sampled basic blocks')
    plt.xticks(rotation=45)
    plt.savefig("out.png")


if __name__ == "__main__":
    main()
