""" Collection of global, configurable objects that AnICA needs.

The center is the `AbstractionContext` which encapsulates all such objects.
It basically covers all the configuration options specified in an abstraction
config.
"""

from copy import deepcopy

from .abstractblock import *
from .insnfeaturemanager import InsnFeatureManager
from .interestingness import InterestingnessMetric
from .iwho_augmentation import IWHOAugmentation
from .jsonrefs import JSONReferenceManager
from iwho.predictors.measurementdb import MeasurementDB
from iwho.predictors.predictor_manager import PredictorManager


from iwho.configurable import ConfigMeta

import iwho

class DiscoveryConfig(metaclass=ConfigMeta):
    """ Configuration options for the discovery and generalization algorithm.
    """
    config_options = dict(
        discovery_batch_size = (20,
            'the number of basic blocks to sample at a time when looking for '
            'new interesting blocks'),
        discovery_possible_block_lengths = (list(range(1, 5)),
            'the different options for allowed block lengths for sampling. '
            'Duplicates are possible and increase the likelyhood.'),
        generalization_batch_size = (100,
            'the number of basic blocks to sample when validating that an '
            'abstract block is still interesting'),
        generalization_strategy = ([['max_benefit', 1], ['random', 3]],
            'the strategy to use for selecting expansions during generalization. '
            'This should be a list of ["<strategy>", <N>] pairs, where each '
            'strategy is tried N times (with a different random state). '
            'Strategy options are: "random", "max_benefit"'),
    )

    def __init__(self, config):
        self.configure(config)


class SamplingConfig(metaclass=ConfigMeta):
    """ Configuration options for the basic block sampling process.
    """
    config_options = dict(
            wrap_in_loop = (False,
                'if true, enclose the sampled basic blocks with a simple loop '
                'before using them if possible (It wouldn\'t be possible if '
                'the predictor does not support this, as is the case e.g. with '
                'measuring predictors like nanoBench.)'
            ),
        )

    def __init__(self, config):
        self.configure(config)

class AbstractionContext:
    """ An instance of the Context pattern to collect and manage the necessary
    objects for performing an AnICA discovery campaign.
    """

    def __init__(self, config, restrict_to_insns_for=None):
        """
        `restrict_to_insns_for`: If a list of predictor keys is provided, the
        iwho context will be restricted to instructions that are supported by
        all of these predictors (additionally to restrictions specified in the
        iwho config).
        """

        discovery_config = config.get('discovery', {})
        self.discovery_cfg = DiscoveryConfig(discovery_config)

        sampling_config = config.get('sampling', {})
        self.sampling_cfg = SamplingConfig(sampling_config)

        self.interestingness_metric = None
        interestingness_config = config.get('interestingness_metric', {})
        if interestingness_config is not None:
            self.interestingness_metric = InterestingnessMetric(interestingness_config)

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

        iwho_cfg_dict = deepcopy(config.get('iwho', {}))

        if restrict_to_insns_for is not None:
            # We need to do this here, because we need to add the
            # filters before we create the insn_feature_manager. Creation of
            # that will already include all insn schemes that are currently not
            # filtered away for building its indices.
            filter_list = list(iwho_cfg_dict.get('filters', []))
            for f in self.predmanager.get_insn_filter_files(restrict_to_insns_for):
                filter_list.append({'kind': 'blacklist', 'file_path': str(f)})
            iwho_cfg_dict['filters'] = filter_list

        self.iwho_cfg = iwho.Config(iwho_cfg_dict)
        iwho_ctx = self.iwho_cfg.context
        self.iwho_ctx = iwho_ctx

        self.iwho_augmentation = IWHOAugmentation(self.iwho_ctx)
        self.json_ref_manager = JSONReferenceManager(self.iwho_ctx)


        ifm_config = config.get('insn_feature_manager', {})
        self.insn_feature_manager = InsnFeatureManager(self.iwho_ctx, ifm_config)

    @staticmethod
    def get_default_config():
        res = dict()
        res['insn_feature_manager'] = InsnFeatureManager.get_default_config()
        res['iwho'] = iwho.Config.get_default_config()
        res['interestingness_metric'] = InterestingnessMetric.get_default_config()
        res['discovery'] = DiscoveryConfig.get_default_config()
        res['sampling'] = SamplingConfig.get_default_config()
        res['measurement_db'] = MeasurementDB.get_default_config()
        res['predmanager'] = PredictorManager.get_default_config()

        return res

    def get_config(self, skip_doc=False):
        res = dict()
        res['insn_feature_manager'] = self.insn_feature_manager.get_config(skip_doc=skip_doc)

        res['iwho'] = self.iwho_cfg.get_config(skip_doc=skip_doc)

        if self.interestingness_metric is None:
            res['interestingness_metric'] = None
        else:
            res['interestingness_metric'] = self.interestingness_metric.get_config(skip_doc=skip_doc)

        res['discovery'] = self.discovery_cfg.get_config(skip_doc=skip_doc)
        res['sampling'] = self.sampling_cfg.get_config(skip_doc=skip_doc)

        if self.measurement_db is None:
            res['measurement_db'] = None
        else:
            res['measurement_db'] = self.measurement_db.get_config(skip_doc=skip_doc)

        if self.predmanager is None:
            res['predmanager'] = None
        else:
            res['predmanager'] = self.predmanager.get_config(skip_doc=skip_doc)

        return res


