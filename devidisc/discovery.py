
from copy import deepcopy
import textwrap

import logging
logger = logging.getLogger(__name__)

def discover(acfg: AbstractionConfig, start_point: AbstractBlock):
    ctx = acfg.ctx

    discoveries = []

    logger.info("starting discovery loop")
    while True:
        # TODO some reasonable termination criterion, e.g. time, #discoveries, ...

        # sample a batch of blocks
        concrete_bbs = [ start_point.sample() for x in range(acfg.discovery_batch_size) ]

        interesting_bbs = acfg.filter_interesting(concrete_bbs)

        logger.info(f"  {len(interesting_bbs)} out of {len(concrete_bbs)} ({100 * len(interesting_bbs) / len(concrete_bbs):.2f}%) are interesting")

        # for each interesting one:
        #   - check if it is already subsumed by a discovery (TODO depending on what is faster, we might want to do this before checking for interestingness)
        #   - if not: generalize
        for bb in interesting_bbs:
            abstracted_bb = AbstractBlock(acfg, sampled_block)
            for d in discoveries:
                if d.subsumes(abstracted_block):
                    logger.info("  existing discovery already subsumes the block:" + textwrap.indent(str(d), 4*' '))
                    # TODO continue outer

            generalize(acfg, abstracted_bb)

            logger.info("  adding new discovery:" + textwrap.indent(str(abstracted_bb), 4*' '))
            discoveries.append(abstracted_bb)
            dump_discovery(abstracted_bb) # TODO we should keep track of witnesses for interestingness here


def generalize(acfg: AbstractionConfig, abstract_bb: AbstractBlock):
    logger.info("  generalizing BB:" + textwrap.indent(str(abstract_bb), 4*' ') )

    # check if sampling from abstract_bb leads to mostly interesting blocks
    concrete_bbs = [ abstract_bb.sample() for x in range(acfg.generalization_batch_size) ]

    interesting = acfg.is_mostly_interesting(concrete_bbs)

    if not interesting:
        logger.info("  samples from the BB are not uniformly interesting!")

    # a set of tokens representing subcomponents of the abstract basic block
    # that we tried to expand but did not yield interesing results
    expansion_limit_tokens = set()

    while True: # TODO add a termination condition, e.g. based on a budget adjusted by potential usefulness? At least a fixed upper bound should exist, so that a bug in the expansion cannot lead to endless loops
        # create a deepcopy to expand
        working_copy = deepcopy(abstract_bb)

        # expand some component
        new_token = working_copy.expand(expansion_limit_tokens)
        if new_token is None:
            # we have hit top
            logger.info("  no more component left for expansion")
            break

        logger.info(f"  evaluating samples for expanding {new_token}")

        # sample a number of concrete blocks from it
        concrete_bbs = [ working_copy.sample() for x in range(acfg.generalization_batch_size) ]

        # if they are mostly interesting, use the copy as new abstract block
        # one could also join the concrete bbs in instead
        interesting = acfg.is_mostly_interesting(concrete_bbs)

        if interesting:
            logger.info(f"  samples for expanding {new_token} are interesting, adjusting BB")
            abstract_bb = working_copy
        else:
            logger.info(f"  samples for expanding {new_token} are not interesting, discarding")
            # make sure that we don't try that token again
            expansion_limit_tokens.add(new_token)

    logger.info("  generalization done.")
    return abstract_bb


