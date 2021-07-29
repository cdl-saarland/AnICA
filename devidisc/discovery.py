
from typing import Optional, Sequence
from copy import deepcopy
from datetime import datetime, timedelta
import json
import math
import os
import random
import shutil
import textwrap
from pathlib import Path

from .abstractblock import AbstractBlock, SamplingError
from .abstractioncontext import AbstractionContext
from .satsumption import check_subsumed
from .witness import WitnessTrace

import logging
logger = logging.getLogger(__name__)

def sample_block_list(abstract_bb, num):
    """Try to sample `num` samples from abstract_bb

    If samples fail, the result will have fewer entries.
    """
    concrete_bbs = []
    for x in range(num):
        try:
            concrete_bbs.append(abstract_bb.sample())
        except SamplingError as e:
            logger.info("a sample failed: {e}")
    return concrete_bbs


def discover(actx: AbstractionContext, termination={}, start_point: Optional[AbstractBlock] = None, out_dir: Optional[Path]=None):
    """ Run the central deviation discovery algorithm.

    If an AbstractBlock is given as `start_point`, discovery will only sample
    from it for finding new starting points for generalization. Otherwise, a
    TOP AbstractBlock is used for this purpose. Generalization is not
    restricted through this parameter.

    If an `out_dir` is specified, reports and witnesses are written there for
    further evaluation.

    `termination` is expected to be a dictionary that may have some of the
    following keys set:
        - hours, minutes, seconds: if any of those are set, they are added
          together and considered as a soft timeout (i.e. once a batch is
          complete and at least as much time has passed since the start of the
          campaign, terminate).
        - num_batches: if this is set to an int N, at most N discovery batches
          are run.
        - num_discoveries: if this is set to an int N, terminate if after a
          discovery batch N or more total discoveries have been found
    If more than one of the above is set, this method terminates when the first
    of them triggers. If none are set, this procedure will run indefinitely.
    """

    if out_dir is not None:
        witness_dir = out_dir / "witnesses"
        os.makedirs(witness_dir)

    discovery_batch_size = actx.discovery_cfg.discovery_batch_size

    # TODO allow previous ones
    discoveries = []

    max_num_batches = math.inf
    max_num_discoveries = math.inf
    max_seconds_passed = math.inf

    if 'num_batches' in termination.keys():
        max_num_batches = termination['num_batches']

    if 'num_discoveries' in termination.keys():
        max_num_discoveries = termination['num_discoveries']

    if any(map(lambda x: x in termination.keys(), ['hours', 'minutes', 'seconds'])):
        max_seconds_passed = termination.get('hours', 0) * 3600
        max_seconds_passed += termination.get('minutes', 0) * 60
        max_seconds_passed += termination.get('seconds', 0)

    curr_num_batches = 0
    curr_num_discoveries = 0
    start_time = datetime.now()
    curr_seconds_passed = 0

    total_sampled = 0
    per_batch_stats = []

    report = dict()
    report['num_batches'] = curr_num_batches
    report['num_total_sampled'] = total_sampled
    report['num_discoveries'] = curr_num_discoveries
    report['seconds_passed'] = curr_seconds_passed
    report['per_batch_stats'] = per_batch_stats

    def write_report():
        if out_dir is not None:
            report_file = out_dir / 'report.json'
            if report_file.exists():
                # backup previous version, for safety
                shutil.copy(report_file, out_dir / 'report.bak.json')
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)

    logger.info("starting discovery loop")
    while True:
        # check if we should terminate for some reason
        curr_seconds_passed = (datetime.now() - start_time).total_seconds()
        report['seconds_passed'] = curr_seconds_passed
        write_report()

        if curr_num_batches >= max_num_batches:
            logger.info("terminating discovery loop: maximal number of batches explored")
            break

        if curr_num_discoveries >= max_num_discoveries:
            logger.info("terminating discovery loop: maximal number of discoveries found")
            break

        if curr_seconds_passed >= max_seconds_passed:
            logger.info("terminating discovery loop: time budget exceeded")
            break

        logger.info(f"  starting batch no. {curr_num_batches}")

        per_batch_entry = dict()
        per_batch_stats.append(per_batch_entry)

        batch_start_time = datetime.now()

        # sample a batch of blocks
        start_sampling_time = datetime.now()

        if start_point is None:
            l = random.choice(actx.discovery_cfg.discovery_possible_block_lengths)
            sample_universe = AbstractBlock.make_top(actx, l)
        else:
            sample_universe = start_point

        concrete_bbs = sample_block_list(sample_universe, discovery_batch_size)
        sampling_time = ((datetime.now() - start_sampling_time) / timedelta(microseconds=1)) / 1000
        total_sampled += len(concrete_bbs)
        report['num_total_sampled'] = total_sampled
        per_batch_entry['num_sampled'] = len(concrete_bbs)
        per_batch_entry['sampling_time'] = sampling_time

        # TODO we might want to avoid generating the result_ref here, to allow more parallelism
        start_interestingness_time = datetime.now()
        interesting_bbs, result_ref = actx.interestingness_metric.filter_interesting(concrete_bbs)
        interestingness_time = ((datetime.now() - start_interestingness_time) / timedelta(microseconds=1)) / 1000
        per_batch_entry['num_interesting'] = len(interesting_bbs)
        per_batch_entry['interestingness_time'] = interestingness_time

        logger.info(f"  {len(interesting_bbs)} out of {len(concrete_bbs)} ({100 * len(interesting_bbs) / len(concrete_bbs):.2f}%) are interesting")

        per_sample_stats = []
        per_batch_entry['per_interesting_sample_stats'] = per_sample_stats
        num_subsumed = 0
        per_batch_entry['num_interesting_subsumed'] = num_subsumed
        # for each interesting one:
        for idx, bb in enumerate(interesting_bbs):
            # First, try to prune some unnecessary instructions.
            # doing that before subsumption checking has several benefits:
            #   - The problem size for the subsumption checker is reduced.
            #   - If bb has a pattern already captured by discoveries, but
            #     additionally even more harmful patterns, there is a chance
            #     that such a new pattern is found because the already
            #     discovered ones are pruned away.
            min_bb = minimize(actx, bb)

            # check if the block is already subsumed by a discovery
            stats = dict()
            per_sample_stats.append(stats)

            start_subsumption_time = datetime.now()
            already_found = False
            for d in discoveries:
                is_subsumed = check_subsumed(bb=bb, ab=d)
                if is_subsumed:
                    logger.info("  existing discovery already subsumes the block:" + textwrap.indent(str(d), 4*' '))
                    already_found = True
            subsumption_time = ((datetime.now() - start_subsumption_time) / timedelta(microseconds=1)) / 1000
            stats['subsumption_time'] = subsumption_time
            if already_found:
                num_subsumed += 1
                per_batch_entry['num_interesting_subsumed'] = num_subsumed
                continue

            # if not: generalize
            start_generalization_time = datetime.now()

            abstracted_bb = AbstractBlock(actx, min_bb)
            generalized_bb, trace = generalize(actx, abstracted_bb)

            generalization_time = ((datetime.now() - start_generalization_time) / timedelta(microseconds=1)) / 1000
            stats['generalization_time'] = generalization_time
            stats['witness_len'] = len(trace)
            # TODO ab height

            logger.info("  adding new discovery:" + textwrap.indent(str(generalized_bb), 4*' '))
            discoveries.append(generalized_bb)
            curr_num_discoveries += 1
            report['num_discoveries'] = curr_num_discoveries

            if out_dir is not None:
                trace.dump_json(witness_dir / f'generalization_batch{curr_num_batches:03}_idx{idx:03}.json')

            write_report()

        batch_time = ((datetime.now() - batch_start_time) / timedelta(microseconds=1)) / 1000
        per_batch_entry['batch_time'] = batch_time

        logger.info(f"  done with batch no. {curr_num_batches}")
        curr_num_batches += 1
        report['num_batches'] = curr_num_batches
        write_report()

    return discoveries

def minimize(actx, concrete_bb):
    """ Try to randomly remove instructions from the concrete basic block while
    preserving its interestingness.

    The result will be a concrete basic block of the same or shorter length.
    """

    num_insns = len(concrete_bb.insns)
    # get a list of all indices into the bb with a random order.
    order = list(range(num_insns))
    random.shuffle(order)

    for i in range(num_insns):
        if len(concrete_bb) <= 1:
            # we don't want empty blocks
            break

        curr_idx = order.pop()
        curr_insns = concrete_bb.insns[:]
        del curr_insns[curr_idx]
        curr_bb = actx.iwho_ctx.make_bb(curr_insns)
        interesting, result_ref = actx.interestingness_metric.is_mostly_interesting([curr_bb])
        if interesting:
            # take the updated (shorter) bb
            concrete_bb = curr_bb
            # Since we removed an index from the block, we need to adjust our
            # order by decrementing all remaining indices that are larger than
            # the current one.
            #
            # consider the example of the order [2, 4, 1, 3, 0] here:
            # bb index:  0 1 2 3 4
            # bb before: A B C D E
            #            | |  / /
            # bb after:  A B D E
            # after removing C at index 2, we need to adjust the order to [3,
            # 1, 2, 0] to refer to the same instructions

            order = list(map(lambda x: x - 1 if x > curr_idx else x, order))

    return concrete_bb


def generalize(actx: AbstractionContext, abstract_bb: AbstractBlock):
    """ Generalize the given AbstractBlock while presering interestingness.

    This means that we try to adjust it such that it represents a maximal
    number of concrete blocks that are still mostly interesting.
    """
    generalization_batch_size = actx.discovery_cfg.generalization_batch_size

    logger.info("  generalizing BB:" + textwrap.indent(str(abstract_bb), 4*' ') )

    trace = WitnessTrace(abstract_bb)

    # check if sampling from abstract_bb leads to mostly interesting blocks
    concrete_bbs = sample_block_list(abstract_bb, generalization_batch_size)
    assert len(concrete_bbs) > 0

    interesting, result_ref = actx.interestingness_metric.is_mostly_interesting(concrete_bbs)

    if not interesting:
        logger.info("  samples from the BB are not uniformly interesting!")
        trace.add_termination(comment="Samples from the starting block are not interesting!", measurements=result_ref)
        return abstract_bb, trace

    # a set of expansions that we tried to apply but did not yield interesting
    # results
    do_not_expand = set()

    while True: # TODO add a termination condition, e.g. based on a budget adjusted by potential usefulness? At least a fixed upper bound should exist, so that a bug in the expansion cannot lead to endless loops
        # create a deepcopy to expand
        working_copy = deepcopy(abstract_bb)

        # expand some component
        expansions = working_copy.get_possible_expansions()

        # don't use one that we already tried and failed
        expansions = [ (exp, benefit) for (exp, benefit) in expansions if exp not in do_not_expand ]

        if len(expansions) == 0:
            # we have hit the most general point possible
            logger.info("  no more component left for expansion")
            break

        # choose the expansion that maximizes sampling freedom
        expansions.sort(key=lambda x: x[1], reverse=True)

        chosen_expansion, benefit = expansions[0]
        working_copy.apply_expansion(chosen_expansion)

        logger.info(f"  evaluating samples for expanding {chosen_expansion} (benefit: {benefit})")

        # sample a number of concrete blocks from it
        concrete_bbs = sample_block_list(working_copy, generalization_batch_size)

        # if they are mostly interesting, use the copy as new abstract block
        # one could also join the concrete bbs in instead
        interesting, result_ref = actx.interestingness_metric.is_mostly_interesting(concrete_bbs)

        if interesting:
            logger.info(f"  samples for expanding {chosen_expansion} are interesting, adjusting BB")
            trace.add_taken_expansion(chosen_expansion, result_ref)
            abstract_bb = working_copy
        else:
            logger.info(f"  samples for expanding {chosen_expansion} are not interesting, discarding")
            trace.add_nontaken_expansion(chosen_expansion, result_ref)
            # make sure that we don't try that expansion again
            do_not_expand.add(chosen_expansion)

    trace.add_termination(comment="No more expansions remain.", measurements=None)

    logger.info("  generalization done.")
    return abstract_bb, trace


