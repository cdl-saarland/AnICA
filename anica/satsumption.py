""" This is an implementation of a stronger subsumption check for finding out
whether a concrete basic block is represented by an AbstractBlock, using a SAT
solver.
"""

from collections import defaultdict
import itertools

from pysat.formula import CNFPlus, IDPool
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver

from iwho import BasicBlock

from .abstractblock import AbstractBlock, SamplingError

def check_subsumed_aa(ab1, ab2, print_assignment=False):
    """ Check whether ab2 represents all concrete blocks that ab1 represents
    (wrt the abstraction context).

    Both blocks must have the same abstraction context.
    """

    actx = ab1.actx

    if len(ab1.abs_insns) < len(ab2.abs_insns):
        # Abstract blocks of different length can only be in a subsumption
        # relation if the shorter one subsumes the longer one.
        return False

    next_id = 1
    def fresh_var():
        nonlocal next_id
        res = next_id
        next_id += 1
        return res

    both_feasible_sets = []
    for ab in (ab1, ab2):
        feasible_sets = []
        for ai in ab.abs_insns:
            fs = actx.insn_feature_manager.compute_feasible_schemes(ai.features)
            feasible_sets.append(fs)
        both_feasible_sets.append(feasible_sets)


    map_vars = dict() # maps a pair of indices into the first and the second ab to their edge variable
    map_b1_vars = defaultdict(list) # maps an index into the first ab to all edge variables to second ab absinsns that subsume it
    # map_b1_idxs = defaultdict(list) # maps an index into the first ab to all indices of second ab absinsns that subsume it
    # not needed
    map_b2_vars = defaultdict(list) # maps an index into the second ab to all edge variables to first ab absinsns that are subsumed by it
    map_b2_idxs = defaultdict(list) # maps an index into the second ab to all indices of first ab absinsns that are subsumed by it
    map_var_to_idx = dict() # converse to map_vars, for printing the satisfying assignment

    for (idx_b1, fs_b1), (idx_b2, fs_b2) in itertools.product(*map(enumerate, both_feasible_sets)):
        if fs_b1.issubset(fs_b2):
            # They could be mapped, i.e. the feasible set of the instruction in
            # b1 is a subset of the feasible set of the instruction in b2. If
            # that is not the case, the variables need to be false anyway, so
            # we can omit them.
            var = fresh_var()
            map_vars[(idx_b1, idx_b2)] = var
            map_b1_vars[idx_b1].append(var)
            # map_b1_idxs[idx_b1].append(idx_b2)
            map_b2_vars[idx_b2].append(var)
            map_b2_idxs[idx_b2].append(idx_b1)
            map_var_to_idx[var] = (idx_b1, idx_b2)

    cnf = CNFPlus()

    for idx_b2 in range(len(ab2.abs_insns)):
        vs = map_b2_vars[idx_b2]
        # We don't just iterate over the map_b2_vars.items() because those
        # wouldn't contain empty entries.
        if len(vs) == 0:
            # there is no fitting AbsInsn for this one
            return False
        # for every AbsInsn in ab2, there should be exactly one in ab1
        cnf.extend(CardEnc.equals(lits=vs, bound=1))

    for idx_b1, vs in map_b1_vars.items():
        # for every AbsInsn in ab1, there should be at most one in ab2
        # It is fine if there is an abstract insn in ab1 that is not matched by
        # any abstract insn in ab2.
        # This is consistent to the check_subsumed function below, which only
        # checks if a concrete block contains a subset of instructions that are
        # matched by the abstract block.
        cnf.extend(CardEnc.atmost(lits=vs, bound=1))


    for ((idx1_b2, op_idx1), (idx2_b2, op_idx2)), abs_feature_b2 in ab2.abs_aliasing._aliasing_dict.items():
        if abs_feature_b2.is_top():
            # this component of b2 subsumes everything anyway, no constraint needed
            continue

        # b2 imposes an actual aliasing constraint. Mapped instructions in b1 need to impose this constraint as well.

        for idx1_b1, idx2_b1 in itertools.product(map_b2_idxs[idx1_b2], map_b2_idxs[idx2_b2]):
            abs_feature_b1 = ab1.abs_aliasing.get_component((idx1_b1, op_idx1), (idx2_b1, op_idx2))
            if (abs_feature_b1 is None # None means TOP here
                    or not abs_feature_b2.subsumes(abs_feature_b1)):
                # this means that in this component, ab2 does not subsume ab1,
                # so we need to add a constraint to disallow mapping those
                # pairs together.
                # i.e. assert(not (map_vars[idx1_b1, idx1_2] and map_vars[idx2_b1, idx2_2]))
                cnf.append([
                        -map_vars[(idx1_b1, idx1_b2)], -map_vars[(idx2_b1, idx2_b2)]
                    ])

    clean_vars = dict()
    # ensure that the mapping does not reorder instructions
    for idx_b2, ai_b2 in enumerate(ab2.abs_insns):
        next_idx_b2 = (idx_b2 + 1) % len(ab2.abs_insns)
        for idx1_b1, idx2_b1 in itertools.permutations(range(len(ab1.abs_insns)), 2): # every pair, with both ways to order them
            if ((idx1_b1 + 1) % len(ab1.abs_insns)) == idx2_b1: # there is no instruction between idx1_b1 and idx2_b1
                continue

            if (idx1_b1, idx_b2) not in map_vars or (idx2_b1, next_idx_b2) not in map_vars: # those pairs cannot be mapped anyway
                continue

            clean_var = fresh_var()
            clean_vars[(idx1_b1, idx2_b1)] = clean_var

            # if idx_b2 is represented by idx1_b1, and the next insn in ab2 is
            # represented by idx2_b1, the insns between idx1_b1 and idx2_b1
            # should be clean (i.e. not represent any ai)
            cnf.append([-map_vars[(idx1_b1, idx_b2)], -map_vars[(idx2_b1, next_idx_b2)], clean_var])

            idx_b1_mid = idx1_b1 + 1
            while idx_b1_mid != idx2_b1: # for every insn between idx1_b1 and idx2_b1
                for idx_b2_it in range(len(ab2.abs_insns)):
                    if (idx_b1_mid, idx_b2_it) not in map_vars: # this pair cannot be mapped anyway
                        continue
                    cnf.append([-clean_var, -map_vars[(idx_b1_mid, idx_b2_it)]])

                idx_b1_mid = (idx_b1_mid + 1) % len(ab1)

    with Solver(bootstrap_with=cnf) as s:
        satisfiable = s.solve()

        if satisfiable and print_assignment:
            print("insn_assignment:")
            model = s.get_model()
            for v in model:
                if v > 0:
                    i1, i2 = map_var_to_idx[abs(v)]
                    print(f"  {i1}: {i2}")

    return satisfiable


def check_subsumed(bb: BasicBlock, ab: AbstractBlock, print_assignment=False, precomputed_schemes=None):
    """ Check if the concrete basic block bb contains a pattern that is
    represented by the abstract basic block ab.

    This is the case if there is an injective mapping of each abstract insn in
    ab to a concrete insn in bb such that each concrete insn is feasible for
    the mapped abstract insn and aliasing among the mapped instructions in bb
    follows the constraints imposed by ab.
    ALSO, the concrete instructions between any two concrete instructions
    mapped to two subsequent abstract instructions may not be mapped to any
    abstract instruction. This should ensure that the ordering is preserved.

    bb might therefore be longer than ab and still be subsumed, if a subset of
    the instructions in bb has a suitable mapping to abstract insns.
    """
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
        # At most one abs insn may be chosen for each concrete insn.
        # It is fine if there is a concrete insn that is not matched by any
        # abstract insn.
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
                    cnf.append([- map_vars[(aidx1, cidx1)], - map_vars[(aidx2, cidx2)]])

    clean_vars = dict()
    # ensure that the mapping does not reorder instructions
    for aidx, ai in enumerate(ab.abs_insns):
        next_aidx = (aidx + 1) % len(ab.abs_insns)
        for cidx1, cidx2 in itertools.permutations(range(len(bb)), 2): # every pair, with both ways to order them
            if ((cidx1 + 1) % len(bb)) == cidx2: # there is no instruction between cidx1 and cidx2
                continue

            if (aidx, cidx1) not in map_vars or (next_aidx, cidx2) not in map_vars: # those pairs cannot be mapped anyway
                continue

            clean_var = fresh_var()
            clean_vars[(cidx1, cidx2)] = clean_var

            cnf.append([-map_vars[(aidx, cidx1)], -map_vars[(next_aidx, cidx2)], clean_var]) # if ai is represented by c1, and the next ai is represented by c2, the insns between c1 and c2 should be clean (i.e. not represent any ai)

            cidx_mid = cidx1 + 1
            while cidx_mid != cidx2: # for every insn between cidx1 and cidx2
                for aidx_it in range(len(ab.abs_insns)):
                    if (aidx_it, cidx_mid) not in map_vars: # this pair cannot be mapped anyway
                        continue
                    cnf.append([-clean_var, -map_vars[(aidx_it, cidx_mid)]])

                cidx_mid = (cidx_mid + 1) % len(bb)


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


def check_subsumed_arbitrary_order(ab1, ab2, print_assignment=False):
    """ Check whether ab2 represents all concrete blocks that ab1 represents
    (wrt the abstraction context).

    Both blocks must have the same abstraction context.
    """

    actx = ab1.actx

    if len(ab1.abs_insns) < len(ab2.abs_insns):
        # Abstract blocks of different length can only be in a subsumption
        # relation if the shorter one subsumes the longer one.
        return False

    next_id = 1
    def fresh_var():
        nonlocal next_id
        res = next_id
        next_id += 1
        return res

    both_feasible_sets = []
    for ab in (ab1, ab2):
        feasible_sets = []
        for ai in ab.abs_insns:
            fs = actx.insn_feature_manager.compute_feasible_schemes(ai.features)
            feasible_sets.append(fs)
        both_feasible_sets.append(feasible_sets)


    map_vars = dict() # maps a pair of indices into the first and the second ab to their edge variable
    map_b1_vars = defaultdict(list) # maps an index into the first ab to all edge variables to second ab absinsns that subsume it
    # map_b1_idxs = defaultdict(list) # maps an index into the first ab to all indices of second ab absinsns that subsume it
    # not needed
    map_b2_vars = defaultdict(list) # maps an index into the second ab to all edge variables to first ab absinsns that are subsumed by it
    map_b2_idxs = defaultdict(list) # maps an index into the second ab to all indices of first ab absinsns that are subsumed by it
    map_var_to_idx = dict() # converse to map_vars, for printing the satisfying assignment

    for (idx_b1, fs_b1), (idx_b2, fs_b2) in itertools.product(*map(enumerate, both_feasible_sets)):
        if fs_b1.issubset(fs_b2):
            # They could be mapped, i.e. the feasible set of the instruction in
            # b1 is a subset of the feasible set of the instruction in b2. If
            # that is not the case, the variables need to be false anyway, so
            # we can omit them.
            var = fresh_var()
            map_vars[(idx_b1, idx_b2)] = var
            map_b1_vars[idx_b1].append(var)
            # map_b1_idxs[idx_b1].append(idx_b2)
            map_b2_vars[idx_b2].append(var)
            map_b2_idxs[idx_b2].append(idx_b1)
            map_var_to_idx[var] = (idx_b1, idx_b2)

    cnf = CNFPlus()

    for idx_b2 in range(len(ab2.abs_insns)):
        vs = map_b2_vars[idx_b2]
        # We don't just iterate over the map_b2_vars.items() because those
        # wouldn't contain empty entries.
        if len(vs) == 0:
            # there is no fitting AbsInsn for this one
            return False
        # for every AbsInsn in ab2, there should be exactly one in ab1
        cnf.extend(CardEnc.equals(lits=vs, bound=1))

    for idx_b1, vs in map_b1_vars.items():
        # for every AbsInsn in ab1, there should be at most one in ab2
        # It is fine if there is an abstract insn in ab1 that is not matched by
        # any abstract insn in ab2.
        # This is consistent to the check_subsumed function below, which only
        # checks if a concrete block contains a subset of instructions that are
        # matched by the abstract block.
        cnf.extend(CardEnc.atmost(lits=vs, bound=1))


    for ((idx1_b2, op_idx1), (idx2_b2, op_idx2)), abs_feature_b2 in ab2.abs_aliasing._aliasing_dict.items():
        if abs_feature_b2.is_top():
            # this component of b2 subsumes everything anyway, no constraint needed
            continue

        # b2 imposes an actual aliasing constraint. Mapped instructions in b1 need to impose this constraint as well.

        for idx1_b1, idx2_b1 in itertools.product(map_b2_idxs[idx1_b2], map_b2_idxs[idx2_b2]):
            abs_feature_b1 = ab1.abs_aliasing.get_component((idx1_b1, op_idx1), (idx2_b1, op_idx2))
            if (abs_feature_b1 is None # None means TOP here
                    or not abs_feature_b2.subsumes(abs_feature_b1)):
                # this means that in this component, ab2 does not subsume ab1,
                # so we need to add a constraint to disallow mapping those
                # pairs together.
                # i.e. assert(not (map_vars[idx1_b1, idx1_2] and map_vars[idx2_b1, idx2_2]))
                cnf.append([
                        -map_vars[(idx1_b1, idx1_b2)], -map_vars[(idx2_b1, idx2_b2)]
                    ])

    with Solver(bootstrap_with=cnf) as s:
        satisfiable = s.solve()

        if satisfiable and print_assignment:
            print("insn_assignment:")
            model = s.get_model()
            for v in model:
                if v > 0:
                    i1, i2 = map_var_to_idx[abs(v)]
                    print(f"  {i1}: {i2}")

    return satisfiable


def check_subsumed_arbitrary_order(bb: BasicBlock, ab: AbstractBlock, print_assignment=False, precomputed_schemes=None):
    """ IMPORTANT!
    THIS IMPLEMENTATION HAS BEEN DEEMED UNREASONABLE since changing up the
    order affects the block semeantics probably too severly.

    Check if the concrete basic block bb contains a pattern that is
    represented by the abstract basic block ab.

    This is the case if there is an injective mapping of each abstract insn in
    ab to a concrete insn in bb such that each concrete insn is feasible for
    the mapped abstract insn and aliasing among the mapped instructions in bb
    follows the constraints imposed by ab.

    bb might therefore be longer than ab and still be subsumed, if a subset of
    the instructions in bb has a suitable mapping to abstract insns.

    """
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
        # At most one abs insn may be chosen for each concrete insn.
        # It is fine if there is a concrete insn that is not matched by any
        # abstract insn.
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


