""" TODO document this
"""

from abc import ABC, abstractmethod
import random
from typing import Optional

import iwho

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
        for ischeme in ctx.insn_schemes:
            # ischeme_features = ctx.get_features(ischeme)
            ischeme_features = {'exact_scheme': str(ischeme)}
            if all([v.subsumes(ischeme_features[k]) for k, v in self.features.items()]):
                feasible_schemes.append(ischeme)
        if len(feasible_schemes) == 0:
            return None
        return random.choice(feasible_schemes)

    def join(self, insn_scheme):

        insn_features = dict()
        # insn_features = ctx.get_features(insn_scheme)
        insn_features['exact_scheme'] = insn_scheme
        for k, v in self.features.items():
            v.join(insn_features[k])


class AbstractBlock:

    def __init__(self, bb: Optional[iwho.BasicBlock]=None):
        self.abs_insns = []

        # operand j of instruction i aliases with operand y of instruction x
        self.abs_deps = dict()

        if bb is not None:
            self.join(bb)

    def sample(self, ctx):
        insn_schemes = []
        for ai in self.abs_insns:
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

        bb = iwho.BasicBlock(ctx)
        return bb

    def join(self, bb):
        len_diff = len(self.abs_insns) - len(bb)

        bb_insns = list(bb)

        if len_diff > 0:
            for x in range(len_diff):
                bb_insns.append(None)
        elif len_diff < 0:
            for x in range(-len_diff):
                self.abs_insns.append(AbstractInsn())

        assert(len(bb_insns) == len(self.abs_insns))

        for a, b in zip(self.abs_insns, bb_insns):
            a.join(b.scheme)
        # TODO dependencies


