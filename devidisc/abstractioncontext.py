""" TODO document
"""

from .abstractblock import *
from .insnfeaturemanager import InsnFeatureManager
from .interestingness import InterestingnessMetric
from .iwho_augmentation import IWHOAugmentation
from .jsonrefs import JSONReferenceManager
from .predmanager import PredictorManager

class DiscoveryConfig:
    def __init__(self):
        # TODO
        self.discovery_batch_size = 100
        self.generalization_batch_size = 100

class AbstractionContext:
    """ An instance of the Context pattern to collect and manage the necessary
    objects for performing a deviation discovery campaign.
    """

    def __init__(self, iwho_ctx, predmanager=None):
        # TODO param
        index_config = [
            ('exact_scheme', 'singleton'),
            ('present', 'singleton'),
            ('mnemonic', 'singleton'),
            # ('skl_uops', 'subset'),
            ('opschemes', 'subset'),
            ('category', 'singleton'),
            ('extension', 'singleton'),
            ('isa-set', 'singleton'),
        ]

        self.iwho_ctx = iwho_ctx

        self.iwho_augmentation = IWHOAugmentation(iwho_ctx)

        self.insn_feature_manager = InsnFeatureManager(iwho_ctx, index_config)

        self.predmanager = predmanager

        self.interestingness_metric = InterestingnessMetric()
        self.interestingness_metric.set_predmanager(self.predmanager)

        self.discovery_cfg = DiscoveryConfig()

        self.json_ref_manager = JSONReferenceManager(iwho_ctx)


