""" TODO document
"""

from collections import defaultdict
from typing import Union, Sequence

import iwho

from .abstractblock import *

class InsnFeatureManager:
    """ A class to manage abstract and concrete instruction features.

    It provides indices to quickly compute InsnSchemes that fulfill constraints
    given as AbstractFeatures through the `compute_feasible_schemes` method and
    it knows how to initialize abstract features.

    Special feature names:
        - exact_scheme
        - present
        - mnemonic
    """

    not_indexed = {'exact_scheme', 'present'}

    def __init__(self, iwho_ctx, feature_config):
        """
        [ (key, kind), ... ]
        This is a list and not a dictionary since order matters: indices will
        be queried according to the order of the feature_config. Placing
        features that filter more fine-grained earlier should therefore be
        better for the running time.
        """
        self.iwho_ctx = iwho_ctx
        self.feature_config = feature_config

        self.index_order = [ key for key, kind in feature_config if key not in self.not_indexed ]
        self.feature_indices = dict()
        self._build_index()

    def _build_index(self):
        # add indices for all the relevant features
        for key, kind in self.feature_config:
            if key in self.not_indexed or key == "mnemonic":
                # No index needed, either because we don't use one or, in
                # the case of the mnemonic, because it is already indexed
                # in the iwho_ctx.
                continue
            self.feature_indices[key] = defaultdict(list)

        # fill the indices with all relevant instructions
        for ischeme in self.iwho_ctx.filtered_insn_schemes:
            insn_features = self.extract_features(ischeme)
            for key, kind in self.feature_config:
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
                else:
                    assert False, f"unknown feature kind for key {key}: {kind}"

    def init_abstract_features(self):
        res = dict()
        for key, kind in self.feature_config:
            if kind == "singleton":
                absval = SingletonAbstractFeature()
            elif kind == "subset":
                absval = SubSetAbstractFeature()
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
            mnemonic = value.val
            return self.iwho_ctx.mnemonic_to_insn_schemes[mnemonic]

        index = self.feature_indices[feature_key]

        if isinstance(value, SubSetAbstractFeature):
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
        res = {'present': True}
        remaining_features.discard('present')
        res['exact_scheme'] = ischeme
        remaining_features.discard('exact_scheme')
        res['mnemonic'] = self.iwho_ctx.extract_mnemonic(ischeme)
        remaining_features.discard('mnemonic')

        opschemes = []
        for k, opscheme in ischeme.explicit_operands.items():
            opschemes.append(str(opscheme))
        for opscheme in ischeme.implicit_operands:
            opschemes.append(str(opscheme))
        res['opschemes'] = opschemes
        remaining_features.discard('opschemes')


        from_scheme = self.iwho_ctx.get_features(ischeme)
        for key in remaining_features:
            if from_scheme is None or len(from_scheme) == 0:
                res[key] = None
                continue
            entry = from_scheme[0]
            res[key] = entry.get(key, None)

        return res

