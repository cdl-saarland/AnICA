""" TODO document
"""

from .abstractblock import *
from .insnfeaturemanager import InsnFeatureManager
from .interestingness import InterestingnessMetric
from .iwho_augmentation import IWHOAugmentation
from .jsonrefs import JSONReferenceManager
from .measurementdb import MeasurementDB
from .predmanager import PredictorManager


from .configurable import ConfigMeta

import iwho

class DiscoveryConfig(metaclass=ConfigMeta):
    config_options = dict(
        discovery_batch_size = (100,
            'the number of basic blocks to sample at a time when looking for '
            'new interesting blocks'),
        discovery_max_block_len = (8,
            'the maximal number of instructions in blocks sampled for '
            'discovering fresh interesting blocks'),
        generalization_batch_size = (100,
            'the number of basic blocks to sample when validating that an '
            'abstract block is still interesting'),
        use_sat_subsumption = (False,
            'use a more elaborate sat-based subsumption checking algorithm to '
            'find out whether discoveries have already been seen'),
    )

    def __init__(self, config):
        self.configure(config)


class SamplingConfig(metaclass=ConfigMeta):
    config_options = dict(
        skip_insn_bias = (0.5,
            'the likelyhood in [0.0, 1.0] to skip an instruction whose \'present\' result is TOP when sampling (1.0 will always skip, 0.0 will always take an instruction)'
            ),
    )

    def __init__(self, config):
        self.configure(config)


class IWHOConfig(metaclass=ConfigMeta):
    config_options = dict(
        context_specifier = ('x86_uops_info',
            'identifier for the IWHO context to use'
            ),
        filters = (['no_cf', 'with_measurements:SKL'],
            'a list of filters to restrict the InsnSchemes used for sampling'
            ),
    )

    def __init__(self, config):
        self.configure(config)

    def create_context(self):
        iwho_ctx = iwho.get_context(self.context_specifier)
        for f in self.filters:
            key, *args = f.split(':')
            if key == 'no_cf':
                iwho_ctx.push_filter(iwho.Filters.no_control_flow)
                continue
            if key == 'with_measurements':
                for uarch in args:
                    uarch_filter = lambda scheme, ctx, uarch_name=uarch: (ctx.get_features(scheme) is not None
                            and uarch_name in ctx.get_features(scheme)[0]["measurements"])
                    iwho_ctx.push_filter(uarch_filter)
                continue

        return iwho_ctx


class AbstractionContext:
    """ An instance of the Context pattern to collect and manage the necessary
    objects for performing a deviation discovery campaign.
    """

    def __init__(self, config):

        self.iwho_cfg = IWHOConfig(config.get('iwho', {}))
        iwho_ctx = self.iwho_cfg.create_context()
        self.iwho_ctx = iwho_ctx

        self.iwho_augmentation = IWHOAugmentation(self.iwho_ctx)
        self.json_ref_manager = JSONReferenceManager(self.iwho_ctx)


        ifm_config = config.get('insn_feature_manager', {})
        self.insn_feature_manager = InsnFeatureManager(self.iwho_ctx, ifm_config)

        self.interestingness_metric = None
        interestingness_config = config.get('interestingness', {})
        if interestingness_config is not None:
            self.interestingness_metric = InterestingnessMetric(interestingness_config)

        discovery_config = config.get('discovery', {})
        self.discovery_cfg = DiscoveryConfig(discovery_config)

        sampling_config = config.get('sampling', {})
        self.sampling_cfg = SamplingConfig(sampling_config)

        self.measurement_db = None
        measurementdb_config = config.get('measurement_db', {})
        if measurementdb_config is not None:
            self.measurement_db = MeasurementDB(measurementdb_config)

        self.predmanager = None
        predman_config = config.get('predmanager', {})
        if predman_config is not None:
            self.predmanager = PredictorManager(predman_config)
            self.interestingness_metric.set_predmanager(self.predmanager)
            if self.measurement_db is not None:
                self.predmanager.set_measurement_db(self.measurement_db)

    @staticmethod
    def get_default_config():
        res = dict()
        res['insn_feature_manager'] = InsnFeatureManager.get_default_config()
        res['iwho'] = IWHOConfig.get_default_config()
        res['interestingness_metric'] = InterestingnessMetric.get_default_config()
        res['discovery'] = DiscoveryConfig.get_default_config()
        res['sampling'] = SamplingConfig.get_default_config()
        res['measurement_db'] = MeasurementDB.get_default_config()
        res['predmanager'] = PredictorManager.get_default_config()

        return res

    def get_config(self):
        res = dict()
        res['insn_feature_manager'] = self.insn_feature_manager.get_config()

        res['iwho'] = self.iwho_cfg.get_config()

        if self.interestingness_metric is None:
            res['interestingness_metric'] = None
        else:
            res['interestingness_metric'] = self.interestingness_metric.get_config()

        res['discovery'] = self.discovery_cfg.get_config()
        res['sampling'] = self.sampling_cfg.get_config()

        if self.measurement_db is None:
            res['measurement_db'] = None
        else:
            res['measurement_db'] = self.measurement_db.get_config()

        if self.predmanager is None:
            res['predmanager'] = None
        else:
            res['predmanager'] = self.predmanager.get_config()

        return res


