
from anica.satsumption import check_subsumed

def get_table_metrics(actx, all_abs, interesting_bbs, total_num_bbs):
    interesting_str, interesting_dict, interesting_covered_per_ab = get_coverage_metrics(actx=actx, all_abs=all_abs, all_bbs=interesting_bbs)

    num_interesting = len(interesting_bbs)

    num_interesting_bbs_covered_top10 = float("NaN")

    coverage_table = list(sorted(interesting_covered_per_ab.items(), key=lambda x: x[1], reverse=True))

    res = 0
    for idx, (abidx, num) in enumerate(coverage_table, start = 1):
        res += num
        if idx == 10:
            num_interesting_bbs_covered_top10 = res
            percent_interesting_bbs_covered_top10 = (num_interesting_bbs_covered_top10 * 100) / num_interesting
            break
    else:
        num_interesting_bbs_covered_top10 = float('NaN')
        percent_interesting_bbs_covered_top10 = float('NaN')

    result = {
            'num_bbs_interesting': num_interesting,
            'percent_bbs_interesting': (num_interesting * 100) / total_num_bbs,
            'num_interesting_bbs_covered': interesting_dict['num_covered'],
            'percent_interesting_bbs_covered': interesting_dict['percent_covered'],
            'num_interesting_bbs_covered_top10': num_interesting_bbs_covered_top10,
            'percent_interesting_bbs_covered_top10': percent_interesting_bbs_covered_top10,
        }
    return result


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
