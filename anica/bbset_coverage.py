""" TODO document
"""

from collections import defaultdict


from ortools.sat.python import cp_model

from anica.satsumption import check_subsumed

def get_table_metrics(actx, all_abs, interesting_bbs, total_num_bbs):
    interesting_str, interesting_dict, interesting_covered_per_ab = get_coverage_metrics(actx=actx, all_abs=all_abs, all_bbs=interesting_bbs)

    num_interesting = len(interesting_bbs)

    num_interesting_bbs_covered_top10, top10_abs = compute_optimal_covering_set(actx=actx, all_abs=all_abs, all_bbs=interesting_bbs, num_abs_taken=10)

    percent_interesting_bbs_covered_top10 = (num_interesting_bbs_covered_top10 * 100) / num_interesting

    coverage_table = list(sorted(interesting_covered_per_ab.items(), key=lambda x: x[1], reverse=True))

    result = {
            'num_bbs_interesting': num_interesting,
            'percent_bbs_interesting': (num_interesting * 100) / total_num_bbs,
            'num_interesting_bbs_covered': interesting_dict['num_covered'],
            'percent_interesting_bbs_covered': interesting_dict['percent_covered'],
            'num_interesting_bbs_covered_top10': num_interesting_bbs_covered_top10,
            'percent_interesting_bbs_covered_top10': percent_interesting_bbs_covered_top10,
        }
    return result

def get_complete_coverage(actx, all_abs, all_bbs):
    cover_map = defaultdict(set)

    for ab_idx, ab in enumerate(all_abs):
        precomputed_schemes = []
        for ai in ab.abs_insns:
            precomputed_schemes.append(actx.insn_feature_manager.compute_feasible_schemes(ai.features))

        for bb_idx, bb in enumerate(all_bbs):
            if check_subsumed(bb, ab, precomputed_schemes=precomputed_schemes):
                cover_map[ab_idx].add(bb_idx)
    return cover_map


def compute_optimal_covering_set(actx, all_abs, all_bbs, num_abs_taken):
    """ Employ an optimizing constraint solver to find an optimal selection of
    num_abs_taken abstract blocks from all_abs to cover the largest portion of
    all_bbs.

    Returns a tuple of the size of the found maximal portion of all_bbs and a
    list of the indices in all_abs of the selected abs.
    """

    cover_map = get_complete_coverage(actx, all_abs, all_bbs)
    candidate_bbs = set()
    for ab, bbs in cover_map.items():
        candidate_bbs.update(bbs)
    candidate_bbs = sorted(candidate_bbs)

    model = cp_model.CpModel()

    # Variables:
    # - 1 iff abstract block i is chosen
    use_ab_vars = {
            i: model.NewIntVar(0, 1, f'use_ab_{i}')
                for i in range(len(all_abs)) if len(cover_map[i]) > 0
                # ABs that cover no BB never need to be chosen, so we cut the
                # variable number here a bit smaller
        }

    # - 1 iff concrete block j is covered
    cover_bb_vars = {
            j: model.NewIntVar(0, 1, f'cover_ab_{j}')
                for j in candidate_bbs
                # Only BBs that are covered by some AB need to be considered,
                # more BBs to be cut.
        }

    # Constraints:
    # - at most 10 ABs may be chosen
    model.Add(cp_model.LinearExpr.Sum([use_ab_i for i, use_ab_i in use_ab_vars.items()]) <= num_abs_taken)

    # - if none of the ABs that cover a BB is chosen, that BB is not covered.
    for j, cover_bb_j in cover_bb_vars.items():
        model.Add(
                cover_bb_j <= cp_model.LinearExpr.Sum([
                    use_ab_i for i, use_ab_i in use_ab_vars.items() if j in cover_map[i]
                ])
            )

    # Objective: maximize the number of covered BBs
    model.Maximize(cp_model.LinearExpr.Sum([cover_bb_j for j, cover_bb_j in cover_bb_vars.items()]))

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        if status == cp_model.FEASIBLE:
            print("found potentially non-optimal solution")
        objective_val = solver.ObjectiveValue()
        chosen_abs = []
        for i, use_ab_i in use_ab_vars.items():
            if solver.Value(use_ab_i) > 0:
                chosen_abs.append(i)

        # Do some sanity checks to validate the result.
        # Without any trust in model and solver, this ensures that at least
        # objective_val many BBs can be covered by a set of num_abs_taken ABs.
        assert len(chosen_abs) <= num_abs_taken
        covered_bbs = set()
        for ab_idx in chosen_abs:
            covered_bbs.update(cover_map[ab_idx])
        assert len(covered_bbs) == objective_val

        return objective_val, chosen_abs
    else:
        assert False, "No solution to coverage problem found!"



def get_coverage_metrics(actx, all_abs, all_bbs):
    covered = []

    not_covered = all_bbs

    covered_per_ab = dict()

    for ab_idx, ab in enumerate(all_abs):
        next_not_covered = []

        # precomputing schemes speeds up subsequent check_subsumed calls for this abstract block
        precomputed_schemes = []
        for ai in ab.abs_insns:
            precomputed_schemes.append(actx.insn_feature_manager.compute_feasible_schemes(ai.features))

        covered_by_ab = 0
        for bb in not_covered:
            if check_subsumed(bb, ab, precomputed_schemes=precomputed_schemes):
                covered.append(bb)
                covered_by_ab += 1
            else:
                next_not_covered.append(bb)

        covered_per_ab[ab_idx] = covered_by_ab

        not_covered = next_not_covered


    total_num = len(all_bbs)
    num_covered = len(covered)
    num_not_covered = len(not_covered)

    if total_num != 0:
        percent_covered = (num_covered * 100) / total_num
        percent_not_covered = (num_not_covered * 100) / total_num
    else:
        percent_covered = -1.0
        percent_not_covered = -1.0

    res_str = f"covered: {num_covered} ({percent_covered:.1f}%)\n" + f"not covered: {num_not_covered} ({percent_not_covered:.1f}%)"
    res_dict = {
            'num_covered': num_covered,
            'percent_covered': percent_covered,
            'num_not_covered': num_not_covered,
            'percent_not_covered': percent_not_covered,
        }
    return res_str, res_dict, covered_per_ab
