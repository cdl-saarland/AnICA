""" TODO document
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Union, Sequence

import iwho

from abstractblock import *
from predmanager import PredictorManager

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
        eval_it, result_ref = self.predmanager.eval_with_all_and_report(bbs)

        interesting_bbs = []

        for bb, eval_res in eval_it:
            if self.is_interesting(eval_res):
                interesting_bbs.append(bb)

        return interesting_bbs, result_ref

    def is_mostly_interesting(self, bbs: Sequence[iwho.BasicBlock]) -> bool:
        interesting_bbs, result_ref = self.filter_interesting(bbs)
        ratio = len(interesting_bbs) / len(bbs)
        return (ratio >= self.mostly_interesting_ratio), result_ref

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

    def init_abstract_features(self):
        res = dict()
        res['exact_scheme'] = SingletonAbstractFeature()
        res['present'] = SingletonAbstractFeature()
        res['mnemonic'] = SingletonAbstractFeature()
        res['skl_uops'] = SubSetAbstractFeature()
        return res

    # TODO it would probably make sense to extract the indexing into its own class
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
        for ischeme in self.ctx.filtered_insn_schemes:
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

    def introduce_json_references(self, json_dict):
        if isinstance(json_dict, tuple) or isinstance(json_dict, list):
            return tuple((self.introduce_json_references(x) for x in json_dict))
        if isinstance(json_dict, dict):
            return { k: self.introduce_json_references(x) for k,x in json_dict.items() }
        if isinstance(json_dict, iwho.InsnScheme.OperandKind):
            return f"$OperandKind:{json_dict.value}"
        if isinstance(json_dict, iwho.InsnScheme):
            return f"$InsnScheme:{str(json_dict)}"
        if isinstance(json_dict, AbstractFeature.SpecialValue):
            return f"$SV:{json_dict.name}"
        return json_dict

    def resolve_json_references(self, json_dict):
        if isinstance(json_dict, tuple) or isinstance(json_dict, list):
            return tuple((self.resolve_json_references(x) for x in json_dict))
        if isinstance(json_dict, dict):
            return { k: self.resolve_json_references(x) for k,x in json_dict.items() }
        if isinstance(json_dict, str):
            json_str = json_dict

            search_str = '$InsnScheme:'
            if json_str.startswith(search_str):
                scheme_str = json_str[len(search_str):]
                return self.ctx.str_to_scheme[scheme_str]

            search_str = '$OperandKind:'
            if json_str.startswith(search_str):
                opkind_val = int(json_str[len(search_str):])
                for ev in iwho.InsnScheme.OperandKind:
                    if opkind_val == ev.value:
                        return ev

            search_str = '$SV:'
            if json_str.startswith(search_str):
                val = json_str[len(search_str):]
                return AbstractFeature.SpecialValue[val]

            return json_str
        return json_dict

