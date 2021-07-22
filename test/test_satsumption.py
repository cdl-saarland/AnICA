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

