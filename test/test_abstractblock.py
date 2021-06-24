#!/usr/bin/env pytest

import pytest

import os
import random as rand
import sys

import iwho

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractblock import AbstractBlock, AbstractionConfig


@pytest.fixture
def random():
    rand.seed(0)

@pytest.fixture(scope="module")
def ctx():
    return iwho.get_context("x86")

def havoc_alias_part(absblock):
    # this sets the aliasing part of the abstract block to top by clearing
    # the respective dict (non-present entries in non-bottom abstract blocks
    # are considered top.
    absblock._abs_aliasing = dict()
    absblock.is_bot = False
    return absblock

def test_concrete_ab_single_insn(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a"))
    ab = AbstractBlock(acfg, bb)
    havoc_alias_part(ab)

    print(ab)
    assert ab.subsumes(ab)


def test_concrete_ab_single_insn_sample(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a"))
    ab = AbstractBlock(acfg, bb)
    havoc_alias_part(ab)

    print(ab)
    assert ab.subsumes(ab)

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(acfg, new_bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_concrete_ab_single_insn_mem(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, [rbx + 0x20]"))
    ab = AbstractBlock(acfg, bb)
    havoc_alias_part(ab)

    print(ab)
    assert ab.subsumes(ab)


def test_concrete_ab_single_insn_mem_sample(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, [rbx + 0x20]"))
    ab = AbstractBlock(acfg, bb)
    havoc_alias_part(ab)

    print(ab)
    assert ab.subsumes(ab)

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(acfg, new_bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_concrete_ab_multiple_insns(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(acfg, bb)
    havoc_alias_part(ab)

    print(ab)
    assert ab.subsumes(ab)


def test_concrete_ab_multiple_insns_sample(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(acfg, bb)
    havoc_alias_part(ab)

    print(ab)
    assert ab.subsumes(ab)

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(acfg, new_bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_sparse_sample(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(None)
    bb2.append(ctx.parse_asm("sub rbx, rax"))

    ab = AbstractBlock(acfg, bb1)
    havoc_alias_part(ab)
    ab.join(bb2)

    one_was_none = False
    for k in range(10):
        # it should be quite likely that at least one sample has a None insn
        # first
        new_bb = ab.sample(ctx)
        one_was_none = one_was_none or new_bb.insns[0] is None
        new_ab = AbstractBlock(acfg, new_bb)
        havoc_alias_part(new_ab)
        assert ab.subsumes(new_ab)

    assert one_was_none, "Careful, this might randomly fail!"


def test_join_equal(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(acfg, bb)
    havoc_alias_part(ab)
    ab.join(bb)

    print(ab)
    assert ab.subsumes(ab)

    new_ab = AbstractBlock(acfg, bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)


def test_join_equal_sample(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(acfg, bb)
    havoc_alias_part(ab)
    ab.join(bb)

    print(ab)
    assert ab.subsumes(ab)

    new_ab = AbstractBlock(acfg, bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(acfg, new_bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_join_different_regs(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rbx, 0x2a\nsub rbx, rax"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rcx, 0x2b\nsub rdx, rcx"))

    ab = AbstractBlock(acfg, bb1)
    havoc_alias_part(ab)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb2)))


def test_join_different_regs_sample(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rbx, 0x2a\nsub rbx, rax"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rcx, 0x2b\nsub rdx, rcx"))

    ab = AbstractBlock(acfg, bb1)
    havoc_alias_part(ab)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb2)))

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb1)
    for new, old in zip(new_bb, bb1):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(acfg, new_bb)
    havoc_alias_part(new_ab)
    assert ab.subsumes(new_ab)


def test_join_different_deps(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rcx, 0x2a\nsub rbx, rcx"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rbx, 0x2a\nsub rbx, rcx"))

    ab = AbstractBlock(acfg, bb1)
    havoc_alias_part(ab)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb2)))


def test_join_different_deps_sample(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rcx, 0x2a\nsub rbx, rcx"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rbx, 0x2a\nsub rbx, rcx"))

    ab = havoc_alias_part(AbstractBlock(acfg, bb1))
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb2)))

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb1)
    for new, old in zip(new_bb, bb1):
        assert new.scheme == old.scheme

    new_ab = havoc_alias_part(AbstractBlock(acfg, new_bb))
    assert ab.subsumes(new_ab)


def test_join_equal_len(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rcx, 0x2a\nsub rbx, rcx"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("adc rbx, 0x2a\ntest rbx, rcx"))

    ab = havoc_alias_part(AbstractBlock(acfg, bb1))
    ab.join(bb2)

    print(ab)
    assert ab.abs_insns[0].features['exact_scheme'].is_top
    assert ab.abs_insns[1].features['exact_scheme'].is_top

    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb2)))


def test_join_equal_len_sample(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rcx, 0x2a\nsub rbx, rcx"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("adc rbx, 0x2a\ntest rbx, rcx"))

    ab = havoc_alias_part(AbstractBlock(acfg, bb1))
    ab.join(bb2)

    print(ab)
    assert ab.abs_insns[0].features['exact_scheme'].is_top
    assert ab.abs_insns[1].features['exact_scheme'].is_top

    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb2)))

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb1)

    new_ab = havoc_alias_part(AbstractBlock(acfg, new_bb))
    assert ab.subsumes(new_ab)


def test_join_shorter(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rax, 0x2a"))

    ab = havoc_alias_part(AbstractBlock(acfg, bb1))
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb2)))


def test_join_shorter_sample(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rax, 0x2a"))

    ab = havoc_alias_part(AbstractBlock(acfg, bb1))
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb2)))

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(bb1) >= len(new_bb) >= len(bb2)
    for new, old in zip(new_bb, bb1):
        assert new.scheme == old.scheme

    new_ab = havoc_alias_part(AbstractBlock(acfg, new_bb))
    assert ab.subsumes(new_ab)


def test_join_same_mnemonic(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rbx, 0x2a"))

    ab = havoc_alias_part(AbstractBlock(acfg, bb1))
    ab.join(bb2)

    new_bb = ab.sample(ctx)

    print(ab)
    assert ctx.extract_mnemonic(new_bb.insns[0]) == "add"


def test_join_longer(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = havoc_alias_part(AbstractBlock(acfg, bb1))
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb2)))


def test_join_longer_sample(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = havoc_alias_part(AbstractBlock(acfg, bb1))
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb1)))
    assert ab.subsumes(havoc_alias_part(AbstractBlock(acfg, bb2)))

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(bb1) <= len(new_bb) <= len(bb2)
    for new, old in zip(new_bb, bb2):
        assert new.scheme == old.scheme

    new_ab = havoc_alias_part(AbstractBlock(acfg, new_bb))
    assert ab.subsumes(new_ab)


def test_aliasing_simple(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(acfg, bb1)

    print(ab)
    assert ab.subsumes(ab)

    str_repr = str(ab)
    assert "0:(E, 'reg0') - 1:(E, 'reg1') : must alias" in str_repr or "1:(E, 'reg1') - 0:(E, 'reg0') : must alias" in str_repr
    assert "0:(E, 'reg0') - 1:(E, 'reg0') : must not alias" in str_repr


def test_aliasing_simple_sample(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(acfg, bb1)

    print(ab)
    assert ab.subsumes(ab)

    str_repr = str(ab)
    assert "0:(E, 'reg0') - 1:(E, 'reg1') : must alias" in str_repr or "1:(E, 'reg1') - 0:(E, 'reg0') : must alias" in str_repr
    assert "0:(E, 'reg0') - 1:(E, 'reg0') : must not alias" in str_repr

    new_bb = ab.sample(ctx)
    print(new_bb)
    new_ab = AbstractBlock(acfg, new_bb)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_aliasing_insn_choice_sample(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a\nsub rax, rbx"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rax, 0x2a\nsub rax, 0x0"))

    ab = AbstractBlock(acfg, bb1)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)

    str_repr = str(ab)
    assert "0:(E, 'reg0') - 1:(E, 'reg0') : must alias" in str_repr or "1:(E, 'reg0') - 0:(E, 'reg0') : must alias" in str_repr

    new_bb = ab.sample(ctx)
    print(new_bb)
    new_ab = AbstractBlock(acfg, new_bb)
    print(new_ab)
    # assert ab.subsumes(new_ab)
    # We cannot assert this, because by sampling an instruction with fewer
    # operand schemes, some alias information is lost and therefore set to TOP.
    # That is an indication that the natural thing to have for such a case
    # would be BOTTOM instead of TOP.


def test_aliasing_different_widths_01_sample(random, ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a\nsub ebx, eax"))

    ab = AbstractBlock(acfg, bb1)

    print(ab)
    assert ab.subsumes(ab)

    str_repr = str(ab)
    assert "0:(E, 'reg0') - 1:(E, 'reg1') : must alias" in str_repr or "1:(E, 'reg1') - 0:(E, 'reg0') : must alias" in str_repr
    assert "0:(E, 'reg0') - 1:(E, 'reg0') : must not alias" in str_repr

    new_bb = ab.sample(ctx)
    print(new_bb)
    new_ab = AbstractBlock(acfg, new_bb)
    assert ab.subsumes(new_ab)


