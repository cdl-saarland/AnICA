""" This file provides classes to represent abstractions of basic blocks, i.e.
representations of sets of 'conrete' basic blocks.

Those abstractions have methods to sample from the represented concrete blocks,
as well as ways to systematically extend the set of represented concrete
blocks.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from copy import deepcopy, copy
import itertools
import random
import textwrap
from typing import Optional, Union

import iwho

import logging
logger = logging.getLogger(__name__)


class AbstractFeature(ABC):
    @abstractmethod
    def __deepcopy__(self, memo):
        pass

    @abstractmethod
    def expand(self):
        pass

    @abstractmethod
    def is_expandable(self) -> bool:
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
        self.is_top = False
        self.is_bot = True
        self.val = None

    def __deepcopy__(self, memo):
        new_one = SingletonAbstractFeature()
        new_one.is_top = self.is_top
        new_one.is_bot = self.is_bot
        new_one.val = self.val # no need to copy at all
        return new_one

    def __str__(self) -> str:
        if self.is_top:
            return "TOP"
        if self.is_bot:
            return "BOT"
        return str(self.val)

    def expand(self):
        self.set_to_top()

    def is_expandable(self) -> bool:
        return not self.is_top

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


class SubSetAbstractFeature(AbstractFeature):
    """ Represents all sets of items that are a (non-strict) superset of
    self.vals.
    """
    def __init__(self):
        self.is_bot = True
        self.vals = None

    def __deepcopy__(self, memo):
        new_one = SubSetAbstractFeature()
        new_one.is_bot = self.is_bot
        new_one.vals = copy(self.vals) # no need to deepcopy
        return new_one

    def expand(self):
        if self.is_bot:
            self.vals = set()
            self.is_bot = False
        else:
            self.vals.remove(random.choice(tuple(self.vals)))

    def is_expandable(self):
        return self.is_bot or len(self.vals) > 0

    def __str__(self) -> str:
        if self.is_bot:
            return "BOT"
        if len(self.vals) == 0:
            return "TOP"
        return "{" + ", ".join(sorted(map(str, self.vals))) + "}"

    def is_bottom(self) -> bool:
        return self.is_bot

    def subsumes(self, other: AbstractFeature) -> bool:
        if other.is_bot:
            return True
        if self.is_bot:
            return False
        return self.vals.issubset(other.vals)

    def subsumes_feature(self, feature) -> bool:
        if feature is None:
            return True
        if self.is_bot:
            return False
        return self.vals.issubset(set(feature))

    def join(self, feature):
        if feature is not None:
            if self.is_bot:
                self.vals = set(feature)
                self.is_bot = False
            else:
                self.vals.intersection_update(feature)


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

    def __str__(self) -> str:
        return self.acfg.stringify_abstract_features(self.features)

    def get_expandable_components(self):
        res = []
        for k, v in self.features.items():
            if v.is_expandable():
                res.append( (k, v) )
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

        # TODO describe semantics - operand j of instruction i aliases with operand y of instruction x
        self._abs_aliasing = dict()

        # the semantics of entries not present in the above map changes over
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

    def __deepcopy__(self, memo):
        new_one = AbstractBlock(self.acfg)
        new_one.maxlen = self.maxlen
        new_one.abs_insns = deepcopy(self.abs_insns, memo)
        new_one._abs_aliasing = { k: deepcopy(v, memo) for k, v in self._abs_aliasing.items() } # no need to duplicate the keys here
        new_one.is_bot = self.is_bot
        return new_one

    def expand(self, limit_tokens):
        """ Choose an expandable AbstractFeature with a token not in
        `limit_tokens` and expand it.

        Returns the token of the expanded component or None if none of the
        AbstractFeatures not in limit_tokens can be expanded.
        """

        expandable_components = dict()

        # collect all expandable AbstractFeatures of the instruction part
        for ai_idx, ai in enumerate(self.abs_insns):
            for k, v in ai.get_expandable_components():
                expandable_components[(0, ai_idx, k)] = v

        # collect all expandable AbstractFeatures of the aliasing part
        for k, v in self._abs_aliasing.items():
            expandable_components[(1, k)] = v

        # take the tokens of the collected AbstractFeatures and remove the forbidden ones
        tokens = set(expandable_components.keys())
        tokens.difference_update(limit_tokens)

        if len(tokens) == 0:
            # nothing to expand remains
            return None

        # choose an allowed expandable token, expand its AbstractFeature, and return the token
        chosen_token = random.choice(tuple(tokens))
        expandable_components[chosen_token].expand()
        return chosen_token

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
            if absval.is_top:
                continue
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

        # aliasing
        if other.is_bot:
            return True

        if self.is_bot:
            return False

        # all items not present are considered TOP and subsume everything
        for k, sv in self._abs_aliasing.items():
            if sv.is_top:
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
            if ad is None or ad.is_top:
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

        same = defaultdict(set)
        not_same = defaultdict(set)

        for (insn_op1, insn_op2), should_alias in self._abs_aliasing.items():
            iidx1, op_key1 = insn_op1
            iidx2, op_key2 = insn_op2
            # Do not enter information for instructions and operands that are
            # not present.
            if insn_schemes[iidx1] is None or insn_schemes[iidx2] is None:
                continue
            if (insn_schemes[iidx1].get_operand_scheme(op_key1) is None or
                    insn_schemes[iidx2].get_operand_scheme(op_key2) is None):
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
                        print(f"InsnScheme {ischeme} requires different operands for {op_key} from aliasing with fixed operands: {prev_choice} and {fixed_op}")
                        assert False, "instantiation error" # TODO
                        return None
                    chosen_operands[idx] = fixed_op
                    for k in same[idx]:
                        prev_choice = chosen_operands.get(k, None)
                        adjusted_fixed_op = self.acfg.adjust_operand_width(fixed_op, insn_schemes[k[0]].get_operand_scheme(k[1]))
                        if prev_choice is not None and prev_choice != adjusted_fixed_op:
                            print(f"InsnScheme {insn_schemes[k[0]]} requires different operands for {k[1]} from aliasing with fixed operands: {prev_choice} and {adjusted_fixed_op}")
                            assert False, "instantiation error" # TODO
                            return None
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
                    chosen_operands[k] = chosen

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
            instance = ischeme.instantiate(op_map)

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

    def may_alias(self, op1: iwho.OperandInstance, op2: iwho.OperandInstance):
        # TODO this could use additional information about the instantiation
        # (in contrast to the iwho.Context method, which should be correct for
        # all uses)
        return self.ctx.may_alias(op1, op2)

    def skip_for_aliasing(self, op_scheme):
        if op_scheme.is_fixed():
            operand = op_scheme.fixed_operand
            if isinstance(operand, iwho.x86.RegisterOperand):
                if operand.category == iwho.x86.RegKind['FLAG']:
                    # Skip flag operands. We might want to revisit this decision.
                    return True
            elif isinstance(operand, iwho.x86.ImmediateOperand):
                return True
            elif isinstance(operand, iwho.x86.SymbolOperand):
                return True
        else:
            constraint = op_scheme.operand_constraint
            if isinstance(constraint, iwho.SetConstraint):
                operand = constraint.acceptable_operands[0]
                if operand.category == iwho.x86.RegKind['FLAG']:
                    # Skip flag operands. We might want to revisit this decision.
                    return True
            elif isinstance(constraint, iwho.x86.ImmConstraint):
                return True
            elif isinstance(constraint, iwho.x86.SymbolConstraint):
                return True
        return False

    def adjust_operand_width(self, operand, op_scheme):
        acceptable = None
        if op_scheme.is_fixed():
            width = op_scheme.fixed_operand.width
            acceptable = {op_scheme.fixed_operand}
        else:
            constraint = op_scheme.operand_constraint
            if isinstance(constraint, iwho.SetConstraint):
                acceptable = constraint.acceptable_operands
                width = acceptable[0].width
                acceptable = set(acceptable)
            else:
                width = constraint.width

        if operand.width == width:
            res = operand
        elif isinstance(operand, iwho.x86.RegisterOperand):
            fitting_regs = set(self.ctx.get_registers_where(alias_class=operand.alias_class, width=width))
            assert len(fitting_regs) >= 1
            if acceptable is not None:
                fitting_regs.intersection_update(acceptable)
            assert len(fitting_regs) >= 1
            res = next(iter(fitting_regs))
        elif isinstance(operand, iwho.x86.MemoryOperand):
            res = iwho.x86.MemoryOperand(width=operand.width, segment=operand.segment, base=operand.base, index=operand.index, scale=operand.scale, displacement=operand.displacement)
        elif isinstance(operand, iwho.x86.MemoryOperand):
            res = iwho.x86.ImmediateOperand(width=operand.width, value=operand.value)
        else:
            res = operand

        return res

    def allowed_operands(self, op_scheme):
        if op_scheme.is_fixed():
            return {op_scheme.fixed_operand}
        constraint = op_scheme.operand_constraint
        if isinstance(constraint, iwho.SetConstraint):
            # TODO remove reserved operands?
            return set(constraint.acceptable_operands)
        elif isinstance(constraint, iwho.x86.MemConstraint):
            base_reg = iwho.x86.all_registers["rbx"]
            displacement = 64
            # TODO allow more, deduplicate?
            return {iwho.x86.MemoryOperand(width=constraint.width, base=base_reg, displacement=displacement)}
        elif isinstance(constraint, iwho.x86.ImmConstraint):
            return {iwho.x86.ImmediateOperand(width=constraint.width, value=42)}
        else:
            assert isinstance(constraint, iwho.x86.SymbolConstraint)
            return {iwho.x86.SymbolOperand()}

    def init_abstract_features(self):
        res = dict()
        res['exact_scheme'] = SingletonAbstractFeature()
        res['present'] = SingletonAbstractFeature()
        res['mnemonic'] = SingletonAbstractFeature()
        res['skl_uops'] = SubSetAbstractFeature()
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
            port_usage = from_scheme[0].get("SKL")
            if port_usage is not None:
                port_usage = port_usage.split('+')
            res['skl_uops'] = port_usage

        return res

    def stringify_abstract_features(self, afeatures):
        return "\n".join((f"{k}: {afeatures[k]}" for k in self.feature_keys))

