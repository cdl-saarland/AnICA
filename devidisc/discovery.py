
from copy import deepcopy
import textwrap

from .abstractblock import AbstractBlock, SamplingError
from .abstractionconfig import AbstractionConfig
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


def discover(acfg: AbstractionConfig, start_point: AbstractBlock):
    ctx = acfg.ctx

    discoveries = []

    logger.info("starting discovery loop")
    while True:
        # TODO some reasonable termination criterion, e.g. time, #discoveries, ...

        # sample a batch of blocks
        concrete_bbs = sample_block_list(start_point, acfg.discovery_batch_size)

        # TODO we might want to avoid generating the result_ref here, to allow more parallelism
        interesting_bbs, result_ref = acfg.filter_interesting(concrete_bbs)

        logger.info(f"  {len(interesting_bbs)} out of {len(concrete_bbs)} ({100 * len(interesting_bbs) / len(concrete_bbs):.2f}%) are interesting")

        # for each interesting one:
        for bb in interesting_bbs:
            abstracted_bb = AbstractBlock(acfg, sampled_block)
            # check if it is already subsumed by a discovery
            # (TODO depending on what is faster, we might want to do this before checking for interestingness)

            already_found = False
            for d in discoveries:
                if d.subsumes(abstracted_block):
                    logger.info("  existing discovery already subsumes the block:" + textwrap.indent(str(d), 4*' '))
                    already_found = True
            if already_found:
                continue

            # if not: generalize
            generalized_bb, trace = generalize(acfg, abstracted_bb)

            logger.info("  adding new discovery:" + textwrap.indent(str(generalized_bb), 4*' '))
            discoveries.append(generalalized_bb)
            dump_discovery(generalized_bb, trace)

def generalize(acfg: AbstractionConfig, abstract_bb: AbstractBlock):
    logger.info("  generalizing BB:" + textwrap.indent(str(abstract_bb), 4*' ') )

    trace = WitnessTrace(abstract_bb)

    # check if sampling from abstract_bb leads to mostly interesting blocks
    concrete_bbs = sample_block_list(abstract_bb, acfg.generalization_batch_size)

    interesting, result_ref = acfg.is_mostly_interesting(concrete_bbs)

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
        concrete_bbs = sample_block_list(working_copy, acfg.generalization_batch_size)

        # if they are mostly interesting, use the copy as new abstract block
        # one could also join the concrete bbs in instead
        interesting, result_ref = acfg.is_mostly_interesting(concrete_bbs)

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


