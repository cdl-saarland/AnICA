#!/usr/bin/env pytest

import pytest

import os
import sys

import iwho

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractblock import AbstractBlock


@pytest.fixture(scope="module")
def ctx():
    return iwho.get_context("x86")


def test_concrete_ab_single_insn(ctx):
    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a"))
    ab = AbstractBlock(bb)

    new_bb = ab.sample(ctx)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme


def test_concrete_ab_single_insn_mem(ctx):
    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, [rbx + 0x20]"))
    ab = AbstractBlock(bb)

    new_bb = ab.sample(ctx)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme


def test_concrete_ab_multiple_insns(ctx):
    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(bb)

    new_bb = ab.sample(ctx)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme


def test_concrete_ab_join_equal(ctx):
    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(bb)
    ab.join(bb)

    new_bb = ab.sample(ctx)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme


def test_concrete_ab_join_different_regs(ctx):
    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rcx, 0x2b\nsub rdx, rcx"))

    ab = AbstractBlock(bb1)
    ab.join(bb2)

    new_bb = ab.sample(ctx)

    assert len(new_bb) == len(bb1)
    for new, old in zip(new_bb, bb1):
        assert new.scheme == old.scheme


def test_concrete_ab_join_different_deps(ctx):
    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rbx, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(bb1)
    ab.join(bb2)

    new_bb = ab.sample(ctx)

    assert len(new_bb) == len(bb1)
    for new, old in zip(new_bb, bb1):
        assert new.scheme == old.scheme


def test_concrete_ab_join_equal_len(ctx):
    pass


def test_concrete_ab_join_shorter(ctx):
    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rax, 0x2a"))

    ab = AbstractBlock(bb1)
    ab.join(bb2)

    new_bb = ab.sample(ctx)

    assert len(bb1) >= len(new_bb) >= len(bb2)
    for new, old in zip(new_bb, bb1):
        assert new.scheme == old.scheme


def test_concrete_ab_join_longer(ctx):
    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(bb1)
    ab.join(bb2)

    new_bb = ab.sample(ctx)

    assert len(bb1) <= len(new_bb) <= len(bb2)
    for new, old in zip(new_bb, bb2):
        assert new.scheme == old.scheme

def test_join_everything(ctx):
    # see what happens if we join an instance of every insnscheme together
    # TODO this should be moved to a separate file with long-running tests
    pass

def test_join_every_pair(ctx):
    # see what happens if we join instance pairs for every pair of insn schemes
    # together.
    # TODO this should be moved to a separate file with long-running tests
    pass

