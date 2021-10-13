#!/usr/bin/env pytest

import pytest

import copy
import json
import os
import sys

import iwho

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from anica.abstractblock import AbstractBlock, SamplingError
from anica.abstractioncontext import AbstractionContext

from test_utils import *


def test_concrete_ab_single_insn(random, actx):
    bb = make_bb(actx, "add rax, 0x2a")
    ab = AbstractBlock(actx, bb)
    havoc_alias_part(ab)

    print(ab)
    assert ab.subsumes(ab)

def test_concrete_ab_single_insn_minimize(random, actx):
    bb = make_bb(actx, "add rax, 0x2a")
    ab = AbstractBlock(actx, bb)
    havoc_alias_part(ab)

    mab = ab.minimize()

    assert ab.subsumes(mab)

def test_div_minimize():
    config_dict = {
            "insn_feature_manager": {
                "features": [
                    ["exact_scheme", "singleton"],
                    ["mnemonic", ["editdistance", 3]],
                    ["opschemes", "subset"],
                    # ["memory_usage", "subset_or_definitely_not"],
                    # ["uops_on_SKL", ["log_ub", 5]],
                ]
            },
            "iwho": {
                "context_specifier": "x86_uops_info",
                "filters": ["no_cf", "with_measurements:SKL", "whitelist:hsw_bhive_schemes.csv"]
            },
            "interestingness_metric": { },
            "discovery": { },
            "sampling": {},
            "measurement_db": None,
            "predmanager": None,
        }

    absblock_dict = {
            "abs_insns": [
                {
                    "exact_scheme": "$SV:TOP",
                    "mnemonic": {"top": False, "base": "idiv", "curr_dist": 2, "max_dist": 3},
                    "opschemes": [],
                    # "memory_usage": {"subfeature": [], "is_in_subfeature": "$SV:TOP"},
                    # "uops_on_SKL": {"val": "$SV:TOP", "max_ub": 5},
                }
            ],
            "abs_aliasing": {
                "aliasing_dict": [
                    [[[0, ["$OperandKind:1", "reg0"]], [0, ["$OperandKind:2", 0]]], "$SV:TOP"],
                    [[[0, ["$OperandKind:1", "reg0"]], [0, ["$OperandKind:2", 1]]], "$SV:TOP"]
                ],
                "is_bot": False
            }
        }

    actx = AbstractionContext(config_dict)
    absblock_dict = actx.json_ref_manager.resolve_json_references(absblock_dict)
    absblock = AbstractBlock.from_json_dict(actx, absblock_dict)

    pre_min_features = actx.insn_feature_manager.compute_feasible_schemes(absblock.abs_insns[0].features)

    min_absblock = absblock.minimize()

    post_min_features = actx.insn_feature_manager.compute_feasible_schemes(min_absblock.abs_insns[0].features)

    assert len(pre_min_features) == len(post_min_features)

    print(list(map(str, pre_min_features)))
    print(len(pre_min_features))
    print("")
    print(list(map(str, post_min_features)))
    print(len(post_min_features))

    # assert False

def test_pause_minimize():
    config_dict = {
        "insn_feature_manager": {
            "features": [
                    ["exact_scheme", "singleton"],
                    ["mnemonic", ["editdistance", 3]],
                ]
            },
        "iwho": {
            "context_specifier": "x86_uops_info",
            "filters": ["no_cf", "with_measurements:SKL", "whitelist:hsw_bhive_schemes.csv"]
        },
        "interestingness_metric": { },
        "discovery": { },
        "sampling": {},
        "measurement_db": None,
        "predmanager": None,
    }

    absblock_dict = {
            "abs_insns": [
                    {
                        "exact_scheme": "$SV:TOP",
                        "mnemonic": {"top": False, "base": "pause", "curr_dist": 2, "max_dist": 3},
                    }
                ],
            "abs_aliasing": {"aliasing_dict": [], "is_bot": False}
        }

    actx = AbstractionContext(config_dict)
    absblock_dict = actx.json_ref_manager.resolve_json_references(absblock_dict)
    absblock = AbstractBlock.from_json_dict(actx, absblock_dict)

    pre_min_features = actx.insn_feature_manager.compute_feasible_schemes(absblock.abs_insns[0].features)

    min_absblock = absblock.minimize()

    post_min_features = actx.insn_feature_manager.compute_feasible_schemes(min_absblock.abs_insns[0].features)

    assert len(pre_min_features) == len(post_min_features)


def test_concrete_ab_single_insn_not_bottom(random, actx):
    bb = make_bb(actx, "add rax, 0x2a")
    ab = AbstractBlock(actx, bb)
    assert not ab.abs_insns[0].features['exact_scheme'].is_bottom()


def test_concrete_ab_single_insn_sample(random, actx):
    bb = make_bb(actx, "add rax, 0x2a")
    ab = AbstractBlock(actx, bb)
    havoc_alias_part(ab)

    print(ab)
    assert ab.subsumes(ab)

    new_bb = ab.sample()
    print(new_bb)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(actx, new_bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_concrete_ab_single_insn_mem(random, actx):
    bb = make_bb(actx, "add rax, [rbx + 0x20]")
    ab = AbstractBlock(actx, bb)
    havoc_alias_part(ab)

    print(ab)
    assert ab.subsumes(ab)


def test_concrete_ab_single_insn_mem_sample(random, actx):
    bb = make_bb(actx, "add rax, [rbx + 0x20]")
    ab = AbstractBlock(actx, bb)
    havoc_alias_part(ab)

    print(ab)
    assert ab.subsumes(ab)

    new_bb = ab.sample()
    print(new_bb)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(actx, new_bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_concrete_ab_multiple_insns(random, actx):
    bb = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb)
    havoc_alias_part(ab)

    print(ab)
    assert ab.subsumes(ab)


def test_concrete_ab_multiple_insns_sample(random, actx):
    bb = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb)
    havoc_alias_part(ab)

    print(ab)
    assert ab.subsumes(ab)

    new_bb = ab.sample()
    print(new_bb)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(actx, new_bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_join_equal(random, actx):
    bb = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb)
    havoc_alias_part(ab)
    ab.join(bb)

    print(ab)
    assert ab.subsumes(ab)

    new_ab = AbstractBlock(actx, bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)


def test_join_equal_sample(random, actx):
    bb = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb)
    havoc_alias_part(ab)
    ab.join(bb)

    print(ab)
    assert ab.subsumes(ab)

    new_ab = AbstractBlock(actx, bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)

    new_bb = ab.sample()
    print(new_bb)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(actx, new_bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_join_different_regs(random, actx):
    bb1 = make_bb(actx, "add rbx, 0x2a\nsub rbx, rax")
    bb2 = make_bb(actx, "add rcx, 0x2b\nsub rdx, rcx")
    ab = AbstractBlock(actx, bb1)
    havoc_alias_part(ab)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb2)))


def test_join_different_regs_sample(random, actx):
    bb1 = make_bb(actx, "add rbx, 0x2a\nsub rbx, rax")
    bb2 = make_bb(actx, "add rcx, 0x2b\nsub rdx, rcx")
    ab = AbstractBlock(actx, bb1)
    havoc_alias_part(ab)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb2)))

    new_bb = ab.sample()
    print(new_bb)

    assert len(new_bb) == len(bb1)
    for new, old in zip(new_bb, bb1):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(actx, new_bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)


def test_join_different_deps(random, actx):
    bb1 = make_bb(actx, "add rcx, 0x2a\nsub rbx, rcx")
    bb2 = make_bb(actx, "add rbx, 0x2a\nsub rbx, rcx")
    ab = AbstractBlock(actx, bb1)
    havoc_alias_part(ab)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb2)))


def test_join_different_deps_sample(random, actx):
    bb1 = make_bb(actx, "add rcx, 0x2a\nsub rbx, rcx")
    bb2 = make_bb(actx, "add rbx, 0x2a\nsub rbx, rcx")
    ab = havoc_alias_part(AbstractBlock(actx, bb1))
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb2)))

    new_bb = ab.sample()
    print(new_bb)

    assert len(new_bb) == len(bb1)
    for new, old in zip(new_bb, bb1):
        assert new.scheme == old.scheme

    new_ab = havoc_alias_part(AbstractBlock(actx, new_bb))
    assert ab.subsumes(new_ab)


def test_join_equal_len(random, actx):
    bb1 = make_bb(actx, "add rcx, 0x2a\nsub rbx, rcx")
    bb2 = make_bb(actx, "adc rbx, 0x2a\ntest rbx, rcx")
    ab = havoc_alias_part(AbstractBlock(actx, bb1))
    ab.join(bb2)

    print(ab)
    assert ab.abs_insns[0].features['exact_scheme'].is_top
    assert ab.abs_insns[1].features['exact_scheme'].is_top

    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb2)))


def test_join_equal_len_sample(random, actx):
    bb1 = make_bb(actx, "add rcx, 0x2a\nsub rbx, rcx")
    bb2 = make_bb(actx, "adc rbx, 0x2a\ntest rbx, rcx")
    ab = havoc_alias_part(AbstractBlock(actx, bb1))
    ab.join(bb2)

    print(ab)
    assert ab.abs_insns[0].features['exact_scheme'].is_top
    assert ab.abs_insns[1].features['exact_scheme'].is_top

    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb2)))

    new_bb = ab.sample()
    print(new_bb)

    assert len(new_bb) == len(bb1)

    new_ab = havoc_alias_part(AbstractBlock(actx, new_bb))
    assert ab.subsumes(new_ab)


def test_join_same_mnemonic(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a")
    bb2 = make_bb(actx, "add rbx, 0x2a")
    ab = havoc_alias_part(AbstractBlock(actx, bb1))
    ab.join(bb2)

    new_bb = ab.sample()

    print(ab)
    assert actx.iwho_ctx.extract_mnemonic(new_bb.insns[0]) == "add"


def test_join_longer(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a")
    bb2 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = havoc_alias_part(AbstractBlock(actx, bb1))
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb2)))


def test_join_longer_sample(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a")
    bb2 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = havoc_alias_part(AbstractBlock(actx, bb1))
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(actx, bb2)))

    new_bb = ab.sample()
    print(new_bb)

    assert len(bb1) <= len(new_bb) <= len(bb2)
    for new, old in zip(new_bb, bb2):
        assert new.scheme == old.scheme

    new_ab = havoc_alias_part(AbstractBlock(actx, new_bb))
    assert ab.subsumes(new_ab)


def test_aliasing_simple(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb1)

    print(ab)
    assert ab.subsumes(ab)

    str_repr = str(ab)
    assert "0:(E, 'reg0') - 1:(E, 'reg1') : must alias" in str_repr or "1:(E, 'reg1') - 0:(E, 'reg0') : must alias" in str_repr
    assert "0:(E, 'reg0') - 1:(E, 'reg0') : must not alias" in str_repr


def test_aliasing_simple_sample(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb1)

    print(ab)
    assert ab.subsumes(ab)

    str_repr = str(ab)
    assert "0:(E, 'reg0') - 1:(E, 'reg1') : must alias" in str_repr or "1:(E, 'reg1') - 0:(E, 'reg0') : must alias" in str_repr
    assert "0:(E, 'reg0') - 1:(E, 'reg0') : must not alias" in str_repr

    new_bb = ab.sample()
    print(new_bb)
    new_ab = AbstractBlock(actx, new_bb)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_aliasing_insn_choice_sample(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a\nsub rax, rbx")
    bb2 = make_bb(actx, "add rax, 0x2a\nsub rax, 0x0")
    ab = AbstractBlock(actx, bb1)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)

    str_repr = str(ab)
    assert "0:(E, 'reg0') - 1:(E, 'reg0') : must alias" in str_repr or "1:(E, 'reg0') - 0:(E, 'reg0') : must alias" in str_repr

    new_bb = ab.sample()
    print(new_bb)
    new_ab = AbstractBlock(actx, new_bb)
    print(new_ab)
    # assert ab.subsumes(new_ab)
    # We cannot assert this, because by sampling an instruction with fewer
    # operand schemes, some alias information is lost and therefore set to TOP.
    # That is an indication that the natural thing to have for such a case
    # would be BOTTOM instead of TOP.


def test_aliasing_different_widths_01_sample(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a\nsub ebx, eax")
    ab = AbstractBlock(actx, bb1)

    print(ab)
    assert ab.subsumes(ab)

    str_repr = str(ab)
    assert "0:(E, 'reg0') - 1:(E, 'reg1') : must alias" in str_repr or "1:(E, 'reg1') - 0:(E, 'reg0') : must alias" in str_repr
    assert "0:(E, 'reg0') - 1:(E, 'reg0') : must not alias" in str_repr

    new_bb = ab.sample()
    print(new_bb)
    new_ab = AbstractBlock(actx, new_bb)
    assert ab.subsumes(new_ab)


def check_sampling_consistent(ab, all_fail=False):
    n = 10

    successes = 0

    for i in range(n):
        try:
            ab.sample()
            successes += 1
        except SamplingError as e:
            print(e)

    if all_fail:
        return successes == 0
    else:
        return successes == n


def test_aliasing_different_widths_02_sample(random, actx):
    bb1 = make_bb(actx, "add ebx, edx\nsub rdx, rbx")
    bb2 = make_bb(actx, "add eax, edx\nsub rdx, rbx")

    ab = AbstractBlock(actx, bb1)
    ab.join(bb2)

    assert check_sampling_consistent(ab)

def test_aliasing_different_types_01_sample(random, actx):
    bb1 = make_bb(actx, "add rbx, rdx\nsub rbx, rcx")
    bb2 = make_bb(actx, "add rbx, rdx\nvsubpd xmm1, xmm2, xmm3")

    frankensteins_ab = AbstractBlock(actx, bb1)
    ab2 = AbstractBlock(actx, bb2)

    frankensteins_ab.abs_insns[1] = ab2.abs_insns[1]
    # This construct is not possible to achieve in "nature", since we cannot be
    # sure that the second insn is a vector insn and that its operand should
    # alias with a GPR operand (hence the name).
    # However, by expanding the insn component, we could sample a vetor
    # instruction and get a similar case that would have to be resolved
    # somehow.

    assert check_sampling_consistent(frankensteins_ab)


def test_aliasing_complex_constraints_01(random, actx):
    bb = make_bb(actx, "add rdx, rdx\nadd rdx, rdx\nadd rdx, rdx")
    ab = AbstractBlock(actx, bb)

    assert check_sampling_consistent(ab)

    sampled_bb = ab.sample()
    operands = set()
    for i in bb.insns:
        for k, op in i._operands.items():
            operands.add(op)
    assert len(operands) == 1


@pytest.mark.xfail # Here, the aliasing info does not encode a valid partition.
                   # We currently omit a test for this because it should not
                   # happen anyway and would only make the normal path slower.
def test_aliasing_complex_constraints_02(random, actx):
    bb = make_bb(actx, "add rdx, rdx\nadd rdx, rdx")
    ab = AbstractBlock(actx, bb)

    assert check_sampling_consistent(ab)

    aliasing_items = list(ab.abs_aliasing._aliasing_dict.items())
    (k1, k2), af1 = aliasing_items[0]
    af1.val = True

    nv = None
    for (k3, k4), af2 in aliasing_items:
        if (k3, k4) == (k1, k2):
            continue
        if k3 == k2:
            af2.val = False
            nv = k4
            break
        if k4 == k2:
            af2.val = False
            nv = k3
            break
    else:
        assert False

    af3 = ab.abs_aliasing._aliasing_dict[(k1, nv)]
    af3.val = True

    for l, v in aliasing_items:
        if l not in [(k1, k2), (k3, k4), (k1, nv)]:
            v.set_to_top()

    try:
        print(ab)
        print(ab.sample())
    except:
        pass
    assert check_sampling_consistent(ab, all_fail=True)

def test_aliasing_complex_constraints_03(random, actx):
    bb = make_bb(actx, "add rax, 0x2a\nadd rax, 0x2a")
    ab = AbstractBlock(actx, bb)

    assert check_sampling_consistent(ab)

    for k, af in ab.abs_aliasing._aliasing_dict.items():
        if af.val == True:
            af.val = False
            break

    # The "add rax, IMM" instructions have an InsnScheme where rax is a fixed
    # operand (because they have a special encoding).
    assert check_sampling_consistent(ab, all_fail=True)

def test_deepcopy(random, actx):
    bb = make_bb(actx, "add rax, 0x2a\nsub ebx, eax")
    ab = AbstractBlock(actx, bb)

    new_ab = copy.deepcopy(ab)

    assert new_ab.subsumes(ab)
    assert ab.subsumes(new_ab)


def test_expand_subsumes(random, actx):
    bb = make_bb(actx, "add rax, 0x2a\nsub ebx, eax")
    ab = AbstractBlock(actx, bb)

    for ex, b in ab.get_possible_expansions():
        new_ab = copy.deepcopy(ab)
        assert new_ab.subsumes(ab) and ab.subsumes(new_ab)

        new_ab.apply_expansion(ex)

        assert new_ab.subsumes(ab)
        assert not ab.subsumes(new_ab)


def test_expand_terminates(random, actx):
    bb = make_bb(actx, "add rax, 0x2a\nsub ebx, eax")
    ab = AbstractBlock(actx, bb)

    for i in range(100): # an arbitrary, but hopefully large enough bound
        print(f"iteration {i}")
        prev_ab = copy.deepcopy(ab)
        expansions = sorted(ab.get_possible_expansions())
        if len(expansions) == 0:
            break

        chosen_exp, b = expansions[0]

        ab.apply_expansion(chosen_exp)

        assert ab.subsumes(prev_ab) and not prev_ab.subsumes(ab)
    else:
        # we probably hit an endless loop here (or the range is not large
        # enough)
        assert False

possible_block_strs =[
        ["add rax, 0x2a"],
        ["add rax, 0x2a\nsub ebx, eax"],
        ["add rax, 0x2a\nsub ebx, eax", "add rax, 0x2a\nsub ebx, eax"],
        ["add rax, 0x2a\nsub ebx, eax", "add rax, 0x2a\nsub eax, eax"],
        ["add rax, 0x2a\nsub ebx, eax", "sub rax, 0x2a\nsub ebx, eax"],
        ["add rax, 0x2a\nvsubpd xmm0, xmm1, xmm2", "add rax, 0x2a\nsub eax, eax"],
    ]

@pytest.mark.parametrize("block_strs", possible_block_strs)
def test_json(actx, block_strs):
    original_ab = None

    for block_str in block_strs:
        bb = make_bb(actx, block_str)
        if original_ab is None:
            original_ab = AbstractBlock(actx, bb)
        else:
            original_ab.join(bb)

    json_dict = original_ab.to_json_dict()

    direct_decoded_ab = AbstractBlock.from_json_dict(actx, json_dict)

    assert str(original_ab) == str(direct_decoded_ab)

    json_str = json.dumps(actx.json_ref_manager.introduce_json_references(json_dict))
    decoded_json_dict = actx.json_ref_manager.resolve_json_references(json.loads(json_str))

    json_decoded_ab = AbstractBlock.from_json_dict(actx, decoded_json_dict)
    assert str(original_ab) == str(json_decoded_ab)


def test_sample_blacklist(random):
    config = {
        "insn_feature_manager": {
            "features": [
                ["exact_scheme", "singleton"],
                ["mnemonic", "singleton"],
                ["opschemes", "subset"],
            ]
        },
        "iwho": { "context_specifier": "x86_uops_info",
            "filters": ["no_cf", "only_mnemonics:add:sub"]
            },
        "interestingness": None,
        "measurement_db": None,
        "predmanager": None,
    }

    actx = AbstractionContext(config)

    ab = AbstractBlock.make_top(actx, 1)

    def check_mnemonics(ab, intended_mnemonics, sample_args={}):
        used_mnemonics = set()
        for i in range(10):
            bb = ab.sample(**sample_args)
            used_mnemonics.add(actx.iwho_ctx.extract_mnemonic(bb.insns[0]))

        return used_mnemonics == set(intended_mnemonics)

    assert check_mnemonics(ab, {"add", "sub"})
    assert not check_mnemonics(ab, {"add"})
    assert not check_mnemonics(ab, {"sub"})

    bl = []
    for ischeme in actx.iwho_ctx.filtered_insn_schemes:
        if actx.iwho_ctx.extract_mnemonic(ischeme) == 'sub':
            bl.append(ischeme)

    assert check_mnemonics(ab, {"add"}, sample_args={"insn_scheme_blacklist": bl})


def test_log_ub_feature(actx_complex):
    # This test checks whether the join of the log domain respects the upper
    # bound to go to top.
    actx = actx_complex

    bb = make_bb(actx, 'CPUID')
    ab = AbstractBlock(actx, bb)

    features = actx.insn_feature_manager.extract_features(bb.insns[0].scheme)
    num_uops = len(features['uops_on_SKL'])

    ai = ab.abs_insns[0]

    assert ai.features['uops_on_SKL'].is_top(), "The CPUID instruction has more than 31 uops on SKL, namely {}".format(num_uops)

    ai.features['exact_scheme'].set_to_top()

    print(ab)

    ab.sample()

