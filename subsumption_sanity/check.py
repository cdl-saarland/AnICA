#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path
import textwrap

import os
import sys

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from iwho.configurable import load_json_config, store_json_config
from anica.abstractblock import AbstractBlock
from anica.abstractioncontext import AbstractionContext
from anica.satsumption import check_subsumed, check_subsumed_fixed_order
from anica.utils import Timer

def load_bb_csv(iwho_ctx, filename):
    res = []
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for idx, line in enumerate(reader):
            bb = line['bb']
            res.append(iwho_ctx.make_bb(iwho_ctx.decode_insns(bb)))
    return res


def get_covered(actx, all_abs, all_bbs, subsumption_fun, get_metrics=False):
    covered = []

    not_covered = all_bbs

    for ab in all_abs:
        next_not_covered = []

        # precomputing schemes speeds up subsequent check_subsumed calls for this abstract block
        precomputed_schemes = []
        for ai in ab.abs_insns:
            precomputed_schemes.append(actx.insn_feature_manager.compute_feasible_schemes(ai.features))

        for bb in not_covered:
            if subsumption_fun(bb, ab, precomputed_schemes=precomputed_schemes):
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

def main():
    Timer.enabled = True
    # ap = argparse.ArgumentParser(description=__doc__)
    # args = ap.parse_args()

    boring_file = os.path.join(os.path.dirname(__file__), 'bbs_boring_100.csv')
    interesting_file = os.path.join(os.path.dirname(__file__), 'bbs_interesting_100.csv')

    ab_file = os.path.join(os.path.dirname(__file__), 'subsumption_abs.json')

    all_abs = []
    with open(ab_file, 'r') as f:
        loaded = load_json_config(ab_file)
        actx = AbstractionContext(config=loaded['config'])
        for ab_json in loaded['abs']:
            ab_data = actx.json_ref_manager.resolve_json_references(ab_json)
            all_abs.append(AbstractBlock.from_json_dict(actx, ab_data))

    boring_bbs = load_bb_csv(actx.iwho_ctx, boring_file)
    interesting_bbs = load_bb_csv(actx.iwho_ctx, interesting_file)

    def check_fun(subsumption_fun):
        print("  interesting:")
        print(textwrap.indent(get_covered(actx=actx, all_abs=all_abs, all_bbs=interesting_bbs, subsumption_fun=subsumption_fun, get_metrics=True), 4*' '))

        print("  boring:")
        print(textwrap.indent(get_covered(actx=actx, all_abs=all_abs, all_bbs=boring_bbs, subsumption_fun=subsumption_fun, get_metrics=True), 4*' '))


    print("plain lattice order:")
    def check_subsumed_lattice(bb, ab, *args, **kwargs):
        if len(bb.insns) != len(ab.abs_insns):
            return False

        bb_ab = AbstractBlock(actx, bb)
        return ab.subsumes(bb_ab)

    with Timer("plain lattice order") as t:
        check_fun(check_subsumed_lattice)
    print(t.get_result())

    print("fixed-order satsumption:")
    with Timer("fixed-order satsumption") as t:
        check_fun(check_subsumed_fixed_order)
    print(t.get_result())

    print("original satsumption:")
    with Timer("original satsumption") as t:
        check_fun(check_subsumed)
    print(t.get_result())


if __name__ == "__main__":
    main()
