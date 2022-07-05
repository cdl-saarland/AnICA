""" Methods to configure and compute when groups of throughput predictions for
a basic block are interesting.
"""

import math
from typing import Sequence

import iwho

from iwho.configurable import ConfigMeta

class InterestingnessMetric(metaclass=ConfigMeta):
    """ This class decides when a group of predictor results are interesting.

    Although not a common usecase (and not well-tested), these metrics should
    work for any number of predictors under test, not only for 2.
    """

    config_options = dict(
        min_interestingness = (0.5,
            'the interestingness of an experiment must be at least that high '
            'to be considered interesting'),
        mostly_interesting_ratio = (1.0,
            'at least this ratio of a batch of experiments must be interesting '
            'for it to be considered mostly interesting.'),
        invert_interestingness = (False,
            'if this is true, consider exactly those cases interesting that '
            'would not be interesting with the other settings.'),
        use_absolute_difference = (False,
            'if true, consider bbs interesiting iff the absolute difference '
            'between the results exceeds the min_interestingness value.'),
    )

    def __init__(self, config):
        self.configure(config)

        self.predmanager = None

    def set_predmanager(self, predmanager):
        self.predmanager = predmanager

    def compute_interestingness(self, eval_res):
        """ Compute the interestingness of a number of evaluation results.

        If `use_absolute_difference` is not given:
            Compute a (symmetric) relative difference between the throughputs.
        If it is:
            Compute the absolute difference between the largest and the
            smallest value.
        If it would be impossible to compute the respective value, return
        infinity to indicate maximally interesting results.
        """
        if any((v.get('TP', None) is None or v.get('TP', -1.0) < 0 for k, v in eval_res.items())):
            # errors are always interesting
            return math.inf
        values = [v['TP'] for k, v in eval_res.items()]
        divisor = sum(values)
        if divisor <= 0.001:
            # divisions by zero here are suspicious
            return math.inf
        abs_error = max(values) - min(values)

        if self.use_absolute_difference:
            return abs_error

        rel_error = (abs_error / divisor) * len(values)
        # This is the difference between minimum and maximum, divided by the
        # average.
        return rel_error

    def is_interesting(self, eval_res) -> bool:
        normally_interesting = (self.compute_interestingness(eval_res) >= self.min_interestingness)

        if self.invert_interestingness:
            return not normally_interesting

        return normally_interesting

    def filter_interesting(self, bbs: Sequence[iwho.BasicBlock]) -> Sequence[iwho.BasicBlock]:
        """ Given a list of concrete BasicBlocks, evaluate their
        interestingness and return the list of interesting ones.
        """
        assert self.predmanager is not None

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

