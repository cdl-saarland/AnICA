
from copy import deepcopy
import json
import textwrap

from devidisc.abstractblock import AbstractBlock
from devidisc.abstractionconfig import AbstractionConfig

import logging
logger = logging.getLogger(__name__)


class WitnessTrace:
    class Witness:
        def __init__(self, component_token, expansion, taken, terminate, measurements):
            self.component_token = component_token
            self.expansion = expansion
            self.taken = taken
            self.terminate = terminate
            self.measurements = measurements

        def to_json_dict(self):
            return {k: repr(v) for k, v in vars(self).items()}

        @staticmethod
        def from_json_dict(self, json_dict):
            return Witness(**json_dict)

    def __init__(self, abs_block):
        self.start = deepcopy(abs_block)
        self.trace = []

    def __len__(self):
        return len(self.trace)

    def add_taken_expansion(self, component_token, expansion, measurements):
        witness = WitnessTrace.Witness(component_token=component_token,
                expansion=expansion,
                taken=True,
                terminate=False,
                measurements=measurements)
        self.trace.append(witness)

    def add_nontaken_expansion(self, component_token, expansion, measurements):
        witness = WitnessTrace.Witness(component_token=component_token,
                expansion=expansion,
                taken=False,
                terminate=False,
                measurements=measurements)
        self.trace.append(witness)

    def add_termination(self, measurements):
        witness = WitnessTrace.Witness(component_token=None,
                expansion=None,
                taken=False,
                terminate=True,
                measurements=measurements)
        self.trace.append(witness)

    def replay(self, index=None, validate=False):
        if index is None:
            trace = self.trace
        else:
            trace = self.trace[:index]

        res = deepcopy(self.start)
        for witness in trace:
            if witness.terminate:
                break
            if not witness.taken:
                continue
            if validate:
                check_tmp = deepcopy(res)
            res.apply_expansion(witness.component_token, witness.expansion)
            if validate:
                assert res.subsumes(check_tmp)
                check_tmp = None

        return res

    def __str__(self):
        return json.dumps(self.to_json_dict(), indent=2, separators=(',', ':'))

    def to_json_dict(self):
        res = dict()
        res['start'] = self.start.to_json_dict()
        trace = []
        for v in self.trace:
            trace.append(v.to_json_dict())
        res['trace'] = trace
        return res

    @staticmethod
    def from_json_dict(self, acfg, json_dict):
        start_bb = AbstractBlock.from_json_dict(acfg, json_dict['start'])
        res = WitnessTrace(start_bb)
        for v in json_dict['trace']:
            res.trace.append(WitnessTrace.from_json_dict(v))
        return res

    def to_dot(self):
        # TODO
        pass


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
    concrete_bbs = [ abstract_bb.sample() for x in range(acfg.generalization_batch_size) ]

    interesting = acfg.is_mostly_interesting(concrete_bbs)

    if not interesting:
        logger.info("  samples from the BB are not uniformly interesting!")
        trace.add_termination([]) # TODO add measurements to the witnesses
        return abstract_bb, trace

    # a set of tokens representing subcomponents of the abstract basic block
    # that we tried to expand but did not yield interesing results
    expansion_limit_tokens = set()

    while True: # TODO add a termination condition, e.g. based on a budget adjusted by potential usefulness? At least a fixed upper bound should exist, so that a bug in the expansion cannot lead to endless loops
        # create a deepcopy to expand
        working_copy = deepcopy(abstract_bb)

        # expand some component
        new_token, new_action = working_copy.expand(expansion_limit_tokens)
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
            trace.add_taken_expansion(new_token, new_action, []) # TODO add measurements to the witnesses
            abstract_bb = working_copy
        else:
            logger.info(f"  samples for expanding {new_token} are not interesting, discarding")
            trace.add_nontaken_expansion(new_token, new_action, []) # TODO add measurements to the witnesses
            # make sure that we don't try that token again
            expansion_limit_tokens.add(new_token)

    logger.info("  generalization done.")
    return abstract_bb, trace


