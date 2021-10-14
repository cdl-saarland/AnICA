""" TODO document
"""

from collections import defaultdict
from typing import Union, Sequence

import editdistance
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
        ["mnemonic", ["editdistance", 3]], # "singleton"
        ["opschemes", "subset"],
        ["memory_usage", "subset_or_definitely_not"],
        ["uops_on_SKL", ["log_ub", 5]],
        ["category", "singleton"],
        ["extension", "singleton"],
        ["isa-set", "singleton"],
        ["has_lock", "singleton"],
        ["has_rep", "singleton"],
    ]

class InsnFeatureManager(metaclass=ConfigMeta):
    """ A class to manage abstract and concrete instruction features.

    It provides indices to quickly compute InsnSchemes that fulfill constraints
    given as AbstractFeatures through the `compute_feasible_schemes` method and
    it knows how to initialize abstract features.

    Special feature names:
        - exact_scheme
    """

    config_options = dict(
        features = (_default_features,
            'An ordered list of tuples containing the names of features and '
            'the kind of abstraction to use for it. The order affects the '
            'index lookup order and as a consequence the run time.'),
    )

    not_indexed = {'exact_scheme'}

    def __init__(self, iwho_ctx, config):
        self.configure(config)

        self.iwho_ctx = iwho_ctx

        self.index_order = [ key for key, kind in self.features if key not in self.not_indexed ]
        self.feature_indices = dict()
        self._build_index()

        # A per-feature index mapping concrete string features s to a list of
        # concrete features with their editing distance from s.
        # We build that one on demand with `get_editdists()`.
        self.editdist_indices = dict()

    def _build_index(self):
        # add indices for all the relevant features
        for key, kind in self.features:
            if key in self.not_indexed:
                # No index needed (applies for exact_scheme)
                continue
            self.feature_indices[key] = defaultdict(list)

        # fill the indices with all relevant instructions
        for ischeme in self.iwho_ctx.filtered_insn_schemes:
            insn_features = self.extract_features(ischeme)
            for key, kind in self.features:
                if key in self.not_indexed:
                    continue
                curr_idx = self.feature_indices[key]

                feature_value = insn_features[key]
                if feature_value is None:
                    continue

                if isinstance(kind, list) or isinstance(kind, tuple):
                    kind, *args = kind

                if kind == "singleton" or kind == "editdistance":
                    curr_idx[feature_value].append(ischeme)
                elif kind == "log_ub":
                    v = len(feature_value)
                    log_feature = math.floor(math.log2(v + 1))
                    for i in range(log_feature, args[0] + 1):
                        curr_idx[i].append(ischeme)
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
            args = []
            if isinstance(kind, list) or isinstance(kind, tuple):
                # arguments are passed lisp style
                kind, *args = kind
            if kind == "singleton":
                absval = SingletonAbstractFeature()
            elif kind == "log_ub":
                assert len(args) == 1, "Wrong number of arguments for editditance feature: {len(args)} (expected: 1)"
                absval = LogUpperBoundAbstractFeature(args[0])
            elif kind == "subset":
                absval = SubSetAbstractFeature()
            elif kind == "subset_or_definitely_not":
                absval = SubSetOrDefinitelyNotAbstractFeature()
            elif kind == "editdistance":
                assert len(args) == 1, "Wrong number of arguments for editditance feature: {len(args)} (expected: 1)"
                absval = EditDistanceAbstractFeature(args[0])
            else:
                assert False, f"unknown feature kind for key {key}: {kind}"
            res[key] = absval
        return res

    def compute_feasible_schemes(self, absfeature_dict):
        """ Collect all insn schemes that match the abstract features.

        Returns a set that can be modified at will without affecting internal
        state.

        `absfeature_dict` is a dict mapping feature names to instances of
        `AbstractFeature`, like it is found in `AbstractInsn`.
        """
        exact_scheme_entry = absfeature_dict.get('exact_scheme', None)
        if exact_scheme_entry is not None:
            # special handling for thsi one, because there is only one feasible
            # scheme that is trivially known
            scheme = exact_scheme_entry.get_val()
            if scheme is not None:
                # we could validate that the other features don't exclude this
                # scheme, but that cannot be an issue as long as we only go up in
                # the lattice
                return {scheme}

        feasible_schemes = None

        order = self.index_order
        for k in order:
            v = absfeature_dict[k]
            if v.is_top():
                continue
            if v.is_bottom():
                return set()
            feasible_schemes_for_feature = self.lookup(k, v)
            if feasible_schemes is None:
                feasible_schemes = set(feasible_schemes_for_feature)
            else:
                feasible_schemes.intersection_update(feasible_schemes_for_feature)

        if feasible_schemes is None:
            # all features are TOP, no restriction
            feasible_schemes = set(self.iwho_ctx.filtered_insn_schemes)

        return feasible_schemes

    def lookup(self, feature_key, value):
        """ Return a set of InsnSchemes that matches the constraint implied by
        `value` on the feature given by `feature_key`.
        """
        assert not value.is_top() and not value.is_bottom()

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

        elif isinstance(value, SingletonAbstractFeature) or isinstance(value, LogUpperBoundAbstractFeature):
            x = value.val
            cached_val = index.get(x, None)
            assert cached_val is not None, f"Found no cached value for '{x}' in the index for '{feature_key}'."
            return cached_val

        elif isinstance(value, EditDistanceAbstractFeature):
            base = value.base
            curr_dist = value.curr_dist
            editing_distances = self.get_editdists(feature_key, base)
            res = set()
            for entry, dist in editing_distances:
                if dist > curr_dist:
                    # the editing distances are sorted in ascending order upon
                    # initialization, if we see one that is too far away, all
                    # following ones will be too far away as well
                    break
                cached_val = index.get(entry, None)
                assert cached_val is not None, f"Found no cached value for '{x}' in the index for '{feature_key}'."
                res.update(cached_val)

            return res

    def get_editdists(self, feature_key, base):
        index = self.editdist_indices.get(feature_key)
        if index is None:
            index = dict()
            self.editdist_indices[feature_key] = index
        res = index.get(base, None)
        if res is None:
            # create a list of (concrete feature, edit distance) pairs for the
            # base and sort it by ascending edit distance
            res = []
            scheme_index = self.feature_indices[feature_key]
            for k in scheme_index.keys():
                res.append((k, editdistance.eval(base, k)))
            res.sort(key=lambda x: x[1])
            index[base] = res
        return res

    def extract_features(self, ischeme: iwho.InsnScheme):
        assert ischeme is not None
        remaining_features = set(self.index_order)

        res = dict()

        if any(map(lambda x: x[0] == 'exact_scheme', self.features)):
            res['exact_scheme'] = ischeme
            remaining_features.discard('exact_scheme')

        if 'mnemonic' in remaining_features:
            res['mnemonic'] = self.iwho_ctx.extract_mnemonic(ischeme)
            remaining_features.discard('mnemonic')

        if 'has_lock' in remaining_features:
            res['has_lock'] = "lock " in str(ischeme)
            remaining_features.discard('has_lock')

        if 'has_rep' in remaining_features:
            res['has_rep'] = str(ischeme).startswith('rep')
            remaining_features.discard('has_rep')

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

        if 'uops_on_SKL' in remaining_features:
            if from_scheme is None or len(from_scheme) == 0:
                res['uops_on_SKL'] = None
            else:
                entry = from_scheme[0]

                port_str = entry['measurements'].get('SKL', None)
                if port_str is None:
                    res['uops_on_SKL'] = None
                else:
                    uops = []
                    for u in port_str.split('+'):
                        n, ps = u.split('*')
                        for x in range(int(n)):
                            uops.append(ps)

                    res['uops_on_SKL'] = uops
            remaining_features.discard('uops_on_SKL')

        for key in remaining_features:
            if from_scheme is None or len(from_scheme) == 0:
                res[key] = None
                continue
            entry = from_scheme[0]
            res[key] = entry.get(key, None)

        return res

