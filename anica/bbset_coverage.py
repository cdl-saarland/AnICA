""" Functions to compute metrics on how many basic blocks from a given set are
covered by a set of abstract blocks.
"""

from collections import defaultdict
import itertools

ORTOOLS=0
Z3=1

# Google's ortools seem to be substantially faster here.
SOLVER=ORTOOLS
# SOLVER=Z3

if SOLVER == ORTOOLS:
    from ortools.sat.python import cp_model
elif SOLVER == Z3:
    import z3
else:
    assert False, f"unknown solver {SOLVER}"

from anica.satsumption import check_subsumed

def get_table_metrics(actx, all_abs, interesting_bbs, total_num_bbs, heuristic=False):
    """ Compute a metrics corresponding to the evaluation table in the AnICA
    paper for a selection of `AbstractBlock`s and interesting concrete basic
    blocks. `total_num_bbs` should be the total number of (interesting and
    non-interesting) basic blocks in the set from which the `interesting_bbs`
    were taken.
    """
    interesting_str, interesting_dict, interesting_covered_per_ab = get_coverage_metrics(actx=actx, all_abs=all_abs, all_bbs=interesting_bbs)

    num_interesting = len(interesting_bbs)

    if heuristic:
        num_interesting_bbs_covered_top10, top10_abs = compute_heuristic_covering_set(actx=actx, all_abs=all_abs, all_bbs=interesting_bbs, num_abs_taken=10)
    else:
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
    """ Compute a dictionary that contains for each abstract block a set of all
    concrete basic blocks that it subsumes. Both entity kinds are represented
    by numerical indices into the argument lists.
    """
    cover_map = defaultdict(set)

    for ab_idx, ab in enumerate(all_abs):
        precomputed_schemes = []
        for ai in ab.abs_insns:
            precomputed_schemes.append(actx.insn_feature_manager.compute_feasible_schemes(ai.features))

        for bb_idx, bb in enumerate(all_bbs):
            if check_subsumed(bb, ab, precomputed_schemes=precomputed_schemes):
                cover_map[ab_idx].add(bb_idx)
    return cover_map


def compute_heuristic_covering_set(actx, all_abs, all_bbs, num_abs_taken):
    """ Employ a greedy algorithm to find a non-optimal selection of
    num_abs_taken abstract blocks from all_abs to cover a large portion of
    all_bbs.

    Returns a tuple of the size of the found large portion of all_bbs and a
    list of the indices in all_abs of the selected abs.
    """
    # sort the ABs by their string representation (which should be
    # deterministic) for a deterministic start
    # with the idx column, we can translate the result back to indices into
    # all_abs
    annotated_abs = [ (ab, str(ab), idx) for idx, ab in enumerate(all_abs) ]
    annotated_abs.sort(key=lambda x: x[1])
    sorted_abs = [ ab for ab, s, i in annotated_abs ]

    cover_map = get_complete_coverage(actx, sorted_abs, all_bbs)

    covered = set()
    recently_covered = set()

    selected_abs = []

    total_abs = len(sorted_abs)
    while len(selected_abs) < min(num_abs_taken, total_abs):
        max_val = -1
        max_ab = None
        max_bbs = None

        for ab, bbs in cover_map.items():
            bbs.difference_update(recently_covered)
            if len(bbs) > max_val:
                max_val = len(bbs)
                max_ab = ab
                max_bbs = bbs

        assert max_ab is not None
        selected_abs.append(max_ab)
        recently_covered = max_bbs
        covered.update(max_bbs)
        del cover_map[max_ab]

    # selected_abs are indices into the sorted_abs, we need to translate them
    # to the original all_abs:
    unsorted_indices = [ annotated_abs[sorted_idx][2] for sorted_idx in selected_abs ]

    return len(covered), unsorted_indices



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

    if SOLVER == ORTOOLS:
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
    elif SOLVER == Z3:
        solver = z3.Optimize()

        use_ab_vars = {
                i: z3.Int(f'use_ab_{i}')
                    for i in range(len(all_abs)) if len(cover_map[i]) > 0
                    # ABs that cover no BB never need to be chosen, so we cut the
                    # variable number here a bit smaller
            }

        for i, v in use_ab_vars.items():
            solver.add(z3.And((0 <= v), (v <= 1)))

        # - 1 iff concrete block j is covered
        cover_bb_vars = {
                j: z3.Int(f'cover_ab_{j}')
                    for j in candidate_bbs
                    # Only BBs that are covered by some AB need to be considered,
                    # more BBs to be cut.
            }

        for i, v in cover_bb_vars.items():
            solver.add(z3.And((0 <= v), (v <= 1)))

        # Constraints:
        # - at most 10 ABs may be chosen
        solver.add(z3.Sum([use_ab_i for i, use_ab_i in use_ab_vars.items()]) <= num_abs_taken)

        # - if none of the ABs that cover a BB is chosen, that BB is not covered.
        for j, cover_bb_j in cover_bb_vars.items():
            solver.add(
                    cover_bb_j <= z3.Sum([
                        use_ab_i for i, use_ab_i in use_ab_vars.items() if j in cover_map[i]
                    ])
                )

        # Objective: maximize the number of covered BBs
        objective = solver.maximize(z3.Sum([cover_bb_j for j, cover_bb_j in cover_bb_vars.items()]))

        status = str(solver.check())

        if status == "sat":
            objective_val = objective.upper().as_long()
            model = solver.model()
            chosen_abs = []
            for i, use_ab_i in use_ab_vars.items():
                if model[use_ab_i].as_long() > 0:
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
    else:
        assert False, f"unknown solver {SOLVER}"



def get_coverage_metrics(actx, all_abs, all_bbs):
    """ Legacy function to compute more coverage metrics in scripts.
    """
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


def make_heatmap(keys, data, err_threshold, paper_mode=False):
    import pandas as pd
    import seaborn as sns
    import matplotlib.pyplot as plt

    all_keys = set(keys)
    all_keys.discard('bb')
    all_keys = sorted(all_keys)
    if paper_mode:
        all_keys = [
            "iaca.hsw",
            "llvm-mca.13-r+a.hsw",
            "llvm-mca.9-r+a.hsw",
            "osaca.0.4.6.hsw",
            "uica.hsw",
            "ithemal.bhive.hsw",
            "difftune.artifact.hsw",
        ]

    def latex_pred_name(x):
        if paper_mode:
            components = x.split('.')
            if x.startswith('llvm-mca'):
                return "llvm-mca " + components[1].split('-')[0]
            elif x.startswith('iaca'):
                return "IACA"
            elif x.startswith('uica'):
                return "uiCA"
            elif x.startswith('difftune'):
                return "DiffTune"
            elif x.startswith('osaca'):
                return "OSACA"
            elif x.startswith('ithemal'):
                return "Ithemal"
            else:
                return components[0]
        else:
            return x

    heatmap_data = defaultdict(dict)
    # for k1, k2 in itertools.product(all_keys, repeat=2):
    for k1, k2 in itertools.combinations_with_replacement(all_keys, r=2):
        res = 0
        for row in data:
            # TODO improvement: use a generalized version from interestingness.py
            values = [float(row[k1]), float(row[k2])]
            if any(map(lambda x: x <= 0, values)):
                res += 1
                continue
            rel_error = ((max(values) - min(values)) / sum(values)) * len(values)
            if rel_error >= err_threshold:
                res += 1
        heatmap_data[latex_pred_name(k1)][latex_pred_name(k2)] = 100 * res / len(data)

    df = pd.DataFrame(heatmap_data)
    cmap = sns.color_palette("rocket", as_cmap=True)

    fig, ax = plt.subplots(figsize=(8.0,6.0))
    p = sns.heatmap(df, annot=True, fmt=".0f", square=True, linewidths=.5, cmap=cmap, vmin=0.0, vmax=100.0, ax=ax, cbar_kws={'format': '%.0f%%', 'label': f"% of blocks with rel. difference > {100 * err_threshold:.0f}%"})
    # plt.title(f"Percentage of blocks with a rel. error >= {err_threshold} on a set of {len(data)} blocks")

    # locs, labels = plt.xticks()
    # plt.setp(labels, rotation=30)
    p.set_xticklabels(p.get_xticklabels(), rotation=30, horizontalalignment='right')

    fig.tight_layout()

    return fig


