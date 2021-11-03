#!/usr/bin/env pytest

import pytest

from copy import deepcopy
import os
import sys

import iwho

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from anica.abstractblock import AbstractBlock
from anica.abstractioncontext import AbstractionContext

from anica.satsumption import check_subsumed, check_subsumed_aa, check_subsumed_arbitrary_order

from test_utils import *



def test_satsumption_trivial_01(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb1)
    assert check_subsumed(bb1, ab)

def test_satsumption_trivial_02(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb1)
    bb2 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    assert check_subsumed(bb2, ab)


def test_satsumption_negative_01(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a")
    ab = AbstractBlock(actx, bb1)
    bb2 = make_bb(actx, "sub rbx, rax")
    assert not check_subsumed(bb2, ab)

def test_satsumption_negtive_02(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb1)
    bb2 = make_bb(actx, "add rax, 0x2a")
    assert not check_subsumed(bb2, ab)

def test_satsumption_negtive_03(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb1)
    print(ab)
    bb2 = make_bb(actx, "add rax, 0x2a\nsub rbx, rcx")
    assert not check_subsumed(bb2, ab)


def test_satsumption_swapped_01(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb1)
    bb2 = make_bb(actx, "sub rbx, rax\nadd rax, 0x2a")
    assert check_subsumed(bb2, ab)

def test_satsumption_swapped_02(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax\nvaddpd ymm1, ymm2, ymm3")
    ab = AbstractBlock(actx, bb1)
    bb2 = make_bb(actx, "sub rbx, rax\nvaddpd ymm1, ymm3, ymm2\nadd rax, 0x2a")
    assert check_subsumed(bb2, ab)

def test_satsumption_more_general_03(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb1)
    bb2 = make_bb(actx, "sub rbx, rax\nvaddpd ymm1, ymm3, ymm2\nadd rax, 0x2a")
    assert check_subsumed(bb2, ab)

def test_satsumption_regression_01(random):
    config = {
        "iwho": { "context_specifier": "x86_uops_info" },
        "interestingness": None,
        "measurement_db": None,
        "predmanager": None,
    }
    my_actx = AbstractionContext(config)

    bb = make_bb(my_actx, """
        vfmsubadd231pd ymm5, ymm0, ymmword ptr [rbx + 0x40]
        lock sbb byte ptr [rbx + 0x40], 0x2a
        xor r12w, word ptr [rbx + 0x40]
        rep cmpsw word ptr [rsi], word ptr es:[rdi]
        or dword ptr [rbx + 0x40], 0x2a
    """)

    ab = AbstractBlock.make_top(my_actx, 1)
    op_feature = ab.abs_insns[0].features['opschemes']
    op_feature.val = {'R:[rsi]'}
    print(bb.get_asm())
    print(ab)
    assert check_subsumed(bb, ab, print_assignment=True)

def test_satsumption_regression_02(random):
    config = {
        "iwho": { "context_specifier": "x86_uops_info" },
        "interestingness": None,
        "measurement_db": None,
        "predmanager": None,
    }
    my_actx = AbstractionContext(config)

    bb = make_bb(my_actx, """
        rep movsq qword ptr es:[rdi], qword ptr [rsi]
        pcmpeqb xmm5, xmmword ptr [rbx + 0x40]
    """)

    ab = AbstractBlock.make_top(my_actx, 2)
    ab.abs_insns[1].features['category'].val = "STRINGOP"
    mem_feature = ab.abs_insns[1].features['memory_usage']
    mem_feature.is_in_subfeature.val = True
    mem_feature.subfeature.val = {'R', 'W'}
    print(bb.get_asm())
    print(ab)
    assert check_subsumed(bb, ab, print_assignment=True)

def test_satsumption_aa_01(random, actx):
    # Every block should subsume itself.
    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb1)
    assert check_subsumed_aa(ab, ab)

def test_satsumption_aa_02(random, actx):
    # Every block should subsume itself.
    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb1)

    ab_exp = deepcopy(ab)
    ab_exp.apply_expansion(ab_exp.get_possible_expansions()[0][0])

    # expanding the subsumer should preserve the subsumption
    assert check_subsumed_aa(ab, ab_exp)

    # maybe not in the first step, but eventually we should have expanded
    # ab_exp enough that it represents strictly more basic blocks
    while check_subsumed_aa(ab_exp, ab):
        possible_expansions = ab_exp.get_possible_expansions()
        if len(possible_expansions) == 0:
            print(ab)
            print(ab_exp)
        assert len(possible_expansions) > 0
        ab_exp.apply_expansion(possible_expansions[0][0])
        # all the time, the original subsumption should not be violated
        assert check_subsumed_aa(ab, ab_exp)
    # if we leave the loop, we managed to get a sufficiently expanded ab_exp.

def test_satsumption_aa_03(random, actx):
    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab = AbstractBlock(actx, bb1)

    ab_exp = deepcopy(ab)

    alias = ab_exp.abs_aliasing
    alias_expansions = alias.get_possible_expansions()
    alias.apply_expansion(alias_expansions[0][0])

    assert check_subsumed_aa(ab, ab_exp)
    assert not check_subsumed_aa(ab_exp, ab)

def test_satsumption_aa_04(random, actx):
    # comparing different lengths should also be possible

    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab1 = AbstractBlock(actx, bb1)

    bb2 = make_bb(actx, "add rax, 0x2a")
    ab2 = AbstractBlock(actx, bb2)

    assert check_subsumed_aa(ab1, ab2)
    assert not check_subsumed_aa(ab2, ab1)

def test_satsumption_aa_05(random, actx):
    # comparing different lengths should also be possible

    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab1 = AbstractBlock(actx, bb1)

    bb2 = make_bb(actx, "sub rbx, rax")
    ab2 = AbstractBlock(actx, bb2)

    assert check_subsumed_aa(ab1, ab2)
    assert not check_subsumed_aa(ab2, ab1)

def test_satsumption_aa_06(random, actx):
    # these are not subsuming each other

    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab1 = AbstractBlock(actx, bb1)

    bb2 = make_bb(actx, "xor rbx, rax")
    ab2 = AbstractBlock(actx, bb2)

    assert not check_subsumed_aa(ab1, ab2)
    assert not check_subsumed_aa(ab2, ab1)

def test_satsumption_aa_07(random, actx):
    # these are not subsuming each other

    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab1 = AbstractBlock(actx, bb1)

    bb2 = make_bb(actx, "xor rax, 0x2a\nsub rbx, rax")
    ab2 = AbstractBlock(actx, bb2)

    assert not check_subsumed_aa(ab1, ab2)
    assert not check_subsumed_aa(ab2, ab1)

def test_satsumption_aa_08(random, actx):
    # these are not subsuming each other

    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab1 = AbstractBlock(actx, bb1)

    bb2 = make_bb(actx, "sub rax, 0x2a\nsub rbx, rax")
    ab2 = AbstractBlock(actx, bb2)

    assert not check_subsumed_aa(ab1, ab2)
    assert not check_subsumed_aa(ab2, ab1)

def test_satsumption_aa_09(random, actx):
    # reordering should be fine

    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax")
    ab1 = AbstractBlock(actx, bb1)

    bb2 = make_bb(actx, "sub rbx, rax\nadd rax, 0x2a")
    ab2 = AbstractBlock(actx, bb2)

    assert check_subsumed_aa(ab1, ab2)
    assert check_subsumed_aa(ab2, ab1)


def test_satsumption_ca_fixed_order_01(random, actx):

    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax\nor rdx, rbx")

    bb2 = make_bb(actx, "add rax, 0x2a\nor rdx, rbx\nsub rbx, rax")
    ab2 = AbstractBlock(actx, bb2)

    assert check_subsumed_arbitrary_order(bb1, ab2)
    assert not check_subsumed(bb1, ab2)

def test_satsumption_ca_fixed_order_02(random, actx):

    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax\nor rdx, rbx")

    bb2 = make_bb(actx, "or rdx, rbx\nadd rax, 0x2a\nsub rbx, rax")
    ab2 = AbstractBlock(actx, bb2)

    assert check_subsumed_arbitrary_order(bb1, ab2)
    assert check_subsumed(bb1, ab2)

def test_satsumption_ca_fixed_order_03(random, actx):

    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax\nor rdx, rbx")

    bb2 = make_bb(actx, "or rdx, rbx\nadd rax, 0x2a")
    ab2 = AbstractBlock(actx, bb2)

    assert check_subsumed_arbitrary_order(bb1, ab2)
    assert check_subsumed(bb1, ab2)

def test_satsumption_ca_fixed_order_04(random, actx):

    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax\nor rdx, rbx")

    bb2 = make_bb(actx, "or rdx, rbx\nsub rbx, rax")
    ab2 = AbstractBlock(actx, bb2)

    assert check_subsumed_arbitrary_order(bb1, ab2)
    assert check_subsumed(bb1, ab2)


def test_satsumption_ca_fixed_order_05(random, actx):

    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax\nadd rax, 0x2a")

    bb2 = make_bb(actx, "or rdx, rbx\nadd rax, 0x2a\nadd rax, 0x2a")
    ab2 = AbstractBlock(actx, bb2)

    assert not check_subsumed_arbitrary_order(bb1, ab2)
    assert not check_subsumed(bb1, ab2)

def test_satsumption_ca_fixed_order_06(random, actx):

    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax\nadd rax, 0x2a")

    bb2 = make_bb(actx, "sub rbx, rax\nadd rax, 0x2a\nadd rax, 0x2a")
    ab2 = AbstractBlock(actx, bb2)

    assert check_subsumed_arbitrary_order(bb1, ab2)
    assert check_subsumed(bb1, ab2)

def test_satsumption_ca_fixed_order_07(random, actx):

    bb1 = make_bb(actx, "add rax, 0x2a\nsub rbx, rax\nadd rax, 0x2a\nor rdx, rbx")

    bb2 = make_bb(actx, "sub rbx, rax\nadd rax, 0x2a\nor rdx, rbx")
    ab2 = AbstractBlock(actx, bb2)

    assert check_subsumed(bb1, ab2)
    assert check_subsumed_arbitrary_order(bb1, ab2)

def test_satsumption_ca_fixed_order_08(random, actx):

    bb1 = make_bb(actx, "sub rbx, rax\nadd rax, 0x2a\nadd rax, 0x2a\nor rdx, rbx")

    bb2 = make_bb(actx, "sub rbx, rax\nadd rax, 0x2a\nor rdx, rbx")
    ab2 = AbstractBlock(actx, bb2)

    assert check_subsumed(bb1, ab2)
    assert check_subsumed_arbitrary_order(bb1, ab2)

