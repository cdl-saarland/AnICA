""" This is an implementation of a stronger subsumption check for finding out
whether a concrete basic block is represented by an AbstractBlock, using a SAT
solver.
"""

from collections import defaultdict

from pysat.formula import CNFPlus, IDPool
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver

from iwho import BasicBlock

from .abstractblock import AbstractBlock, SamplingError

def check_subsumed(bb: BasicBlock, ab: AbstractBlock, print_assignment=False, precomputed_schemes=None):
    actx = ab.actx

    cnf = CNFPlus()

    next_id = 1
    def fresh_var():
        nonlocal next_id
        res = next_id
        next_id += 1
        return res

    map_vars = dict()
    map_a_vars = defaultdict(list)
    map_a_idxs = defaultdict(list)
    map_c_vars = defaultdict(list)
    map_c_idxs = defaultdict(list)
    map_var_to_ac = dict()

    abs_aliasing = ab.abs_aliasing

    for aidx, ai in enumerate(ab.abs_insns):
        if precomputed_schemes is not None:
            feasible_schemes = precomputed_schemes[aidx]
        else:
            feasible_schemes = actx.insn_feature_manager.compute_feasible_schemes(ai.features)
        for cidx, ci in enumerate(bb):
            if ci.scheme in feasible_schemes:
                var = fresh_var()
                map_vars[(aidx, cidx)] = var
                map_a_vars[aidx].append(var)
                map_a_idxs[aidx].append(cidx)
                map_c_vars[cidx].append(var)
                map_c_idxs[cidx].append(aidx)
                map_var_to_ac[var] = (aidx, cidx)

    for aidx, ai in enumerate(ab.abs_insns):
        vs = map_a_vars[aidx]
        if len(vs) == 0:
            # no fitting concrete insn for this entry
            return False
        # exactly one concrete insn must be chosen for each abs insn
        cnf.extend(CardEnc.equals(lits=vs, bound=1))

    for cidx, vs in map_c_vars.items():
        # at most one abs insn may be chosen for each concrete insn
        cnf.extend(CardEnc.atmost(lits=vs, bound=1))

    for ((aidx1, op_idx1), (aidx2, op_idx2)), v in abs_aliasing._aliasing_dict.items():
        if v.is_top():
            continue
        assert not v.is_bottom()
        should_alias = v.val

        for cidx1, ci1 in enumerate(bb):
            op1 = ci1.get_operand(op_idx1)
            if (cidx1 not in map_a_idxs[aidx1] or # cidx1 cannot be mapped to aidx1
                    op1 is None): # the entry wouldn't affect cidx1, because it has no fitting operand
                continue
            for cidx2, ci2 in enumerate(bb):
                op2 = ci2.get_operand(op_idx2)
                if (cidx2 not in map_a_idxs[aidx2] or # cidx2 cannot be mapped to aidx2
                        op2 is None): # the entry wouldn't affect cidx2, because it has no fitting operand
                    continue
                # map_vars[aidx1, cidx1] /\ map_vars[aidx2, cidx2] => (does_alias == should_alias)
                if ((should_alias and not actx.iwho_augmentation.must_alias(op1, op2)) or
                        (not should_alias and actx.iwho_augmentation.may_alias(op1, op2))):
                    cnf.append([- map_vars[aidx1, cidx1], - map_vars[aidx2, cidx2]])

    with Solver(bootstrap_with=cnf) as s:
        satisfiable = s.solve()

        if satisfiable and print_assignment:
            print("insn_assignment:")
            model = s.get_model()
            for v in model:
                if v > 0:
                    ai, ci = map_var_to_ac[abs(v)]
                    print(f"  {ai}: {ci}")

    return satisfiable


def compute_coverage(ab, bb_sample, ratio=True):
    actx = ab.actx

    # Without this, we would compute the same feasible schemes for all concrete
    # bbs, which is quite expensive.
    precomputed_schemes = []
    for ai in ab.abs_insns:
        precomputed_schemes.append(actx.insn_feature_manager.compute_feasible_schemes(ai.features))

    num_covered = 0
    for bb in bb_sample:
        if check_subsumed(bb, ab, precomputed_schemes=precomputed_schemes):
            num_covered += 1

    if ratio:
        return num_covered / len(bb_sample)
    else:
        return num_covered


def ab_coverage(ab, num_samples, bb_len=None):
    """ Compute the coverage of the AbstractBlock `ab` over `num_samples` basic
    blocks of length `bb_len` (or the number of insns in `ab` if bb_len is
    None).
    That is the ratio of the randomly sampled basic blocks that are subsumed by
    `ab`.
    """
    actx = ab.actx

    if bb_len is None:
        bb_len = len(ab.abs_insns)

    concrete_bbs = []
    sample_universe = AbstractBlock.make_top(actx, bb_len)
    sampler = sample_universe.precompute_sampler()
    for x in range(num_samples):
        try:
            concrete_bbs.append(sampler.sample())
        except SamplingError as e:
            logger.info("a sample failed: {e}")

    coverage_ratio = compute_coverage(ab, concrete_bbs, ratio=True)
    return coverage_ratio


