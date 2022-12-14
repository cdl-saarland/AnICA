""" Implementation of the core AnICA algorithms: discovery and generalization.
"""

from typing import Optional, Sequence
from copy import deepcopy
from datetime import datetime, timedelta
import math
import os
import random
import shutil
import socket
import textwrap
from pathlib import Path

from .abstractblock import AbstractBlock, SamplingError
from .abstractioncontext import AbstractionContext
from iwho.configurable import store_json_config
from .satsumption import check_subsumed, check_subsumed_aa
from .witness import WitnessTrace

import logging
logger = logging.getLogger(__name__)

class DiscoveryError(Exception):
    """ Something went really wrong during discovery
    """
    def __init__(self, message):
        super().__init__(message)

def sample_block_list(abstract_bb, num, insn_scheme_blacklist=None, remarks=None):
    """Try to sample `num` samples from abstract_bb.

    If samples fail, at most 2*num attempts will be made to sample enough
    blocks anyway. If this is not enough, the result will have fewer samples.
    """
    if insn_scheme_blacklist is None:
        insn_scheme_blacklist = []

    try:
        sampler = abstract_bb.precompute_sampler(insn_scheme_blacklist=insn_scheme_blacklist)
    except SamplingError as e:
        logger.info(f"creating a precomputed sampler failed: {e}")
        if remarks is not None:
            remarks.append(("creating a precomputed sampler failed for this absblock:\n{}", str(abstract_bb)))
        return []

    concrete_bbs = []
    num_failed = 0
    for x in range(2 * num):
        if len(concrete_bbs) >= num:
            break
        try:
            concrete_bbs.append(sampler.sample())
        except SamplingError as e:
            logger.info(f"a sample failed: {e}")
            num_failed += 1

    if remarks is not None and num_failed > 0:
        # This means that a portion of the samples failed.
        # If it is larger than 0.5, fewer samples than required are produced.
        # If it is 1.0, no samples at all could be produced.
        fail_ratio = num_failed / (2 * num)
        remarks.append(("non-zero sampling fail ratio encountered: {}", fail_ratio))
    return concrete_bbs


def discover(actx: AbstractionContext, termination={}, start_point: Optional[AbstractBlock] = None, out_dir: Optional[Path]=None):
    """ Run the central inconsistency discovery algorithm.

    If an AbstractBlock is given as `start_point`, discovery will only sample
    from it for finding new starting points for generalization. Otherwise, a
    TOP AbstractBlock is used for this purpose. Generalization is not
    restricted through this parameter.

    If an `out_dir` is specified, reports and witnesses are written there for
    further evaluation.

    `termination` is expected to be a dictionary that may have some of the
    following keys set:
        - days, hours, minutes, seconds: if any of those are set, they are
          added together and considered as a soft timeout (i.e. once a batch is
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
        discovery_dir = out_dir / "discoveries"
        os.makedirs(witness_dir)
        os.makedirs(discovery_dir)

    discovery_batch_size = actx.discovery_cfg.discovery_batch_size

    discoveries = []

    max_num_batches = math.inf
    max_num_discoveries = math.inf
    max_seconds_passed = math.inf
    max_same_num_discoveries = math.inf

    if 'num_batches' in termination.keys():
        max_num_batches = termination['num_batches']

    if 'num_discoveries' in termination.keys():
        max_num_discoveries = termination['num_discoveries']

    if 'same_num_discoveries' in termination.keys():
        max_same_num_discoveries = termination['same_num_discoveries']

    if any(map(lambda x: x in termination.keys(), ['days', 'hours', 'minutes', 'seconds'])):
        max_seconds_passed = termination.get('days', 0) * 3600 * 24
        max_seconds_passed += termination.get('hours', 0) * 3600
        max_seconds_passed += termination.get('minutes', 0) * 60
        max_seconds_passed += termination.get('seconds', 0)

    curr_num_batches = 0
    curr_num_discoveries = 0
    start_time = datetime.now()
    curr_seconds_passed = 0

    prev_num_discoveries = -1
    same_num_discoveries_counter = 0

    total_sampled = 0
    per_batch_stats = []

    report = dict()
    report['host_pc'] = socket.gethostname()
    report['start_date'] = start_time.isoformat()
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
            store_json_config(report, report_file)

    # A set of InsnSchemes for which we already have discoveries that subsume
    # any block containing one of them. We can avoid sampling boring blocks
    # by omitting those from sampling in the discovery phase.
    insn_scheme_blacklist = set()

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

        if curr_num_discoveries == prev_num_discoveries:
            same_num_discoveries_counter += 1
        else:
            same_num_discoveries_counter = 0
            prev_num_discoveries = curr_num_discoveries

        if same_num_discoveries_counter >= max_same_num_discoveries:
            logger.info("terminating discovery loop: number of discoveries stagnated")
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

        concrete_bbs = sample_block_list(sample_universe, discovery_batch_size, insn_scheme_blacklist=insn_scheme_blacklist)
        sampling_time = ((datetime.now() - start_sampling_time) / timedelta(milliseconds=1)) / 1000
        total_sampled += len(concrete_bbs)
        report['num_total_sampled'] = total_sampled
        per_batch_entry['num_sampled'] = len(concrete_bbs)
        per_batch_entry['sampling_time'] = sampling_time

        if len(concrete_bbs) == 0:
            per_batch_entry['num_interesting'] = 0
            per_batch_entry['interestingness_time'] = 0
            per_batch_entry['per_interesting_sample_stats'] = []
            per_batch_entry['num_interesting_subsumed'] = 0
            per_batch_entry['batch_time'] = 0
            report['seconds_passed'] = (datetime.now() - start_time).total_seconds()
            write_report()

            logger.info("terminating discovery loop: failed to sample any concrete blocks")
            break

        # TODO improvement: we could avoid generating the result_ref here, to allow more parallelism
        start_interestingness_time = datetime.now()
        interesting_bbs, result_ref = actx.interestingness_metric.filter_interesting(concrete_bbs)
        interestingness_time = ((datetime.now() - start_interestingness_time) / timedelta(milliseconds=1)) / 1000
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
            subsumption_time = ((datetime.now() - start_subsumption_time) / timedelta(milliseconds=1)) / 1000
            stats['subsumption_time'] = subsumption_time
            if already_found:
                num_subsumed += 1
                per_batch_entry['num_interesting_subsumed'] = num_subsumed
                continue

            # if not: generalize
            abstracted_bb = AbstractBlock(actx, min_bb)

            gen_stats = []
            stats['per_generalization_stats'] = gen_stats

            gen_idx = 0
            good_generalizations = dict()

            for curr_strategy, num_attempts in actx.discovery_cfg.generalization_strategy:
                for x in range(num_attempts):
                    generalization_id = f'b{curr_num_batches:03}_i{idx:03}_g{gen_idx:03}'
                    gen_idx += 1

                    logger.info(f'  performing generalization {generalization_id} (strategy: {curr_strategy})')

                    gen_stat_entry = dict()
                    gen_stats.append(gen_stat_entry)

                    gen_stat_entry['id'] = generalization_id

                    working_bb = deepcopy(abstracted_bb)

                    remarks = [('generalization strategy: {}', curr_strategy) ]

                    start_generalization_time = datetime.now()
                    generalized_bb, trace, last_result_ref = generalize(actx, working_bb, strategy=curr_strategy, remarks=remarks)

                    generalization_time = ((datetime.now() - start_generalization_time) / timedelta(milliseconds=1)) / 1000
                    gen_stat_entry['generalization_time'] = generalization_time
                    gen_stat_entry['witness_len'] = len(trace)

                    already_found = False
                    subsumes = []

                    for prev_id, prev_gen_data in good_generalizations.items():
                        prev_gen = prev_gen_data['absblock']
                        if generalized_bb == prev_gen:
                            logger.info(f'  generalized to the same abstract block as {prev_id}')
                            already_found = True
                            break
                        elif check_subsumed_aa(generalized_bb, prev_gen):
                            # the old one is at least as general
                            logger.info(f'  generalized to a block subsumed by {prev_id}')
                            already_found = True
                            break
                        elif check_subsumed_aa(prev_gen, generalized_bb):
                            # the new one is more general
                            logger.info(f'  generalized to a block that subsumes {prev_id}')
                            subsumes.append(prev_id)

                    gen_stat_entry['already_found'] = already_found
                    gen_stat_entry['subsumes'] = subsumes

                    if already_found:
                        assert len(subsumes) == 0, ("A generalization has already been found, but subsumes other generalizations!")
                        # This should not be possible, since the previous
                        # instance should either have caused the subsumed one
                        # to be deleted or avoided adding it in the first
                        # place.
                        continue

                    # remove all the generalizations that this one makes obsolete
                    for prev_id in subsumes:
                        del good_generalizations[prev_id]

                    if len(subsumes) > 0:
                        remarks.append(('subsumes {} previous generalizations', len(subsumes)))

                    good_generalizations[generalization_id] = {
                            'absblock': generalized_bb,
                            'trace': trace,
                            'remarks': remarks,
                            'last_result_ref': last_result_ref,
                        }

            # take all the generalizations that were not subsumed by others and
            # report them as discoveries
            for generalization_id, gen_data in good_generalizations.items():
                generalized_bb = gen_data['absblock']
                trace = gen_data['trace']
                last_result_ref = gen_data['last_result_ref']
                remarks = gen_data['remarks']

                logger.info("  adding new discovery:\n" + textwrap.indent(str(generalized_bb), 4*' '))
                discoveries.append(generalized_bb)
                curr_num_discoveries += 1
                report['num_discoveries'] = curr_num_discoveries

                if len(generalized_bb.abs_insns) == 1 and generalized_bb.abs_aliasing.is_top():
                    # this discovery subsumes all blocks containing one of the
                    # InsnSchemes represented by its singular abstract instruction
                    ai = generalized_bb.abs_insns[0]
                    insn_scheme_blacklist.update(actx.insn_feature_manager.compute_feasible_schemes(ai.features))
                    logger.info(f"  updated InsnScheme blacklist: now {len(insn_scheme_blacklist)} entries")

                if out_dir is not None:
                    trace.dump_json(witness_dir / f'{generalization_id}.json')
                    generalized_bb.dump_json(discovery_dir / f'{generalization_id}.json', result_ref=last_result_ref, remarks=remarks)

                write_report()

        batch_time = ((datetime.now() - batch_start_time) / timedelta(milliseconds=1)) / 1000
        per_batch_entry['batch_time'] = batch_time

        logger.info(f"  done with batch no. {curr_num_batches}")
        curr_num_batches += 1
        report['num_batches'] = curr_num_batches
        write_report()

    # the final subsumption check happens in `add_metrics.py` in the AnICA UI.
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


def generalize(actx: AbstractionContext, abstract_bb: AbstractBlock, strategy: str, remarks=None, interact=None):
    """ Generalize the given AbstractBlock while presering interestingness.

    This means that we try to adjust it such that it represents a maximal
    number of concrete blocks that are still mostly interesting.
    """
    generalization_batch_size = actx.discovery_cfg.generalization_batch_size

    logger.info("  generalizing BB:" + textwrap.indent(str(abstract_bb), 4*' ') )

    trace = WitnessTrace(abstract_bb)

    # check if sampling from abstract_bb leads to mostly interesting blocks
    concrete_bbs = sample_block_list(abstract_bb, generalization_batch_size, remarks=remarks)
    if len(concrete_bbs) == 0:
        raise DiscoveryError(f'Failed to sample any basic blocks for this abstract block:\n{abstract_bb}')

    interesting, result_ref = actx.interestingness_metric.is_mostly_interesting(concrete_bbs)
    last_result_ref = result_ref

    if not interesting:
        logger.info("  samples from the BB are not uniformly interesting!")
        trace.add_termination(comment="Samples from the starting block are not interesting!", measurements=result_ref)

        if remarks is not None:
            remarks.append("generalization terminated prematurely because the trivial abstraction is not uniformly interesting")

        return abstract_bb, trace, last_result_ref

    # a set of expansions that we tried to apply but did not yield interesting
    # results
    do_not_expand = set()

    while True:
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

        if strategy == "max_benefit":
            # choose the expansion that maximizes sampling freedom
            expansions.sort(key=lambda x: x[1][0], reverse=True)
            chosen_expansion, (benefit, definitely_does_not_change) = expansions[0]
        elif strategy == "random":
            chosen_expansion, (benefit, definitely_does_not_change) = random.choice(expansions)
        elif strategy == "interactive":
            assert interact is not None
            chosen_expansion, (benefit, definitely_does_not_change) = interact(working_copy, expansions)
        else:
            assert False, f"unknown generalization strategy: {strategy}"

        working_copy.apply_expansion(chosen_expansion)

        if definitely_does_not_change:
            logger.info(f"  the chosen expansion {chosen_expansion} (benefit: {benefit}) cannot change the represented basic blocks, skipping interestingness evaluation")
            trace.add_taken_expansion(chosen_expansion, None)
            abstract_bb = working_copy
        else:
            logger.info(f"  evaluating samples for expanding {chosen_expansion} (benefit: {benefit})")

            # sample a number of concrete blocks from it
            concrete_bbs = sample_block_list(working_copy, generalization_batch_size, remarks=remarks)

            # if they are mostly interesting, use the copy as new abstract block
            # one could also join the concrete bbs in instead
            interesting, result_ref = actx.interestingness_metric.is_mostly_interesting(concrete_bbs)

            if interesting:
                logger.info(f"  samples for expanding {chosen_expansion} are interesting, adjusting BB")
                trace.add_taken_expansion(chosen_expansion, result_ref)
                last_result_ref = result_ref
                abstract_bb = working_copy
            else:
                logger.info(f"  samples for expanding {chosen_expansion} are not interesting, discarding")
                trace.add_nontaken_expansion(chosen_expansion, result_ref)
                # make sure that we don't try that expansion again
                do_not_expand.add(chosen_expansion)

    trace.add_termination(comment="No more expansions remain.", measurements=None)

    if remarks is not None:
        remarks.append("generalization terminated properly")

    logger.info("  generalization done.")
    return abstract_bb, trace, last_result_ref


