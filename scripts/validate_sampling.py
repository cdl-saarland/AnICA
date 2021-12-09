#!/usr/bin/env python3

""" A script to gather information about the sampling of concrete basic blocks
used in the generalization runs of a discovery campaign.
"""

import argparse
from collections import Counter
import math
import random
import textwrap
from pathlib import Path

import os
import sys

from iwho.utils import parse_args_with_logging

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from anica.witness import WitnessTrace
from iwho.configurable import load_json_config, pretty_print

import logging
logger = logging.getLogger(__name__)

def main():
    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('indir', nargs='+', metavar="PATH",
            help='directories of campaigns or paths to witnesses')

    argparser.add_argument('-o', '--output', required=True, metavar="PATH",
            help='file where suspicious results will be written')

    args = parse_args_with_logging(argparser, "info")


    file_paths = []

    for d in args.indir:
        p = Path(d)
        if p.is_file():
            file_paths.append(p)
        elif p.is_dir():
            for g in p.glob("witnesses/*.json"):
                file_paths.append(g)
        else:
            print("wrong input path: {}".format(p), file=sys.stderr)

    with open(args.output, 'w') as outfile:
        for p in file_paths:
            trace = WitnessTrace.load_json_dump(p)
            actx = trace.start.actx
            iwho = actx.iwho_ctx
            with actx.measurement_db as mdb:
                for witness, curr_ab in trace.iter():
                    meas_id = witness.measurements
                    if meas_id is None:
                        continue
                    counters = [Counter() for x in range(len(curr_ab.abs_insns))]
                    series = mdb.get_series(meas_id)
                    for m in series['measurements']:
                        hex_bb = m['input']
                        bb = iwho.decode_insns(hex_bb)
                        for idx, insn in enumerate(bb):
                            counters[idx][insn.scheme] += 1
                    num_measurements = len(series['measurements'])
                    for ai, counter in zip(curr_ab.abs_insns, counters):
                        feasible_schemes = actx.insn_feature_manager.compute_feasible_schemes(ai.features)
                        chance_factor = 2
                        suspicious_if_above = math.ceil((1 + math.ceil(1/len(feasible_schemes) * num_measurements)) * chance_factor)
                        for scheme, num in counter.items():
                            if num > suspicious_if_above:
                                print("suspicious samples in file '{witness_file}': {scheme} was sampled more than {k} times, namely {num}, in series {meas_id}".format(witness_file=p, scheme=scheme, k=suspicious_if_above, num=num, meas_id=meas_id), file=outfile)

                                out_data = dict()
                                out_data['config'] = actx.get_config(skip_doc=True)
                                out_data['ab'] = actx.json_ref_manager.introduce_json_references(curr_ab.to_json_dict())
                                pretty_ab = pretty_print(out_data)
                                print(" - abstract block:\n" + textwrap.indent(pretty_ab, "    "), file=outfile)


if __name__ == "__main__":
    main()
