""" TODO document
"""

from collections import defaultdict
from typing import Union, Sequence

import iwho

from .abstractblock import *
from .configurable import ConfigMeta

import iwho.x86

def is_memory_opscheme(opscheme):
    # TODO this is x86 specific
    if opscheme.is_fixed():
        return isinstance(opscheme.fixed_operand, iwho.x86.MemoryOperand)
    else:
        return isinstance(opscheme.operand_constraint, iwho.x86.MemConstraint)

def mem_access_width(opscheme):
    # TODO this is x86 specific
    if opscheme.is_fixed():
        return opscheme.fixed_operand.width
    else:
        return opscheme.operand_constraint.width

_default_features = [
        ["exact_scheme", "singleton"],
        ["present", "singleton"],
        ["mnemonic", "singleton"],
        ["opschemes", "subset"],
        ["memory_usage", "subset_or_definitely_not"],
        ["category", "singleton"],
        ["extension", "singleton"],
        ["isa-set", "singleton"],
    ]

class InsnFeatureManager(metaclass=ConfigMeta):
    """ A class to manage abstract and concrete instruction features.

    It provides indices to quickly compute InsnSchemes that fulfill constraints
    given as AbstractFeatures through the `compute_feasible_schemes` method and
    it knows how to initialize abstract features.

    Special feature names:
        - exact_scheme
        - present
        - mnemonic
    """

    config_options = dict(
        features = (_default_features,
            'An ordered list of tuples containing the names of features and '
            'the kind of abstraction to use for it. The order affects the '
            'index lookup order and as a consequence the run time.'),
    )

    not_indexed = {'exact_scheme', 'present'}

    def __init__(self, iwho_ctx, config):
        self.configure(config)

        self.iwho_ctx = iwho_ctx

        self.index_order = [ key for key, kind in self.features if key not in self.not_indexed ]
        self.feature_indices = dict()
        self._build_index()

    def _build_index(self):
        # add indices for all the relevant features
        for key, kind in self.features:
            if key in self.not_indexed or key == "mnemonic":
                # No index needed, either because we don't use one or, in
                # the case of the mnemonic, because it is already indexed
                # in the iwho_ctx.
                continue
            self.feature_indices[key] = defaultdict(list)

        # fill the indices with all relevant instructions
        for ischeme in self.iwho_ctx.filtered_insn_schemes:
            insn_features = self.extract_features(ischeme)
            for key, kind in self.features:
                if key in self.not_indexed or key == "mnemonic":
                    continue
                curr_idx = self.feature_indices[key]

                feature_value = insn_features[key]
                if feature_value is None:
                    continue

                if kind == "singleton":
                    curr_idx[feature_value].append(ischeme)
                elif kind == "subset":
                    for elem in feature_value:
                        curr_idx[elem].append(ischeme)
                elif kind == "subset_or_definitely_not":
                    for elem in feature_value:
                        curr_idx[elem].append(ischeme)
                    if len(feature_value) == 0:
                        curr_idx['_definitely_not_'].append(ischeme)
                    else:
                        curr_idx['_definitely_'].append(ischeme)
                else:
                    assert False, f"unknown feature kind for key {key}: {kind}"

    def init_abstract_features(self):
        res = dict()
        for key, kind in self.features:
            if kind == "singleton":
                absval = SingletonAbstractFeature()
            elif kind == "subset":
                absval = SubSetAbstractFeature()
            elif kind == "subset_or_definitely_not":
                absval = SubSetOrDefinitelyNotAbstractFeature()
            else:
                assert False, f"unknown feature kind for key {key}: {kind}"
            res[key] = absval
        return res

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
            feasible_schemes_for_feature = self.lookup(k, v)
            if feasible_schemes is None:
                feasible_schemes = set(feasible_schemes_for_feature)
            else:
                feasible_schemes.intersection_update(feasible_schemes_for_feature)

        if feasible_schemes is None:
            # all features are TOP, no restriction
            feasible_schemes = self.iwho_ctx.filtered_insn_schemes
        else:
            feasible_schemes = tuple(feasible_schemes)

        return feasible_schemes

    def lookup(self, feature_key, value):
        """ Return a set of InsnSchemes that matches the constraint implied by
        `value` on the feature given by `feature_key`.
        """
        assert not value.is_top() and not value.is_bottom()

        if feature_key == 'mnemonic':
            # We don't need to cache that, since the iwho context already does
            # that.
            index = self.iwho_ctx.mnemonic_to_insn_schemes
        else:
            index = self.feature_indices[feature_key]

        if isinstance(value, SubSetAbstractFeature) or isinstance(value, SubSetOrDefinitelyNotAbstractFeature):
            if isinstance(value, SubSetOrDefinitelyNotAbstractFeature):
                if value.is_in_subfeature.val == False:
                    return set(index['_definitely_not_'])
                assert value.is_in_subfeature.val == True
                if value.subfeature.is_top():
                    return set(index['_definitely_'])
                value = value.subfeature

            # We are looking for InsnSchemes that contain all elements of
            # value, i.e. the intersection of the InsnScheme sets associated to
            # those elements.
            assert len(value.val) > 0
            res = None # this None will never carry through the following loop
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

    def extract_features(self, ischeme: Union[iwho.InsnScheme, None]):
        if ischeme is None:
            return {'present': False}
        remaining_features = set(self.index_order)

        res = dict()
        res['present'] = True
        remaining_features.discard('present')

        res['exact_scheme'] = ischeme
        remaining_features.discard('exact_scheme')

        if 'mnemonic' in remaining_features:
            res['mnemonic'] = self.iwho_ctx.extract_mnemonic(ischeme)
            remaining_features.discard('mnemonic')

        if 'opschemes' in remaining_features or 'memory_usage' in remaining_features:
            memory_opschemes = []
            opschemes = []
            for k, opscheme in ischeme.explicit_operands.items():
                if is_memory_opscheme(opscheme):
                    memory_opschemes.append(opscheme)
                opschemes.append(str(opscheme))
            for opscheme in ischeme.implicit_operands:
                opschemes.append(str(opscheme))

        if 'opschemes' in remaining_features:
            res['opschemes'] = opschemes
            remaining_features.discard('opschemes')

        if 'memory_usage' in remaining_features:
            mem_usage = set()
            for opscheme in memory_opschemes:
                if opscheme.is_read:
                    mem_usage.add("R")
                if opscheme.is_written:
                    mem_usage.add("W")
                mem_usage.add(f"S:{mem_access_width(opscheme)}")
            res['memory_usage'] = mem_usage
            remaining_features.discard('memory_usage')

        from_scheme = self.iwho_ctx.get_features(ischeme)
        for key in remaining_features:
            if from_scheme is None or len(from_scheme) == 0:
                res[key] = None
                continue
            entry = from_scheme[0]
            res[key] = entry.get(key, None)

        return res

