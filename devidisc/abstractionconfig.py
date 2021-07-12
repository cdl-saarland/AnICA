""" TODO document
"""

from abc import ABC, abstractmethod
from collections import defaultdict
import math
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

        self.feature_keys = [
                'exact_scheme',
                'present',
                'mnemonic',
                'opschemes',

                'category',
                'extension',
                'isa-set',

                # 'skl_uops',
            ]

        self.max_block_len = max_block_len

        self.generalization_batch_size = 100
        self.discovery_batch_size = 100

        # the interestingness of an experiment must be at least that high to be
        # considered interesting
        self.min_interestingness = 0.1

        # at least this ratio of a batch of experiments must be interesting for
        # the batch to be considered mostly interesting.
        self.mostly_interesting_ratio = 0.97

        self.predmanager = predmanager

        self.build_index()

    def compute_interestingness(self, eval_res):
        if any((v.get('TP', None) is None or v.get('TP', -1.0) < 0 for k, v in eval_res.items())):
            # errors are always interesting
            return math.inf
        values = [v['TP'] for k, v in eval_res.items()]
        rel_error = ((max(values) - min(values)) / sum(values)) * len(values)
        # TODO think about this metric?
        return rel_error

    def is_interesting(self, eval_res) -> bool:
        return self.compute_interestingness(eval_res) >= self.min_interestingness

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
        # res['skl_uops'] = SubSetAbstractFeature()
        res['opschemes'] = SubSetAbstractFeature()

        res['category'] = SingletonAbstractFeature()
        res['extension'] = SingletonAbstractFeature()
        res['isa-set'] = SingletonAbstractFeature()

        return res

    # TODO it would probably make sense to extract the indexing into its own class
    @property
    def index_order(self):
        return [
                'mnemonic',
                # 'skl_uops',
                'opschemes',

                'category',
                'extension',
                'isa-set',
            ]

    def scheme_index(self, feature_key, value):
        if feature_key == 'mnemonic':
            mnemonic = value.val
            return self.ctx.mnemonic_to_insn_schemes[mnemonic]

        index = self.feature_indices[feature_key]

        if isinstance(value, SubSetAbstractFeature):
            assert len(value.val) > 0
            res = None
            for x in value.val:
                cached_val = index.get(x, None)
                if cached_val is None:
                    logger.info(f"Found no cached value for '{x}' in the index for {feature_key}, probably because its using InsnSchemes have been filtered.")
                    cached_val = {}
                if res is None:
                    res = set(cached_val)
                else:
                    res.intersection_update(cached_val)
            return res
        elif isinstance(value, SingletonAbstractFeature):
            x = value.val
            cached_val = index.get(x, None)
            assert cached_val is not None, f"Found no cached value for '{x}' in the index for '{feature_key}'."
            return cached_val

    def build_index(self):
        self.feature_indices = dict()
        # TODO we might want to do a loop interchange here

        # subsets
        for f in ['opschemes']:
            curr_idx = defaultdict(list)
            self.feature_indices[f] = curr_idx
            for ischeme in self.ctx.filtered_insn_schemes:
                features = self.extract_features(ischeme)
                if features[f] is not None:
                    for u in features[f]:
                        curr_idx[u].append(ischeme)

        # singletons
        for f in ['category', 'extension', 'isa-set']:
            curr_idx = defaultdict(list)
            self.feature_indices[f] = curr_idx
            for ischeme in self.ctx.filtered_insn_schemes:
                features = self.extract_features(ischeme)
                x = features[f]
                if x is not None:
                    curr_idx[x].append(ischeme)

    def compute_feasible_schemes(self, absfeature_dict):
        """ Collect all insn schemes that match the abstract features.

        `absfeature_dict` is a dict mapping feature names to instances of
        `AbstractFeature`, like it is found in `AbstractInsn`.
        """
        scheme = absfeature_dict['exact_scheme'].get_val()
        if scheme is not None:
            # we could validate that the other features don't exclude this
            # scheme, but that cannot be an issue as long as we only go up in
            # the lattice
            return (scheme,)

        feasible_schemes = None

        order = self.index_order
        for k in order:
            v = absfeature_dict[k]
            if v.is_top():
                continue
            if v.is_bottom():
                return tuple()
            feasible_schemes_for_feature = self.scheme_index(k, v)
            if feasible_schemes is None:
                feasible_schemes = set(feasible_schemes_for_feature)
            else:
                feasible_schemes.intersection_update(feasible_schemes_for_feature)

        if feasible_schemes is None:
            # all features are TOP, no restriction
            feasible_schemes = self.ctx.filtered_insn_schemes
        else:
            feasible_schemes = tuple(feasible_schemes)

        return feasible_schemes

    def extract_features(self, ischeme: Union[iwho.InsnScheme, None]):
        if ischeme is None:
            return {'present': False}
        res = {'present': True}
        res['exact_scheme'] = ischeme
        res['mnemonic'] = self.ctx.extract_mnemonic(ischeme)
        # res['skl_uops'] = [] # This will produce a TOP entry if the feature is not present

        from_scheme = self.ctx.get_features(ischeme)
        if from_scheme is not None:
            entry = from_scheme[0]
            res['category'] = entry.get('category', None)
            res['extension'] = entry.get('extension', None)
            res['isa-set'] = entry.get('isa-set', None)
        #     port_usage = from_scheme[0]["measurements"].get("SKL")
        #     if port_usage is not None:
        #         port_usage = port_usage.split('+')
        #         res['skl_uops'] = port_usage
        else:
            res['category'] = None
            res['extension'] = None
            res['isa-set'] = None

        opschemes = []
        for k, opscheme in ischeme.explicit_operands.items():
            opschemes.append(str(opscheme))

        for opscheme in ischeme.implicit_operands:
            opschemes.append(str(opscheme))

        res['opschemes'] = opschemes

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

