""" TODO document
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Union, Sequence

import iwho

from .abstractblock import *
from .predmanager import PredictorManager

# TODO this should be an ABC with subclasses for different testing campaigns
class AbstractionConfig:
    """ Configuration Class for AbstractBlock and subcomponents

    This encapsulates several configuration options like which features of the
    instructions to use for abstraction and how they are abstracted.
    """

    def __init__(self, ctx: iwho.Context, max_block_len, predmanager=None):
        self.ctx = ctx

        self.feature_keys = ['exact_scheme', 'present', 'mnemonic', 'skl_uops']

        self.max_block_len = max_block_len

        self.generalization_batch_size = 100
        self.discovery_batch_size = 100

        self.min_interesting_error = 0.1
        self.mostly_interesting_ratio = 0.9

        self.predmanager = predmanager

        self.build_index()

    def is_interesting(self, eval_res) -> bool:
        if any((v.get('TP', None) is None for k, v in eval_res.items())):
            # errors are always interesting
            return True
        values = [v['TP'] for k, v in eval_res.items()]
        rel_error = ((max(values) - min(values)) / sum(values)) * len(values)
        # TODO think about this metric?
        return rel_error >= self.min_interesting_error

    def filter_interesting(self, bbs: Sequence[iwho.BasicBlock]) -> Sequence[iwho.BasicBlock]:
        """ Given a list of concrete BasicBlocks, evaluate their
        interestingness and return the list of interesting ones.
        """
        eval_it = self.predmanager.eval_with_all(bbs)

        interesting_bbs = []

        for bb, eval_res in eval_it:
            if self.is_interesting(eval_res):
                interesting_bbs.append(bb)
                # TODO do something with the benchmark, give witnesses for interestingness

        return interesting_bbs

    def is_mostly_interesting(self, bbs: Sequence[iwho.BasicBlock]) -> bool:
        interesting_bbs = self.filter_interesting(bbs)
        ratio = len(interesting_bbs) / len(bbs)
        return ratio >= self.mostly_interesting_ratio


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
        # TODO this probably belongs to the iwho.Context
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
            # TODO deduplicate
            res = iwho.x86.MemoryOperand(width=operand.width, segment=operand.segment, base=operand.base, index=operand.index, scale=operand.scale, displacement=operand.displacement)
        elif isinstance(operand, iwho.x86.MemoryOperand):
            # TODO deduplicate
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

    @property
    def index_order(self):
        return ['mnemonic', 'skl_uops']

    def scheme_index(self, feature_key, value):
        if feature_key == 'mnemonic':
            mnemonic = value.val
            return self.ctx.mnemonic_to_insn_schemes[mnemonic]

        index = self.feature_indices[feature_key]

        if isinstance(value, SubSetAbstractFeature):
            res = set()
            for x in value.val:
                cached_val = index.get(x, None)
                assert cached_val is not None
                res.update(cached_val)
            return res
        elif isinstance(value, SingletonAbstractFeature):
            cached_val = index.get(x, None)
            assert cached_val is not None
            return cached_val

    def build_index(self):
        self.feature_indices = dict()
        uop_index = defaultdict(list)
        self.feature_indices['skl_uops'] = uop_index
        for ischeme in self.ctx.insn_schemes:
            features = self.extract_features(ischeme)
            if features['skl_uops'] is not None:
                for u in features['skl_uops']:
                    uop_index[u].append(ischeme)

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
