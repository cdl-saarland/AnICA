""" TODO document
"""

from abc import ABC, abstractmethod
from typing import Union

import iwho

from .abstractblock import *

# TODO this should be an ABC with subclasses for different testing campaigns
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

