""" TODO document this
"""

from abc import ABC, abstractmethod
from collections import defaultdict
import itertools
import random
import textwrap
from typing import Optional, Union

import iwho

import logging
logger = logging.getLogger(__name__)


class AbstractFeature(ABC):
    @abstractmethod
    def is_bottom(self) -> bool:
        pass

    @abstractmethod
    def subsumes(self, other: "AbstractFeature") -> bool:
        pass

    @abstractmethod
    def subsumes_feature(self, feature) -> bool:
        pass

    @abstractmethod
    def join(self, feature):
        pass


class SingletonAbstractFeature(AbstractFeature):
    def __init__(self):
        self.is_top = False
        self.is_bot = True
        self.val = None

    def __str__(self) -> str:
        if self.is_top:
            return "TOP"
        if self.is_bot:
            return "BOT"
        return str(self.val)

    def is_bottom(self) -> bool:
        return self.is_bot

    def set_to_top(self):
        self.is_top = True
        self.is_bot = False
        self.val = None

    def subsumes(self, other: AbstractFeature) -> bool:
        assert isinstance(other, SingletonAbstractFeature)
        if self.is_top or other.is_bot:
            return True
        if self.is_bot or other.is_top:
            return False
        return self.val == other.val

    def subsumes_feature(self, feature) -> bool:
        if feature is None:
            return True
        if self.is_top:
            return True
        if self.is_bot:
            return False
        return self.val == feature

    def join(self, feature):
        if feature is None:
            return
        if self.is_top:
            return
        if self.is_bot:
            self.is_bot = False
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

    def __str__(self) -> str:
        return "{" + ", ".join(sorted(map(str, self.vals))) + "}"

    def is_bottom(self) -> bool:
        return len(self.vals) == 0

    def subsumes(self, other: AbstractFeature) -> bool:
        return self.vals.issuperset(other.vals)

    def subsumes_feature(self, feature) -> bool:
        if feature is None:
            return True
        return feature in self.vals

    def join(self, feature):
        if feature is not None:
            self.vals.add(feature)


class AbstractInsn:
    """ An instance of this class represents a set of (concrete) InsnInstances
    that share certain features.
    """

    def __init__(self, acfg: "AbstractionConfig"):
        self.acfg = acfg
        self.features = self.acfg.init_abstract_features()

    def __str__(self) -> str:
        return self.acfg.stringify_abstract_features(self.features)

    def subsumes(self, other: "AbstractInsn") -> bool:
        """ Check if all concrete instruction instances represented by other
        are also represented by self.
        """
        for k, abs_feature in self.features.items():
            other_feature = other.features[k]
            if not abs_feature.subsumes(other_feature):
                return False

        return True

    def join(self, insn_scheme: Union[iwho.InsnInstance, None]):
        """ Update self so that it additionally represents all instances of
        insn_scheme (and possibly, due to over-approximation, even more
        insn instances).

        If insn_scheme is None, the instruction is considered "not present" in
        the basic block.
        """

        insn_features = self.acfg.extract_features(insn_scheme)

        for k, v in insn_features.items():
            self.features[k].join(v)

    def sample(self, ctx: iwho.Context) -> iwho.InsnInstance:
        """ TODO document
        """

        if self.features['present'].val == False:
            return None

        if self.features['present'].is_top:
            if random.choice([True, False]):
                # TODO one might want to adjust the probabilities here...
                return None

        # Collect all insn schemes that match the AbstractInsn. If necessary,
        # this should probably be sped up using indices.
        feasible_schemes = []
        for ischeme in ctx.insn_schemes:
            ischeme_features = self.acfg.extract_features(ischeme)
            if all([v.subsumes_feature(ischeme_features.get(k)) for k, v in self.features.items()]):
                feasible_schemes.append(ischeme)
        if len(feasible_schemes) == 0:
            return None
        return random.choice(feasible_schemes)


class AbstractBlock:
    """ An instance of this class represents a set of (concrete) BasicBlocks
    (up to a fixed length maxlen).
    """

    def __init__(self, acfg: "AbstractionConfig", bb: Optional[iwho.BasicBlock]=None):
        self.acfg = acfg
        self.maxlen = acfg.max_block_len
        self.abs_insns = [ AbstractInsn(self.acfg) for i in range(self.maxlen) ]

        # operand j of instruction i aliases with operand y of instruction x
        self.abs_deps = defaultdict(SingletonAbstractFeature)

        if bb is not None:
            self.join(bb)

    def __str__(self) -> str:
        def format_insn(x):
            idx, abs_insn = x
            return "{:2}:\n{}".format(idx, textwrap.indent(str(abs_insn), '  '))

        # instruction part
        insn_part = "\n".join(map(format_insn, enumerate(self.abs_insns)))
        res = "AbstractInsns:\n" + textwrap.indent(insn_part, '  ')

        # dependency part
        entries = []
        for ((iidx1, oidx1), (iidx2,oidx2)), absval in self.abs_deps.items():
            if absval.is_top:
                valtxt = "TOP"
            elif absval.is_bot:
                valtxt = "BOTTOM"
            elif absval.val is False:
                valtxt = "must not alias"
            elif absval.val is True:
                valtxt = "must alias"
            else:
                assert False

            entries.append(f"{iidx1}:{oidx1} - {iidx2}:{oidx2} : {valtxt}")

        entries.sort()
        res += "\nAliasing:\n" + textwrap.indent("\n".join(entries), '  ')

        return res

    def subsumes(self, other: "AbstractBlock") -> bool:
        """ Check if all concrete basic blocks represented by other are also
        represented by self.

        other is expected to have the same maxlen as self.
        """
        # we expect compatible AbstractBlocks with the same number of abstract
        # insns (do note that abstract insns could have a "not present" state).
        assert self.maxlen == other.maxlen

        # check if all abstract insns are subsumed
        for self_ai, other_ai in zip(self.abs_insns, other.abs_insns):
            if not self_ai.subsumes(other_ai):
                return False

        #TODO dependencies
        return True

    def join(self, bb):
        """ Update self so that it additionally represents bb (and possibly,
        due to over-approximation, even more basic blocks).
        """
        assert self.maxlen >= len(bb.insns)

        len_diff = self.maxlen - len(bb.insns)

        bb_insns = list(bb.insns)

        for x in range(len_diff):
            bb_insns.append(None)

        assert(len(bb_insns) == len(self.abs_insns))

        for a, b in zip(self.abs_insns, bb_insns):
            scheme = None if b is None else b.scheme
            a.join(scheme)

        aliasing_partition = []
        idx2partition = dict()

        running_id = 0

        # collect the dependencies of bb
        for insn_idx, ii in enumerate(bb_insns):
            if ii is None:
                continue
            for operand, (op_idx, opscheme, key) in ii.indexable_operands():
                idx = (insn_idx, op_idx)
                for ks, vs, n in aliasing_partition:
                    if any(map(lambda x: self.acfg.must_alias(operand, x), ks)):
                        ks.add(operand)
                        vs.add(idx)
                        idx2partition[idx] = n
                        break
                else:
                    aliasing_partition.append(({operand}, {idx}, running_id))
                    idx2partition[idx] = running_id
                    running_id += 1

        for ks, vs, n in aliasing_partition:
            for idx1, idx2 in itertools.combinations(vs, 2): # are combinations enough here?
                self.abs_deps[(idx1, idx2)].join(True)

        # TODO use may-alias or must-not-alias info?

        # for (idx1, idx2), val in self.abs_deps.items():
        #     pid1 = idx2partition.get(idx1, None)
        #     pid2 = idx2partition.get(idx2, None)
        #     if pid1 is None or pid2 is None:
        #         val.set_to_top() # TODO we could also just remove it
        #     if pid1 == pid2:
        #         val.join(True)
        #     else:
        #         val.join(False)


    def sample(self, ctx: iwho.Context) -> iwho.BasicBlock:
        """ Randomly sample a basic block that is represented by self.
        """
        insn_schemes = []
        for ai in self.abs_insns:
            insn_scheme = ai.sample(ctx) # may be None
            insn_schemes.append(insn_scheme)

        # for (insn_op1, insn_op2), should_alias in self.abs_deps.items():
        #     if should_alias:
        #         same[insn_op1].add(insn_op2)
        #         same[insn_op2].add(insn_op1)
        #     else:
        #         not_same[insn_op1].add(insn_op2)
        #         not_same[insn_op2].add(insn_op1)
        #
        # chosen_operands = dict()

        # TODO dependencies
        # go through all insn_schemes and pin each fixed operand
        # go through all operands for all insns and check if one from its "same" set has a chosen operand.
        #   if yes: take the same (with adjusted width). if it is also chosen in the not_same set, fail
        #   if no: choose one that is not chosen in its not_same set
        from iwho.x86 import DefaultInstantiator
        instor = DefaultInstantiator(ctx)

        bb = iwho.BasicBlock(ctx)
        for scheme in insn_schemes:
            instance = None if scheme is None else instor(scheme)
            bb.append(instance)

        return bb


class AbstractionConfig:
    """ Configuration Class for AbstractBlock and subcomponents

    This encapsulates several configuration options like which features of the
    instructions to use for abstraction and how they are abstracted.
    """

    def __init__(self, ctx: iwho.Context, max_block_len):
        self.ctx = ctx

        self.feature_keys = ['exact_scheme', 'present', 'mnemonic', 'skl_uops']

        self.max_block_len = max_block_len

    def must_alias(self, op1: iwho.OperandInstance, op2: iwho.OperandInstance):
        # TODO this could use additional information about the instantiation
        # (in contrast to the iwho.Context method, which should be correct for
        # all uses)
        return self.ctx.must_alias(op1, op2)

    def init_abstract_features(self):
        res = dict()
        res['exact_scheme'] = SingletonAbstractFeature()
        res['present'] = SingletonAbstractFeature()
        res['mnemonic'] = SingletonAbstractFeature()
        res['skl_uops'] = PowerSetAbstractFeature()
        return res

    def extract_features(self, ischeme: Union[iwho.InsnScheme, None]):
        if ischeme is None:
            return {'present': False}
        res = {'present': True}
        res['exact_scheme'] = ischeme
        res['mnemonic'] = self.ctx.extract_mnemonic(ischeme)
        res['skl_uops'] = None

        from_scheme = self.ctx.get_features(ischeme)
        if from_scheme is not None:
            res['skl_uops'] = from_scheme[0].get("SKL")

        return res

    def stringify_abstract_features(self, afeatures):
        return "\n".join((f"{k}: {afeatures[k]}" for k in self.feature_keys))

