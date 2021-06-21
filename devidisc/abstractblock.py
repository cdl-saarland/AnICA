""" TODO document this
"""

from abc import ABC, abstractmethod
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

    def subsumes(self, other: AbstractFeature) -> bool:
        assert isinstance(other, SingletonAbstractFeature)
        if self.is_top or other.is_bot:
            return True
        if self.is_bot or other.is_top:
            return False
        return self.val == feature

    def subsumes_feature(self, feature) -> bool:
        if self.is_top:
            return True
        if self.is_bot:
            return False
        return self.val == feature

    def join(self, feature):
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
        return feature in self.vals

    def join(self, feature):
        self.vals.add(feature)


class AbstractInsn:
    """ An instance of this class represents a set of (concrete) InsnInstances
    that share certain features.
    """

    def __init__(self):
        self.features = dict()
        self.features['exact_scheme'] = SingletonAbstractFeature()
        self.features['present'] = SingletonAbstractFeature()
        # features not in the dict are considered bottom
        # TODO this decision might lead to inconsistencies

        # TODO add more features here?

    def __str__(self) -> str:
        special_keys = ['exact_scheme', 'present']
        keys = set(self.features.keys())
        keys.difference_update(special_keys)
        order = special_keys + sorted(keys)
        return "\n".join((f"{k}: {self.features[k]}" for k in order))

    def subsumes(self, other: "AbstractInsn") -> bool:
        """ Check if all concrete instruction instances represented by other
        are also represented by self.

        That is the case if
            (1) all features present in self are not present in other or
                subsume the abstract feature present in other and
            (2) all features from other that are not present in self are bottom.
        """
        for k, abs_feature in self.features.items():
            other_feature = other.features.get(abs_feature, None)
            if other_feature is None:
                continue
            if not abs_feature.subsumes(other_feture):
                return False

        for k, other_feature in other.features.items():
            if (not other_feature.is_bottom()) and k not in self.features.keys():
                return False

        return True

    def join(self, insn_scheme: Union[iwho.InsnInstance, None]):
        """ Update self so that it additionally represents all instances of
        insn_scheme (and possibly, due to over-approximation, even more
        insn instances).

        If insn_scheme is None, the instruction is considered "not present" in
        the basic block.
        """

        if insn_scheme is None:
            self.features['present'].join(False)
            return

        insn_features = dict()
        # TODO get other features insn_features = ctx.get_features(insn_scheme)
        insn_features['exact_scheme'] = insn_scheme
        insn_features['present'] = True
        for k, v in self.features.items():
            v.join(insn_features[k])

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
            # ischeme_features = ctx.get_features(ischeme)
            ischeme_features = {'exact_scheme': ischeme, 'present': True}
            if all([v.subsumes_feature(ischeme_features[k]) for k, v in self.features.items()]):
                feasible_schemes.append(ischeme)
        if len(feasible_schemes) == 0:
            return None
        return random.choice(feasible_schemes)


class AbstractBlock:
    """ An instance of this class represents a set of (concrete) BasicBlocks
    (up to a fixed length maxlen).
    """

    def __init__(self, maxlen: int, bb: Optional[iwho.BasicBlock]=None):
        self.abs_insns = [ AbstractInsn() for i in range(maxlen) ]
        self.maxlen = maxlen

        # operand j of instruction i aliases with operand y of instruction x
        self.abs_deps = dict()

        if bb is not None:
            self.join(bb)

    def __str__(self) -> str:
        def format_insn(x):
            idx, abs_insn = x
            return "{:2}:\n{}".format(idx, textwrap.indent(str(abs_insn), '  '))

        insn_part = "\n".join(map(format_insn, enumerate(self.abs_insns)))
        res = "AbstractInsns:\n" + textwrap.indent(insn_part, '  ')
        # TODO dependency part
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
        # TODO dependencies

    def sample(self, ctx: iwho.Context) -> iwho.BasicBlock:
        """ Randomly sample a basic block that is represented by self.
        """
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

