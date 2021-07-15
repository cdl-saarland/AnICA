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

class DiscoveryConfig(metaclass=ConfigMeta):
    config_options = dict(
        discovery_batch_size = (100,
            'the number of basic blocks to sample at a time when looking for '
            'new interesting blocks'),
        generalization_batch_size = (100,
            'the number of basic blocks to sample when validating that an '
            'abstract block is still interesting'),
    )

    def __init__(self, config):
        self.configure(config)


class AbstractionContext:
    """ An instance of the Context pattern to collect and manage the necessary
    objects for performing a deviation discovery campaign.
    """

    def __init__(self, config, *, iwho_ctx=None, predmanager=None):

        if iwho_ctx is None:
            assert False, "TODO!"

        self.iwho_ctx = iwho_ctx

        self.iwho_augmentation = IWHOAugmentation(self.iwho_ctx)
        self.json_ref_manager = JSONReferenceManager(self.iwho_ctx)


        ifm_config = config.get('insn_feature_manager', {})
        self.insn_feature_manager = InsnFeatureManager(self.iwho_ctx, ifm_config)

        self.interestingness_metric = None
        interestingness_config = config.get('interestingness', {})
        if interestingness_config is not None:
            self.interestingness_metric = InterestingnessMetric(interestingness_config)

        self.discovery_cfg = None
        discovery_config = config.get('discovery', {})
        if discovery_config is not None:
            self.discovery_cfg = DiscoveryConfig(discovery_config)

        self.measurement_db = None
        measurementdb_config = config.get('measurement_db', {})
        if measurementdb_config is not None:
            self.measurement_db = MeasurementDB(measurementdb_config)

        if predmanager is not None:
            self.set_predmanager(predmanager)


    def set_predmanager(self, predmanager):
        self.interestingness_metric.set_predmanager(predmanager)

    @staticmethod
    def get_default_config():
        res = dict()
        res['insn_feature_manager'] = InsnFeatureManager.get_default_config()
        res['interestingness_metric'] = InterestingnessMetric.get_default_config()
        res['discovery'] = DiscoveryConfig.get_default_config()
        res['measurement_db'] = MeasurementDB.get_default_config()

        return res

    def get_config(self):
        res = dict()
        res['insn_feature_manager'] = self.insn_feature_manager.get_config()

        if self.interestingness_metric is None:
            res['interestingness_metric'] = None
        else:
            res['interestingness_metric'] = self.interestingness_metric.get_config()

        if self.discovery_cfg is None:
            res['discovery'] = None
        else:
            res['discovery'] = self.discovery_cfg.get_config()

        if self.measurement_db is None:
            res['measurement_db'] = None
        else:
            res['measurement_db'] = self.measurement_db.get_config()

        return res


