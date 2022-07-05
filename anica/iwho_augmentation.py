""" Functionality that is closely related to IWHO components, but specific to
the AnICA application.

Mainly, this concerns alias information on operands that we have because we
know how AnICA samples basic blocks.
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
        if isinstance(op1, iwho.x86.MemoryOperand) and isinstance(op2, iwho.x86.MemoryOperand):
            # we know that because of how we sample memory operands
            return op1.base == op2.base and op1.displacement == op2.displacement

        # TODO this could use additional information about the instantiation
        # (in contrast to the iwho.Context method, which should be correct for
        # all uses)
        return self.iwho_ctx.must_alias(op1, op2)

    def may_alias(self, op1: iwho.OperandInstance, op2: iwho.OperandInstance):
        if isinstance(op1, iwho.x86.MemoryOperand) and isinstance(op2, iwho.x86.MemoryOperand):
            # we know that because of how we sample memory operands
            return op1.base == op2.base and op1.displacement == op2.displacement

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
        """ Return `True` if the operand scheme should not be considered for
        aliases.
        """
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

    mem_base_names = ["rbp", "rsi", "rdi"]
    # To produce valid inputs for nanoBench, we need to use only registers as
    # base pointers that get a memory allocation there. A natural choice of
    # those would be r14 rather than rbp (because rbp cannot be used as base
    # pointer without displacement). However, r14 is an extended register, i.e.
    # using it requires a REX prefix, which can break instruction schemes that
    # do not want a REX prefix. Since we use a displacement anyway, using rbp
    # should be fine as well.

    reserved_names = ["r15", "rsp", "r14"] + mem_base_names
    # nanoBench requires an unused r15 for the loop counter
    # similarly, r14 is a memory base register, even though we don't use it

    def allowed_operands(self, op_scheme):
        """ For an operand scheme, return operands that we can use in AnICA to
        instantiate them. They should be a subset of those allowed by the iwho
        constraints.
        """
        if op_scheme.is_fixed():
            return {op_scheme.fixed_operand}
        constraint = op_scheme.operand_constraint
        if isinstance(constraint, iwho.x86.RegisterConstraint):
            reserved_alias_classes = [iwho.x86.all_registers[n].alias_class for n in self.reserved_names]
            # TODO should we allow register operands to alias with memory locations?
            return { o for o in constraint.acceptable_operands if o.alias_class not in reserved_alias_classes }
        elif isinstance(constraint, iwho.x86.MemConstraint):
            reg_names = self.mem_base_names
            base_regs = [iwho.x86.all_registers[n] for n in reg_names]
            displacements = [64, 128]
            # TODO deduplicate?
            return {iwho.x86.MemoryOperand(width=constraint.width, base=base_reg, displacement=displacement) for base_reg in base_regs for displacement in displacements}
        elif isinstance(constraint, iwho.x86.ImmConstraint):
            return {iwho.x86.ImmediateOperand(width=constraint.width, value=42)}
        else:
            assert isinstance(constraint, iwho.x86.SymbolConstraint)
            return {iwho.x86.SymbolOperand()}

