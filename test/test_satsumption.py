#!/usr/bin/env pytest

import pytest

import os
import sys

import iwho

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractblock import AbstractBlock
from devidisc.abstractioncontext import AbstractionContext

from devidisc.satsumption import check_subsumed

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

