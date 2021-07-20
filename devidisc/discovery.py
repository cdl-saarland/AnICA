
from copy import deepcopy
from datetime import datetime
import math
import os
import textwrap

from .abstractblock import AbstractBlock, SamplingError
from .abstractioncontext import AbstractionContext
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


def discover(actx: AbstractionContext, termination={}, start_point: AbstractBlock = None, out_dir=None):
    """ TODO document

    `termination` is expected to be a dictionary with some of the following
    keys set:
        - hours, minutes, seconds: if any of those are set, they are added
          together and considered as a soft timeout (i.e. once a batch is
          complete and at least as much time has passed since the start of the
          campaign, terminate).
        - num_batches: if this is set to an int N, at most N discovery batches
          are run.
        - num_discoveries: if this is set to an int N, terminate if after a
          discovery batch N or more total discoveries have been found
    If more than one of the above is set, this method terminates when the first
    of them triggers.
    """

    if start_point is None:
        start_point = AbstractBlock.make_top(actx, actx.discovery_cfg.discovery_max_block_len)

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

    logger.info("starting discovery loop")
    while True:
        # check if we should terminate for some reason
        if curr_num_batches >= max_num_batches:
            logger.info("terminating discovery loop: maximal number of batches explored")
            break

        if curr_num_discoveries >= max_num_discoveries:
            logger.info("terminating discovery loop: maximal number of discoveries found")
            break

        curr_seconds_passed = (datetime.now() - start_time).total_seconds()
        if curr_seconds_passed >= max_seconds_passed:
            logger.info("terminating discovery loop: time budget exceeded")
            break

        # sample a batch of blocks
        concrete_bbs = sample_block_list(start_point, discovery_batch_size)

        # TODO we might want to avoid generating the result_ref here, to allow more parallelism
        interesting_bbs, result_ref = actx.interestingness_metric.filter_interesting(concrete_bbs)

        logger.info(f"  {len(interesting_bbs)} out of {len(concrete_bbs)} ({100 * len(interesting_bbs) / len(concrete_bbs):.2f}%) are interesting")

        # for each interesting one:
        for idx, bb in enumerate(interesting_bbs):
            abstracted_bb = AbstractBlock(actx, bb)
            # check if it is already subsumed by a discovery
            # (TODO depending on what is faster, we might want to do this before checking for interestingness)

            already_found = False
            for d in discoveries:
                if d.subsumes(abstracted_bb):
                    logger.info("  existing discovery already subsumes the block:" + textwrap.indent(str(d), 4*' '))
                    already_found = True
            if already_found:
                continue

            # if not: generalize
            generalized_bb, trace = generalize(actx, abstracted_bb)

            logger.info("  adding new discovery:" + textwrap.indent(str(generalized_bb), 4*' '))
            discoveries.append(generalized_bb)
            curr_num_discoveries += 1

            if out_dir is not None:
                trace.dump_json(witness_dir / f'generalization_batch{curr_num_batches:03}_idx{idx:03}.json')

        curr_num_batches += 1

    # TODO report stats
    # curr_num_batches
    # curr_num_discoveries
    # curr_seconds_passed
    # ratio of interesing discoveries

    return discoveries


def generalize(actx: AbstractionContext, abstract_bb: AbstractBlock):
    generalization_batch_size = actx.discovery_cfg.generalization_batch_size

    logger.info("  generalizing BB:" + textwrap.indent(str(abstract_bb), 4*' ') )

    trace = WitnessTrace(abstract_bb)

    # check if sampling from abstract_bb leads to mostly interesting blocks
    concrete_bbs = sample_block_list(abstract_bb, generalization_batch_size)

    interesting, result_ref = actx.interestingness_metric.is_mostly_interesting(concrete_bbs)

    if not interesting:
        logger.info("  samples from the BB are not uniformly interesting!")
        trace.add_termination(comment="Samples from the starting block are not interesting!", measurements=result_ref)
        return abstract_bb, trace

    # a set of expansions that we tried to apply but did not yield interesing
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


