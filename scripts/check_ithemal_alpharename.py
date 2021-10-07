#!/usr/bin/env python3

""" A small script to test how sensitive a throughput predictor is with respect
to semantics-preserving register substitution.
"""

import argparse
import csv
import random
import textwrap

import os
import sys

import iwho
from iwho.utils import parse_args_with_logging

import iwho.x86 as x86

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.predmanager import PredictorManager

import logging
logger = logging.getLogger(__name__)

def main():
    default_seed = 424242

    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-b', '--benchmarks', required=True, metavar="CONFIG",
            help='csv file containing the benchmarks that should be checked')

    argparser.add_argument('-s', '--seed', type=int, default=default_seed, metavar="N",
            help='seed for the rng')

    argparser.add_argument('predictor', metavar="PREDICTOR_ID",
            help='id of predictor to test')

    args = parse_args_with_logging(argparser, "info")

    random.seed(args.seed)

    ctx = iwho.get_context("x86")

    pred_key = args.predictor

    predman = PredictorManager(config={})
    predman.set_predictors([pred_key])


    replacements = {
        }

    replacement_classes = [
            # (x86.RegAliasClass.GPR_B, x86.RegAliasClass.GPR_D),
            # (x86.RegAliasClass.GPR_C, x86.RegAliasClass.GPR_D),
            # (x86.RegAliasClass.GPR_D, x86.RegAliasClass.GPR_B),
            (x86.RegAliasClass.GPR_R8, x86.RegAliasClass.GPR_R11),
            (x86.RegAliasClass.GPR_R9, x86.RegAliasClass.GPR_R12),
            (x86.RegAliasClass.GPR_R10, x86.RegAliasClass.GPR_R8),
            (x86.RegAliasClass.GPR_R11, x86.RegAliasClass.GPR_R9),
            (x86.RegAliasClass.GPR_R12, x86.RegAliasClass.GPR_R10),

            (x86.RegAliasClass.vMM0, x86.RegAliasClass.vMM15),
            (x86.RegAliasClass.vMM1, x86.RegAliasClass.vMM14),
            (x86.RegAliasClass.vMM2, x86.RegAliasClass.vMM13),
            (x86.RegAliasClass.vMM3, x86.RegAliasClass.vMM12),
            (x86.RegAliasClass.vMM4, x86.RegAliasClass.vMM11),
            (x86.RegAliasClass.vMM5, x86.RegAliasClass.vMM10),
            (x86.RegAliasClass.vMM6, x86.RegAliasClass.vMM9),
            (x86.RegAliasClass.vMM7, x86.RegAliasClass.vMM8),
            (x86.RegAliasClass.vMM8, x86.RegAliasClass.vMM0),
            (x86.RegAliasClass.vMM9, x86.RegAliasClass.vMM7),
            (x86.RegAliasClass.vMM10, x86.RegAliasClass.vMM6),
            (x86.RegAliasClass.vMM11, x86.RegAliasClass.vMM5),
            (x86.RegAliasClass.vMM12, x86.RegAliasClass.vMM4),
            (x86.RegAliasClass.vMM13, x86.RegAliasClass.vMM3),
            (x86.RegAliasClass.vMM14, x86.RegAliasClass.vMM2),
            (x86.RegAliasClass.vMM15, x86.RegAliasClass.vMM1),

            (x86.RegAliasClass.vMM16, x86.RegAliasClass.vMM26),
            (x86.RegAliasClass.vMM17, x86.RegAliasClass.vMM27),
            (x86.RegAliasClass.vMM18, x86.RegAliasClass.vMM25),
            (x86.RegAliasClass.vMM19, x86.RegAliasClass.vMM17),
            (x86.RegAliasClass.vMM20, x86.RegAliasClass.vMM21),
            (x86.RegAliasClass.vMM21, x86.RegAliasClass.vMM16),
            (x86.RegAliasClass.vMM22, x86.RegAliasClass.vMM23),
            (x86.RegAliasClass.vMM23, x86.RegAliasClass.vMM29),
            (x86.RegAliasClass.vMM24, x86.RegAliasClass.vMM28),
            (x86.RegAliasClass.vMM25, x86.RegAliasClass.vMM24),
            (x86.RegAliasClass.vMM26, x86.RegAliasClass.vMM22),
            (x86.RegAliasClass.vMM27, x86.RegAliasClass.vMM18),
            (x86.RegAliasClass.vMM28, x86.RegAliasClass.vMM30),
            (x86.RegAliasClass.vMM29, x86.RegAliasClass.vMM31),
            (x86.RegAliasClass.vMM30, x86.RegAliasClass.vMM20),
            (x86.RegAliasClass.vMM31, x86.RegAliasClass.vMM19),
        ]

    for name, reg in x86.all_registers.items():
        for lhs, rhs in replacement_classes:
            if reg.alias_class == lhs:
                repl = ctx.get_registers_where(alias_class=rhs, width=reg.width)
                if len(repl) != 1:
                    replacements[reg] = reg
                    break

                replacements[reg] = repl[0]
                break
        else:
            replacements[reg] = reg

    # for k, v in replacements.items():
    #     print(f"{k}: {v}")


    def replace(bb):
        new_insns = []
        for ii in bb.insns:
            new_ops = {}
            for op, (k, op_scheme) in ii.get_operands():
                if isinstance(op, x86.RegisterOperand):
                    new_ops[k] = replacements[op]
                elif isinstance(op, x86.MemoryOperand):
                    if op.base is not None:
                        new_base = replacements[op.base]
                    else:
                        new_base = None

                    if op.index is not None:
                        new_index = replacements[op.index]
                    else:
                        new_index = None

                    new_ops[k] = ctx.dedup_store.get(x86.MemoryOperand, width=op.width,
                            segment=op.segment,
                            base=new_base,
                            index=new_index,
                            scale=op.scale,
                            displacement=op.displacement,
                        )
                else:
                    new_ops[k] = op
            new_insns.append(ii.scheme.instantiate(new_ops))
        return ctx.make_bb(new_insns)


    bbs = []
    tps = []
    with open(args.benchmarks, 'r') as f:
        reader = csv.reader(f)
        for idx, row in enumerate(reader):
            if idx >= 10000:
                break
            bmk = row[0]
            if len(bmk) == 0:
                continue
            expected_tp = float(row[1]) / 100.0
            try:
                bbs.append(ctx.make_bb(ctx.decode_insns(bmk)))
                tps.append(expected_tp)
            except iwho.InstantiationError:
                continue

    # bb = bbs[0]
    # print("original:")
    # print(bb)
    #
    # print("replaced:")
    # print(replace(bb))
    #
    # sys.exit(0)

    def do_eval(bbs):
        pred_res = predman.eval_with_all(bbs)

        all_errors = []

        for (bb, eval_res), expected_tp in zip(pred_res, tps):
            pred_tp = eval_res[pred_key]['TP']
            if pred_tp is None or pred_tp <= 0.0:
                print("prediction failed for block '{}': {}".format("; ".join(map(str, bb.insns)), eval_res))
                continue
            rel_error = abs(pred_tp - expected_tp) / expected_tp
            all_errors.append(rel_error)

        if len(all_errors) == 0:
            print("All predictions failed!")
            sys.exit(1)

        mae = sum(all_errors) / len(all_errors)

        print("MAPE: {:.1f}%".format(mae*100))

    # print("original:")
    # do_eval(bbs)


    print("replaced:")
    do_eval([replace(bb) for bb in bbs])


if __name__ == "__main__":
    main()
