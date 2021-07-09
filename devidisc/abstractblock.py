""" This file provides classes to represent abstractions of basic blocks, i.e.
representations of sets of 'conrete' basic blocks.

Those abstractions have methods to sample from the represented concrete blocks,
as well as ways to systematically extend the set of represented concrete
blocks.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from copy import deepcopy, copy
from enum import Enum
import itertools
import random
import textwrap
from typing import Optional, Union

import iwho

import logging
logger = logging.getLogger(__name__)


class SamplingError(Exception):
    """ Something went wrong with sampling
    """

    def __init__(self, message):
        super().__init__(message)

# TODO document json funcitonality, mention that acfg.introduce_json_references
# and acfg.resolve_json_references should be used

class Expandable(ABC):
    """TODO document"""
    @abstractmethod
    def get_possible_expansions(self):
        """ Return a list of possible expansions for `apply_expansion()`.

        The list contains tuples of an expansion and a value that corresponds
        to its estimated benefit in the amount of freedom that it would give
        the sampling.
        """

        pass

    @abstractmethod
    def apply_expansion(self, expansion):
        """ Apply an expansion from `get_possible_expansions()`. """
        pass

class AbstractFeature(Expandable, ABC):
    """ TODO document
    """
    class SpecialValue(Enum):
        BOTTOM=0
        TOP=1

        def __str__(self):
            return str(self.name)

    BOTTOM = SpecialValue.BOTTOM
    TOP = SpecialValue.TOP

    @abstractmethod
    def __deepcopy__(self, memo):
        pass

    @abstractmethod
    def to_json_dict(self):
        pass

    @abstractmethod
    def is_top(self) -> bool:
        pass

    @abstractmethod
    def is_bottom(self) -> bool:
        pass

    @abstractmethod
    def set_to_top(self):
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
        self.val = AbstractFeature.BOTTOM

    def __deepcopy__(self, memo):
        new_one = SingletonAbstractFeature()
        new_one.val = self.val # no need to copy at all
        return new_one

    def to_json_dict(self):
        return self.val

    @staticmethod
    def from_json_dict(json_dict):
        res = SingletonAbstractFeature()
        res.val = json_dict
        return res

    def __str__(self) -> str:
        return str(self.val)

    def get_possible_expansions(self):
        if self.is_top():
            return []
        return [(AbstractFeature.TOP, 1)]

    def apply_expansion(self, expansion):
        self.val = expansion

    def is_top(self) -> bool:
        return self.val == AbstractFeature.TOP

    def is_bottom(self) -> bool:
        return self.val == AbstractFeature.BOTTOM

    def get_val(self):
        if isinstance(self.val, AbstractFeature.SpecialValue):
            return None
        else:
            return self.val

    def set_to_top(self):
        self.val = AbstractFeature.TOP

    def subsumes(self, other: AbstractFeature) -> bool:
        assert isinstance(other, SingletonAbstractFeature)
        return (self.val == other.val or
                other.val == AbstractFeature.BOTTOM or
                self.val == AbstractFeature.TOP)

    def subsumes_feature(self, feature) -> bool:
        if feature is None:
            return True
        if self.is_top():
            return True
        if self.is_bottom():
            return False
        return self.val == feature

    def join(self, feature):
        if feature is None:
            return
        if self.is_top():
            return
        if self.is_bottom():
            self.val = feature
            return
        if self.val != feature:
            self.set_to_top()
        return


class SubSetAbstractFeature(AbstractFeature):
    """ Represents all sets of items that are a (non-strict) superset of
    self.val.
    """
    def __init__(self):
        self.val = AbstractFeature.BOTTOM

    def __deepcopy__(self, memo):
        new_one = SubSetAbstractFeature()
        new_one.val = copy(self.val) # no need to deepcopy
        return new_one

    def to_json_dict(self):
        if self.is_bottom():
            return self.val
        return tuple(self.val)

    @staticmethod
    def from_json_dict(json_dict):
        res = SubSetAbstractFeature()
        if isinstance(json_dict, AbstractFeature.SpecialValue):
            res.val = json_dict
        else:
            assert isinstance(json_dict, list) or isinstance(json_dict, tuple)
            res.val = set(json_dict)
        return res

    def get_possible_expansions(self):
        if self.is_top():
            return []
        if self.is_bottom():
            return [(AbstractFeature.TOP, 1)]
        res = []
        for v in self.val:
            res.append((v, 1))
        return res

    def apply_expansion(self, expansion):
        if expansion == AbstractFeature.TOP:
            self.set_to_top()
            return
        self.val.remove(expansion)

    def __str__(self) -> str:
        if self.is_bottom():
            return "BOTTOM"
        if self.is_top():
            return "TOP"
        return "{" + ", ".join(sorted(map(str, self.val))) + "}"

    def is_top(self) -> bool:
        return (not self.is_bottom()) and len(self.val) == 0

    def is_bottom(self) -> bool:
        return self.val == AbstractFeature.BOTTOM

    def set_to_top(self):
        self.val = set()

    def subsumes(self, other: AbstractFeature) -> bool:
        assert isinstance(other, SubSetAbstractFeature)
        if other.is_bottom():
            return True
        if self.is_bottom():
            return False
        return self.val.issubset(other.val)

    def subsumes_feature(self, feature) -> bool:
        if feature is None:
            return True
        if self.is_bottom():
            return False
        return self.val.issubset(set(feature))

    def join(self, feature):
        if feature is not None:
            if self.is_bottom():
                self.val = set(feature)
            else:
                self.val.intersection_update(feature)


class AbstractInsn(Expandable):
    """ An instance of this class represents a set of (concrete) InsnSchemes
    that share certain features.
    """

    def __init__(self, acfg: "AbstractionConfig"):
        self.acfg = acfg
        self.features = self.acfg.init_abstract_features()

    def __deepcopy__(self, memo):
        new_one = AbstractInsn(self.acfg)
        new_one.features = deepcopy(self.features, memo)
        return new_one

    def to_json_dict(self):
        res = dict()
        for k, v in self.features.items():
            res[k] = v.to_json_dict()
        return res

    @staticmethod
    def from_json_dict(acfg, json_dict):
        res = AbstractInsn(acfg)
        init_features = res.features
        assert set(init_features.keys()) == set(json_dict.keys())
        json_features = dict()
        for k, v in json_dict.items():
            cls = type(init_features[k])
            json_features[k] = cls.from_json_dict(v)
        res.features = json_features
        return res

    def __str__(self) -> str:
        if all(map(lambda x: (x[0] == 'present' and x[1].val == False) or x[1].is_bottom(), self.features.items())):
            return "not present"
        if all(map(lambda x: x[1].is_top(), self.features.items())):
            return "TOP"
        return "\n".join((f"{k}: {v}" for k, v in self.features.items()))

    def compute_benefit(self, expansion):
        if expansion == 'all_top':
            # One could argue that this benefit should actually be large.
            # However, adding new instructions into the mix is not really
            # helpful for our purpose, so we give it low priority.
            return 0

        absfeature_dict = { k: v for k, v in self.features.items() }

        replace_k, inner_expansion = expansion
        replace_feature = deepcopy(self.features[replace_k])
        replace_feature.apply_expansion(inner_expansion)
        absfeature_dict[replace_k] = replace_feature

        feasible_schemes = self.acfg.compute_feasible_schemes(absfeature_dict)
        return len(feasible_schemes)


    def get_possible_expansions(self):
        if self.features['present'].val == False:
            expansion = 'all_top'
            return [(expansion, self.compute_benefit(expansion))]

        if not self.features['exact_scheme'].is_top():
            # The exact scheme is more specific than the other features (it
            # implies all of them). It is therefore pointless and harmful to
            # expand another feature first, as it will not affect the sampling
            # at all, but might very well lead to a situation where expanding
            # the scheme later on will no longer be allowed.
            # An alternative, more general way of dealing with this (also for
            # other co-dependent features) would be to join the original with
            # the sampled experiments rather than using the expanded abstract
            # block, or to make sure that blocks not covered by the original
            # block are sampled.
            expansion = ('exact_scheme', AbstractFeature.TOP)
            benefit = self.compute_benefit(expansion)
            return [(expansion, benefit)]

        res = []
        for key, af in self.features.items():
            for inner_expansion, benefit in af.get_possible_expansions():
                expansion = (key, inner_expansion)
                benefit = self.compute_benefit(expansion)
                res.append((expansion, benefit))
        return res

    def apply_expansion(self, expansion):
        if expansion == 'all_top':
            for k, v in self.features.items():
                v.set_to_top()
            return
        key, inner_expansion = expansion
        self.features[key].apply_expansion(inner_expansion)

    def subsumes(self, other: "AbstractInsn") -> bool:
        """ Check if all concrete instruction instances represented by other
        are also represented by self.
        """
        for k, abs_feature in self.features.items():
            other_feature = other.features[k]
            if not abs_feature.subsumes(other_feature):
                return False

        return True

    def join(self, insn_scheme: Union[iwho.InsnScheme, None]):
        """ Update self so that it additionally represents all instances of
        insn_scheme (and possibly, due to over-approximation, even more
        insn instances).

        If insn_scheme is None, the instruction is considered "not present" in
        the basic block.
        """

        insn_features = self.acfg.extract_features(insn_scheme)

        for k, v in insn_features.items():
            self.features[k].join(v)

    def sample(self) -> iwho.InsnScheme:
        """ Randomly choose one from the set of concrete instruction schemes
        represented by this abstract instruction.
        """
        if self.features['present'].val == False:
            return None

        if self.features['present'].is_top():
            if random.choice([True, False]):
                # TODO one might want to adjust the probabilities here...
                return None

        feasible_schemes = self.acfg.compute_feasible_schemes(self.features)

        if len(feasible_schemes) == 0:
            raise SamplingError(f"No InsnScheme is feasible for AbstractInsn {self}")
        return random.choice(feasible_schemes)


def _lists2tuples(obj):
    if isinstance(obj, list) or isinstance(obj, tuple):
        return tuple(( _lists2tuples(x) for x in obj ))
    return obj

class AbstractBlock(Expandable):
    """ An instance of this class represents a set of (concrete) BasicBlocks
    (up to a fixed length maxlen).
    """

    def __init__(self, acfg: "AbstractionConfig", bb: Optional[iwho.BasicBlock]=None):
        self.acfg = acfg
        self.maxlen = acfg.max_block_len
        self.abs_insns = [ AbstractInsn(self.acfg) for i in range(self.maxlen) ]

        self._abs_aliasing = dict()
        # A mapping from pairs of (instruction index, operand index) pairs to a
        # boolean SingletonAbstractFeature.
        # An entry for (op1, op2) means "if op1 and op2 allow for aliasing,
        # then {they alias, they don't alias, anything goes}.
        #
        # The semantics of entries not present in the above map changes over
        # the lifetime of the AbstractBlock, through the value of the following
        # flag. In the beginning, before any concrete Block is joined in,
        # nothing will be present, which should be interpreted as a BOTTOM
        # value for everything. When joining the first concrete Block in, the
        # map gets entries for all the observed relationships, and any
        # non-present relationship that might be encountered later should be
        # considered TOP.
        self.is_bot = True

        if bb is not None:
            self.join(bb)

    def to_json_dict(self):
        res = dict()
        res['abs_insns'] = [ ai.to_json_dict() for ai in self.abs_insns ]
        res['abs_aliasing'] = [ (k, x.to_json_dict()) for k, x in self._abs_aliasing.items() ]
        res['is_bot'] = self.is_bot
        return res

    @staticmethod
    def from_json_dict(acfg, json_dict):
        res = AbstractBlock(acfg)
        res.abs_insns = []
        for sub_dict in json_dict['abs_insns']:
            res.abs_insns.append(AbstractInsn.from_json_dict(acfg, sub_dict))
        aliasing = dict()
        for k, v in json_dict['abs_aliasing']:
            key = _lists2tuples(k)
            aliasing[key] = SingletonAbstractFeature.from_json_dict(v)
        res._abs_aliasing = aliasing
        res.is_bot = json_dict['is_bot']
        return res

    def __deepcopy__(self, memo):
        new_one = AbstractBlock(self.acfg)
        new_one.maxlen = self.maxlen
        new_one.abs_insns = deepcopy(self.abs_insns, memo)
        new_one._abs_aliasing = { k: deepcopy(v, memo) for k, v in self._abs_aliasing.items() } # no need to duplicate the keys here
        new_one.is_bot = self.is_bot
        return new_one

    def get_possible_expansions(self):
        res = []

        for ai_idx, ai in enumerate(self.abs_insns):
            for inner_expansion, benefit in ai.get_possible_expansions():
                expansion = (0, ai_idx, inner_expansion)
                res.append((expansion, benefit))

        for key, av in self._abs_aliasing.items():
            for inner_expansion, benefit in av.get_possible_expansions():
                expansion = (1, key, inner_expansion)
                res.append((expansion, benefit))

        return res

    def apply_expansion(self, expansion):
        component, key, inner_expansion = expansion
        if component == 0: # Insn component
            ai = self.abs_insns[key]
            ai.apply_expansion(inner_expansion)
        else: # Aliasing component
            assert component == 1
            av = self._abs_aliasing[key]
            av.apply_expansion(inner_expansion)

    def get_abs_aliasing(self, idx1, idx2):
        """ TODO document
        """
        key = tuple(sorted((idx1, idx2)))
        res = self._abs_aliasing.get(key, None)
        if res is None and self.is_bot:
            res = SingletonAbstractFeature()
            self._abs_aliasing[key] = res
        return res

    def __str__(self) -> str:
        def format_insn(x):
            idx, abs_insn = x
            return "{:2}:\n{}".format(idx, textwrap.indent(str(abs_insn), '  '))

        # instruction part
        insn_part = "\n".join(map(format_insn, enumerate(self.abs_insns)))
        res = "AbstractInsns:\n" + textwrap.indent(insn_part, '  ')

        # dependency part
        entries = []
        for ((iidx1, oidx1), (iidx2,oidx2)), absval in self._abs_aliasing.items():
            if absval.is_top():
                continue
            elif absval.is_bottom():
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

        # aliasing
        if other.is_bot:
            return True

        if self.is_bot:
            return False

        # all items not present are considered TOP and subsume everything
        for k, sv in self._abs_aliasing.items():
            if sv.is_top():
                continue
            ov = other._abs_aliasing.get(k, None)
            if ov is None or not sv.subsumes(ov):
                return False

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

        all_indices = []
        for insn_idx, ii in enumerate(bb_insns):
            if ii is None:
                continue
            for operand, (op_key, op_scheme) in ii.get_operands():
                if self.acfg.skip_for_aliasing(op_scheme):
                    continue
                idx = (insn_idx, op_key)
                all_indices.append((idx, operand))

        for (idx1, op1), (idx2, op2) in itertools.combinations(all_indices, 2):
            ad = self.get_abs_aliasing(idx1, idx2)
            if ad is None or ad.is_top():
                continue

            # if operand schemes are not compatible, this entry is ignored
            op_scheme1 = bb_insns[idx1[0]].scheme.get_operand_scheme(idx1[1])
            op_scheme2 = bb_insns[idx2[0]].scheme.get_operand_scheme(idx2[1])
            if not self.acfg.is_compatible(op_scheme1, op_scheme2):
                if ad.is_bottom():
                    # This is to avoid bottom entries for incompatible operand
                    # combinations when initializing. Those would not be
                    # unsound, but they are pointless and cause work.
                    ad.set_to_top()
                continue

            if self.acfg.must_alias(op1, op2):
                ad.join(True)
            elif not self.acfg.may_alias(op1, op2):
                ad.join(False)
            else:
                ad.set_to_top()

        # if this is the first join, this switches the interpretation of
        # non-present entries in the abs_aliasing dict.
        self.is_bot = False


    def sample(self) -> iwho.BasicBlock:
        """ Randomly sample a basic block that is represented by self.
        """
        ctx = self.acfg.ctx

        insn_schemes = []
        for ai in self.abs_insns:
            insn_scheme = ai.sample() # may be None
            insn_schemes.append(insn_scheme)

        # aliasing/operands
        if self.is_bot:
            return None

        same = defaultdict(set) # a mapping from instruction operands to sets of instruction operands with which they should alias
        not_same = defaultdict(set) # a mapping from instruction operands to sets of instruction operands with which they should not alias

        for (insn_op1, insn_op2), should_alias in self._abs_aliasing.items():
            iidx1, op_key1 = insn_op1
            iidx2, op_key2 = insn_op2
            # Do not enter information for instructions and operands that are
            # not present.
            if insn_schemes[iidx1] is None or insn_schemes[iidx2] is None:
                continue
            op_scheme1 = insn_schemes[iidx1].get_operand_scheme(op_key1)
            op_scheme2 = insn_schemes[iidx2].get_operand_scheme(op_key2)
            if (op_scheme1 is None or op_scheme2 is None):
                continue

            # if operand schemes are not compatible, this entry is ignored
            if not self.acfg.is_compatible(op_scheme1, op_scheme2):
                continue

            if should_alias.val is True:
                same[insn_op1].add(insn_op2)
                same[insn_op2].add(insn_op1)
            elif should_alias.val is False:
                not_same[insn_op1].add(insn_op2)
                not_same[insn_op2].add(insn_op1)

        chosen_operands = dict()

        # go through all insn_schemes and pin each fixed operand
        for iidx, ischeme in enumerate(insn_schemes):
            if ischeme is None:
                continue
            for op_key, op_scheme in ischeme.operand_keys:
                if self.acfg.skip_for_aliasing(op_scheme):
                    continue
                idx = (iidx, op_key)
                if op_scheme.is_fixed():
                    fixed_op = op_scheme.fixed_operand
                    prev_choice = chosen_operands.get(idx, None)
                    if prev_choice is not None and prev_choice != fixed_op:
                        raise SamplingError(f"InsnScheme {ischeme} requires different operands for {op_key} from aliasing with fixed operands: {prev_choice} and {fixed_op}")
                    chosen_operands[idx] = fixed_op
                    for k in same[idx]:
                        prev_choice = chosen_operands.get(k, None)
                        adjusted_fixed_op = ctx.adjust_operand(fixed_op, insn_schemes[k[0]].get_operand_scheme(k[1]))
                        if adjusted_fixed_op is None:
                            raise SamplingError(f"InsnScheme {insn_schemes[k[0]]} requires an incompatible operand for {k[1]} from aliasing with a fixed operand: {fixed_op}")
                        if prev_choice is not None and prev_choice != adjusted_fixed_op:
                            raise SamplingError(f"InsnScheme {insn_schemes[k[0]]} requires different operands for {k[1]} from aliasing with fixed operands: {prev_choice} and {adjusted_fixed_op}")
                        chosen_operands[k] = adjusted_fixed_op

        # remaining unchosen operands are not determined by fixed operands
        # in here, backtracking would be necessary
        for iidx, ischeme in enumerate(insn_schemes):
            if ischeme is None:
                continue
            for op_key, op_scheme in ischeme.operand_keys:
                idx = (iidx, op_key)
                if chosen_operands.get(idx, None) is not None:
                    continue
                # choose an operand that is not already taken in the not_same
                # set
                allowed_operands = set(self.acfg.allowed_operands(op_scheme))
                if not self.acfg.skip_for_aliasing(op_scheme):
                    for k in not_same[idx]:
                        disallowed = chosen_operands.get(k, None)
                        if disallowed is not None:
                            disallowed = ctx.adjust_operand(disallowed, op_scheme)
                            if disallowed is not None:
                                try:
                                    allowed_operands.remove(disallowed)
                                except KeyError as e:
                                    pass
                chosen = random.choice(list(allowed_operands))
                chosen_operands[idx] = chosen
                for k in same[idx]:
                    chosen_operand = ctx.adjust_operand(chosen, insn_schemes[k[0]].get_operand_scheme(k[1]))
                    if chosen_operand is None:
                        raise SamplingError(f"InsnScheme {insn_schemes[k[0]]} requires incompatible operand for {k[1]}: {chosen}")
                    chosen_operands[k] = chosen_operand

        op_maps = defaultdict(dict)
        for (iidx, op_key), chosen_operand in chosen_operands.items():
            op_maps[iidx][op_key] = chosen_operand

        # instantiate the schemes with the chosen operands
        bb = iwho.BasicBlock(ctx)
        for iidx, ischeme in enumerate(insn_schemes):
            if ischeme is None:
                bb.append(None)
                continue
            op_map = op_maps[iidx]
            try:
                instance = ischeme.instantiate(op_map)
            except iwho.InstantiationError as e:
                msg = "Failed to sample abstract block:\n" + textwrap.indent(str(self), '  ')
                msg += "\n"
                msg += "chosen InsnSchemes:\n" + "\n".join(map(str, insn_schemes))
                raise SamplingError(msg) from e

            bb.append(instance)

        return bb

