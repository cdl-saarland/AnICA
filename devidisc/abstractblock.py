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


class AbstractFeature(ABC):
    class SpecialValues(Enum):
        BOTTOM=0
        TOP=1

        def __str__(self):
            return str(self.name)

    BOTTOM = SpecialValues.BOTTOM
    TOP = SpecialValues.TOP

    @abstractmethod
    def __deepcopy__(self, memo):
        pass

    @abstractmethod
    def to_json_dict(self):
        pass

    @abstractmethod
    def expand(self):
        pass

    @abstractmethod
    def apply_expansion(self, expansion):
        pass

    @abstractmethod
    def is_expandable(self) -> bool:
        pass

    @abstractmethod
    def is_top(self) -> bool:
        pass

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
        self.val = AbstractFeature.BOTTOM

    def __deepcopy__(self, memo):
        new_one = SingletonAbstractFeature()
        new_one.val = self.val # no need to copy at all
        return new_one

    def to_json_dict(self):
        if self.is_top():
            return "$TOP"
        if self.is_bottom():
            return "$BOTTOM"
        v = self.val
        if isinstance(v, iwho.InsnScheme):
            return "$InsnScheme:{}".format(str(v))
        else:
            return v

    @staticmethod
    def from_json_dict(acfg, json_dict):
        res = SingletonAbstractFeature()
        if isinstance(json_dict, str) and len(json_dict) > 0 and json_dict[0] == '$':
            if json_dict == "$TOP":
                res.val = AbstractFeature.TOP
            elif json_dict == "$BOTTOM":
                res.val = AbstractFeature.BOTTOM
            else:
                res.val = acfg.reconstruct_json_str(json_dict)
        else:
            res.val = json_dict
        return res

    def __str__(self) -> str:
        return str(self.val)

    def expand(self):
        self.set_to_top()
        return self.val

    def apply_expansion(self, expansion):
        self.val = expansion

    def is_expandable(self) -> bool:
        return not self.is_top()

    def is_top(self) -> bool:
        return self.val == AbstractFeature.TOP

    def is_bottom(self) -> bool:
        return self.val == AbstractFeature.BOTTOM

    def get_val(self):
        if isinstance(self.val, AbstractFeature.SpecialValues):
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
            return "$BOTTOM"
        return tuple(self.val)

    @staticmethod
    def from_json_dict(acfg, json_dict):
        res = SubSetAbstractFeature()
        if isinstance(json_dict, str) and len(json_dict) > 0 and json_dict[0] == '$':
            if json_dict == "$BOTTOM":
                res.val = AbstractFeature.BOTTOM
        else:
            assert isinstance(json_dict, list) or isinstance(json_dict, tuple)
            res.val = set(json_dict)
        return res

    def expand(self):
        if self.is_bottom():
            self.val = set()
        else:
            self.val.remove(random.choice(tuple(self.val)))
        return self.val

    def apply_expansion(self, expansion):
        self.val = expansion

    def is_expandable(self):
        return not self.is_top()

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


class AbstractInsn:
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
            json_features[k] = cls.from_json_dict(acfg, v)
        res.features = json_features
        return res

    def __str__(self) -> str:
        return self.acfg.stringify_abstract_features(self.features)

    def get_expandable_components(self):
        if self.features['present'].val == False:
            # There is no point in expanding components of insns that are
            # guaranteed to not be present anyway.
            # If we expand such an instruction, we should expand every feature
            # of it to top.

            all_features = [ v for k, v in self.features.items()]
            assert all(map(lambda x: x[0] == 'present' or x[1].is_bottom(), self.features.items()))

            return [('present', all_features)]

        res = []
        for k, v in self.features.items():
            if v.is_expandable():
                res.append( (k, [v]) )
        return res

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
        ctx = self.acfg.ctx

        if self.features['present'].val == False:
            return None

        if self.features['present'].is_top():
            if random.choice([True, False]):
                # TODO one might want to adjust the probabilities here...
                return None

        # Collect all insn schemes that match the AbstractInsn.
        scheme = self.features['exact_scheme'].get_val()
        if scheme is not None:
            # we could validate that the other features don't exclude this
            # scheme, but that cannot be an issue as long as we only go up in
            # the lattice
            return scheme

        feasible_schemes = None

        order = self.acfg.index_order
        for k in order:
            v = self.features[k]
            if v.is_top():
                continue
            if v.is_bottom():
                raise SamplingError(f"Sampling an AbstractInsn with a BOTTOM feature: {k} in {self}")
            feasible_schemes_for_feature = self.acfg.scheme_index(k, v)
            if feasible_schemes is None:
                feasible_schemes = set(feasible_schemes_for_feature)
            else:
                feasible_schemes.intersection_update(feasible_schemes_for_feature)

        if feasible_schemes is None:
            # all features are TOP, no restriction
            feasible_schemes = ctx.insn_schemes
        else:
            feasible_schemes = tuple(feasible_schemes)

        if len(feasible_schemes) == 0:
            raise SamplingError(f"No InsnScheme is feasible for AbstractInsn {self}")
        return random.choice(feasible_schemes)



def encode_op_keys(op_keys):
    if isinstance(op_keys, list) or isinstance(op_keys, tuple):
        return tuple(( encode_op_keys(k) for k in op_keys ))
    elif isinstance(op_keys, iwho.InsnScheme.OperandKind):
        return f"$OperandKind:{op_keys.value}"
    else:
        return op_keys

def decode_op_keys(acfg, op_key_list):
    if isinstance(op_key_list, list) or isinstance(op_key_list, tuple):
        return tuple(( decode_op_keys(acfg, k) for k in op_key_list ))
    elif isinstance(op_key_list, str) and op_key_list.startswith('$'):
        return acfg.reconstruct_json_str(op_key_list)
    return op_key_list


class AbstractBlock:
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
        res['abs_aliasing'] = [ (encode_op_keys(k), x.to_json_dict()) for k, x in self._abs_aliasing.items() ]
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
            key = decode_op_keys(acfg, k)
            aliasing[key] = SingletonAbstractFeature.from_json_dict(acfg, v)
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

    @property
    def expandable_components(self):
        """TODO document"""
        expandable_components = dict()

        # collect all expandable AbstractFeatures of the instruction part
        for ai_idx, ai in enumerate(self.abs_insns):
            for k, vs in ai.get_expandable_components():
                expandable_components[(0, ai_idx, k)] = vs

        # collect all expandable AbstractFeatures of the aliasing part
        for k, v in self._abs_aliasing.items():
            if v.is_expandable():
                expandable_components[(1, k)] = [v]

        return expandable_components

    def expand(self, limit_tokens):
        """ Choose an expandable AbstractFeature with a token not in
        `limit_tokens` and expand it.

        Returns the token of the expanded component or None if none of the
        AbstractFeatures not in limit_tokens can be expanded.
        """

        expandable_components = self.expandable_components

        # take the tokens of the collected AbstractFeatures and remove the forbidden ones
        tokens = set(expandable_components.keys())
        tokens.difference_update(limit_tokens)

        if len(tokens) == 0:
            # nothing to expand remains
            return None, None

        # choose an allowed expandable token, expand its AbstractFeature, and return the token
        chosen_token = random.choice(tuple(tokens))
        chosen_expansion = [ v.expand() for v in expandable_components[chosen_token] ]
        return (chosen_token, chosen_expansion)

    def apply_expansion(self, token, expansion):
        expandable_components = self.expandable_components
        features = expandable_components[token]
        assert len(features) == len(expansion)
        for feature, exp in zip(features, expansion):
            feature.apply_expansion(exp)

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
                        adjusted_fixed_op = self.acfg.adjust_operand_width(fixed_op, insn_schemes[k[0]].get_operand_scheme(k[1]))
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
                            disallowed = self.acfg.adjust_operand_width(disallowed, op_scheme)
                            try:
                                allowed_operands.remove(disallowed)
                            except KeyError as e:
                                pass
                chosen = random.choice(list(allowed_operands))
                chosen_operands[idx] = chosen
                for k in same[idx]:
                    chosen_operands[k] = self.acfg.adjust_operand_width(chosen, insn_schemes[k[0]].get_operand_scheme(k[1]))

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

