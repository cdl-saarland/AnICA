#!/usr/bin/env python3

"""Small script to get interesting blocks out of the overview results.
"""

import argparse
import csv
import textwrap

import iwho

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("infile", metavar="CSVFILE", help="csv file containing the overview results")

    args = ap.parse_args()

    data = []
    with open(args.infile) as f:
        r = csv.DictReader(f)

        for row in r:
            entry = {}
            entry['bb'] = row['bb']
            vals = []
            for col, val in row.items():
                if col == 'bb':
                    continue
                entry[col] = float(val)
                vals.append(float(val))

            if len(vals) <= 1 or min(vals) <= 0:
                variety = 42.0
            else:
                vals.sort()
                dist = 0
                prev = vals[0]
                divisor = min(vals)
                for v in vals[1:]:
                    dist += abs(v - prev)/divisor
                    prev = v
                variety = dist / len(vals) - 1

            entry['.variety'] = variety
            data.append(entry)

    data.sort(key=lambda x: x['.variety'], reverse=True)

    ctx = iwho.get_context('x86')

    coder = ctx.coder

    num = 0
    for entry in data:
        if entry['.variety'] == 42.0:
            continue

        strbb = "\n".join(map(lambda x: 4*' ' + x, coder.hex2asm(entry['bb'])))
        if 'div' in strbb:
            continue

        if 'cpuid' in strbb:
            continue

        if num >= 30:
            break
        num += 1

        print("Entry:")
        print(strbb)
        for k, v in entry.items():
            print(f'  {k}: {v}')
        print("")


if __name__ == '__main__':
    main()
