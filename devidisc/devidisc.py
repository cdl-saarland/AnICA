#!/usr/bin/env python3

"""DeviDisc: the deviation discovery tool for basic block throughput predictors.
"""

from abc import ABC, abstractmethod
import argparse
from collections import defaultdict
from functools import partial
import json
import multiprocessing
from multiprocessing import Pool
import random
import textwrap
from timeit import default_timer as timer

import iwho
from iwho.predictors import Predictor
from iwho.utils import parse_args_with_logging
import iwho.x86 as x86


import logging
logger = logging.getLogger(__name__)


class AbstractFeature(ABC):
    @abstractmethod
    def subsumes(self, feature):
        pass

    @abstractmethod
    def join(self, feature):
        pass


class SingletonAbstractFeature(AbstractFeature):
    def __init__(self):
        self.is_top = False
        self.is_bottom = True
        self.val = None

    def subsumes(self, feature):
        if self.is_top:
            return True
        if self.is_bottom:
            return False
        return self.val == feature

    def join(self, feature):
        if self.is_top:
            return
        if self.is_bottom:
            self.is_bottom = False
            self.val = feature
            return
        if self.val != feature:
            self.val = None
            self.is_top = True
            return
        return


class PowerSetAbstractFeature(AbstractFeature):
    def __init__(self):
        self.vals = set()

    def subsumes(self, feature):
        return feature in self.vals

    def join(self, feature):
        self.vals.add(feature)


class AbstractInsn:
    def __init__(self):
        self.features = dict()
        self.features['exact_scheme'] = SingletonAbstractFeature()
        # TODO add more features here?
        # TODO add a "present" feature?

    def sample(self, ctx):
        feasible_schemes = []
        for ai in ctx.insn_schemes:
            if all([v.subsumes(ai.features[k]) for k, v in self.features.items()]):
                feasible_schemes.append()
        if len(feasible_schemes) == 0:
            return None
        return random.choice(feasible_schemes)

    def join(self, insn_scheme):
        insn_features = dict(insn_scheme.features)
        insn_features['exact_scheme'] = insn_scheme
        for k, v in self.features.items():
            v.join(insn_features[k])


class AbstractBlock:

    def __init__(self):
        self.abs_insns = []
        self.abs_deps = dict()
        # operand j of instruction i aliases with operand y of instruction x

    def sample(self, ctx):
        insn_schemes = []
        for ai in abs_insns:
            insn_scheme = ai.sample(ctx) # may be None
            insn_schemes.append(insn_scheme)

        for (insn_op1, insn_op2), should_alias in self.abs_deps.items():
            if should_alias:
                same[insn_op1].add(insn_op2)
                same[insn_op2].add(insn_op1)
            else:
                not_same[insn_op1].add(insn_op2)
                not_same[insn_op2].add(insn_op1)

        chosen_operands = dict()

        # go through all insn_schemes and pin each fixed operand
        # go through all operands for all insns and check if one from its "same" set has a chosen operand.
        #   if yes: take the same (with adjusted width). if it is also chosen in the not_same set, fail
        #   if no: choose one that is not chosen in its not_same set

        bb = iwho.BasicBlock()
        return bb

    def join(self, bb):
        len_diff = len(self.abs_insn) - len(bb)

        bb_insns = list(bb)

        if len_diff > 0:
            for x in range(len_diff):
                bb_insns.append(None)
        elif len_diff > 0:
            for x in range(-len_diff):
                self.abs_insns.append(AbstractInsn())

        assert(len(bb_insns) == len(self.abs_insns))

        for a, b in zip(self.abs_insns, bb_insns):
            a.join(b.scheme)
        # TODO dependencies


def evaluate_bb(bb, pred):
    try:
        result = pred.evaluate(bb, disable_logging=True)
    except Exception as e:
        result = "an exception occured: " + str(e)
    return result


class LightBBWrapper:
    """ Light-weight wrapper of all things necessary to get the hex
    representation of a BasicBlock.

    The key is the execution time distribution:
    Creating this wrapper is fast, serializing it is efficient (since nothing
    unnecessary from the iwho context is present), and `get_hex()` does the
    heavy lifting (i.e. calls to the coder, which might require expensive
    subprocesses).

    This makes this very effective to use as a task for a PredictorManager,
    since all expensive things can be done by the process pool.

    This could be considered a hack.
    """
    def __init__(self, bb):
        self.asm_str = bb.get_asm()
        self.coder = bb.context.coder

    def get_hex(self):
        return self.coder.asm2hex(self.asm_str)

    def get_asm(self):
        return self.asm_str


class PredictorManager:
    def __init__(self, num_threads=None):
        if num_threads is None:
            num_threads = multiprocessing.cpu_count()
        self.pool = Pool(num_threads)

    def do(self, pred, bbs, lazy=True):
        """ Use the given predictor to predict inverse throughputs for all
        basic blocks in the given list.

        If lazy is true, return an asynchronous iterator for the results and
        return before they are all predicted.
        If lazy is false, return a complete list of predictions (awaiting all
        results).
        """
        tasks = map(lambda x: LightBBWrapper(x), bbs)
        results = self.pool.imap(partial(evaluate_bb, pred=pred), tasks)
        if not lazy:
            results = list(results)
        return results


def main():
    argparser = argparse.ArgumentParser(description=__doc__)
    # argparser.add_argument('infile', metavar="CSVFILE", help='')
    args = parse_args_with_logging(argparser, "info")

    num_experiments = 1000
    max_num_insns = 10
    random.seed(424242)


    # get a list of throughput predictors
    predictors = []

    iaca_config = {
            "kind": "iaca",
            "iaca_path": "/opt/iaca/iaca",
            "iaca_opts": ["-arch", "SKL"]
        }
    predictors.append(Predictor.get(iaca_config))

    llvmmca_config = {
            "kind": "llvmmca",
            "llvmmca_path": "/home/ritter/projects/portmapping/llvm/install/bin/llvm-mca",
            "llvmmca_opts": ["-mcpu", "skylake"]
        }
    predictors.append(Predictor.get(llvmmca_config))


    # get an iwho context with appropriate schemes
    ctx = iwho.get_context("x86")
    schemes = ctx.insn_schemes
    schemes = list(filter(lambda x: not x.affects_control_flow, schemes))

    instor = x86.RandomRegisterInstantiator(ctx)

    # sample basic blocks and run them through the predictors
    start = timer()
    bbs = []
    for x in range(num_experiments):
        num_insns = random.randrange(2, max_num_insns + 1)
        bb = ctx.make_bb()
        for n in range(num_insns):
            ischeme = random.choice(schemes)
            bb.append(instor(ischeme))
        bbs.append(bb)

    predman = PredictorManager(16)

    end = timer()
    diff = end - start
    print(f"generated {len(bbs)} blocks in {diff:.2f} seconds")

    results = dict()
    for p in predictors:
        pred_name = p.predictor_name
        start = timer()
        results[pred_name] = predman.do(p, bbs)
        end = timer()
        diff = end - start
        print(f"started all {pred_name} jobs in {diff:.2f} seconds")

    with open("results.json", "w") as f:
        total_tool_time = defaultdict(lambda: 0.0)
        print("[", file=f)

        start = timer()

        keys = results.keys()
        for x, (rs, bb) in enumerate(zip(zip( *(results[k] for k in keys )), bbs)):
            predictions = dict()
            for y, k in enumerate(keys):
                res = rs[y]
                predictions[k] = res
                total_tool_time[k] += res['rt']

            record = {
                    "exp_idx": x,
                    "bb": str(bb),
                    "results": predictions
                }

            print(json.dumps(record) + ",", file=f)

        end = timer()
        diff = end - start

        print("]", file=f)

        print(f"evaluation done in {diff:.2f} seconds")
        for k, v in total_tool_time.items():
            print(f"total time spent in {k}: {v:.2f} seconds")


if __name__ == "__main__":
    main()
