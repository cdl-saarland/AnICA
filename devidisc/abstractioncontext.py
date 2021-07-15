""" TODO document
"""

from .abstractblock import *
from .insnfeaturemanager import InsnFeatureManager
from .interestingness import InterestingnessMetric
from .iwho_augmentation import IWHOAugmentation
from .jsonrefs import JSONReferenceManager
from .predmanager import PredictorManager

from .configurable import Configurable

class DiscoveryConfig(Configurable):
    def __init__(self, config):
        Configurable.__init__(self, defaults=dict(
            discovery_batch_size = (100,
                'the number of basic blocks to sample at a time when looking for new interesting blocks'),
            generalization_batch_size = (100,
                'the number of basic blocks to sample when validating that an abstract block is still interesting'),
        ), config=config)


class AbstractionContext:
    """ An instance of the Context pattern to collect and manage the necessary
    objects for performing a deviation discovery campaign.
    """

    def __init__(self, iwho_ctx, predmanager=None):

        config = {
            "insn_feature_manager": {
                "features": [
                    ["exact_scheme", "singleton"],
                    ["present", "singleton"],
                    ["mnemonic", "singleton"],
                    ["opschemes", "subset"],
                    ["category", "singleton"],
                    ["extension", "singleton"],
                    ["isa-set", "singleton"]
                ]
            },
            "discovery": {
                "discovery_batch_size": 100,
                "generalization_batch_size": 100
            }
        }

        self.iwho_ctx = iwho_ctx

        self.iwho_augmentation = IWHOAugmentation(self.iwho_ctx)

        ifm_config = config.get('insn_feature_manager', {})

        self.insn_feature_manager = InsnFeatureManager(self.iwho_ctx, ifm_config['features'])

        self.predmanager = None

        self.interestingness_metric = InterestingnessMetric()

        discovery_config = config.get('discovery', {})
        self.discovery_cfg = DiscoveryConfig(discovery_config)

        self.json_ref_manager = JSONReferenceManager(self.iwho_ctx)

        if predmanager is not None:
            self.set_predmanager(predmanager)


    def set_predmanager(self, predmanager):
        self.predmanager = predmanager
        self.interestingness_metric.set_predmanager(self.predmanager)


