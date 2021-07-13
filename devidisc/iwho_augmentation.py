""" TODO document
"""

import iwho

class IWHOAugmentation:
    """ Configuration Class for AbstractBlock and subcomponents

    This encapsulates several configuration options like which features of the
    instructions to use for abstraction and how they are abstracted.
    """

    def __init__(self, iwho_ctx: iwho.Context):
        self.iwho_ctx = iwho_ctx

    def must_alias(self, op1: iwho.OperandInstance, op2: iwho.OperandInstance):
        # TODO this could use additional information about the instantiation
        # (in contrast to the iwho.Context method, which should be correct for
        # all uses)
        return self.iwho_ctx.must_alias(op1, op2)

    def may_alias(self, op1: iwho.OperandInstance, op2: iwho.OperandInstance):
        # TODO this could use additional information about the instantiation
        # (in contrast to the iwho.Context method, which should be correct for
        # all uses)
        return self.iwho_ctx.may_alias(op1, op2)

    def is_compatible(self, op_scheme1, op_scheme2):
        def extract_allowed_classes(op_scheme):
            if op_scheme.is_fixed():
                fixed_op = op_scheme.fixed_operand
                if isinstance(fixed_op, iwho.x86.RegisterOperand):
                    return {fixed_op.alias_class}
                if isinstance(fixed_op, iwho.x86.MemoryOperand):
                    return {"mem"}
                return set()
            op_constr = op_scheme.operand_constraint
            if isinstance(op_constr, iwho.x86.RegisterConstraint):
                return { x.alias_class for x in op_constr.acceptable_operands }
            if isinstance(op_constr, iwho.x86.MemConstraint):
                return {"mem"}
            return set()

        allowed_classes1 = extract_allowed_classes(op_scheme1)

        allowed_classes2 = extract_allowed_classes(op_scheme2)

        return not allowed_classes1.isdisjoint(allowed_classes2)

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
            if isinstance(constraint, iwho.x86.RegisterConstraint):
                operand = constraint.acceptable_operands[0]
                if operand.category == iwho.x86.RegKind['FLAG']:
                    # Skip flag operands. We might want to revisit this decision.
                    return True
            elif isinstance(constraint, iwho.x86.ImmConstraint):
                return True
            elif isinstance(constraint, iwho.x86.SymbolConstraint):
                return True
        return False

    def allowed_operands(self, op_scheme):
        if op_scheme.is_fixed():
            return {op_scheme.fixed_operand}
        constraint = op_scheme.operand_constraint
        if isinstance(constraint, iwho.x86.RegisterConstraint):
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

