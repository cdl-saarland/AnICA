#!/usr/bin/env pytest

import pytest

import os
import sys

import iwho

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractblock import AbstractBlock, AbstractionConfig


@pytest.fixture(scope="module")
def ctx():
    return iwho.get_context("x86")


def test_concrete_ab_single_insn(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a"))
    ab = AbstractBlock(acfg, bb)

    print(ab)
    assert ab.subsumes(ab)


def test_concrete_ab_single_insn_sample(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a"))
    ab = AbstractBlock(acfg, bb)

    print(ab)
    assert ab.subsumes(ab)

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(acfg, new_bb)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_concrete_ab_single_insn_mem(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, [rbx + 0x20]"))
    ab = AbstractBlock(acfg, bb)

    print(ab)
    assert ab.subsumes(ab)


def test_concrete_ab_single_insn_mem_sample(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, [rbx + 0x20]"))
    ab = AbstractBlock(acfg, bb)

    print(ab)
    assert ab.subsumes(ab)

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(acfg, new_bb)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_concrete_ab_multiple_insns(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(acfg, bb)

    print(ab)
    assert ab.subsumes(ab)


def test_concrete_ab_multiple_insns_sample(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(acfg, bb)

    print(ab)
    assert ab.subsumes(ab)

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(acfg, new_bb)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_sparse_sample(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(None)
    bb2.append(ctx.parse_asm("sub rbx, rax"))

    ab = AbstractBlock(acfg, bb1)
    ab.join(bb2)

    one_was_none = False
    for k in range(10):
        # it should be quite likely that at least one sample has a None insn
        # first
        new_bb = ab.sample(ctx)
        one_was_none = one_was_none or new_bb.insns[0] is None
        new_ab = AbstractBlock(acfg, new_bb)
        assert ab.subsumes(new_ab)

    assert one_was_none, "Careful, this might randomly fail!"


def test_join_equal(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(acfg, bb)
    ab.join(bb)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(AbstractBlock(acfg, bb))


def test_join_equal_sample(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb = iwho.BasicBlock(ctx)
    bb.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(acfg, bb)
    ab.join(bb)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(AbstractBlock(acfg, bb))

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb)
    for new, old in zip(new_bb, bb):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(acfg, new_bb)
    assert ab.subsumes(new_ab)
    assert new_ab.subsumes(ab)


def test_join_different_regs(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rbx, 0x2a\nsub rbx, rax"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rcx, 0x2b\nsub rdx, rcx"))

    ab = AbstractBlock(acfg, bb1)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(AbstractBlock(acfg, bb1))
    assert ab.subsumes(AbstractBlock(acfg, bb2))


def test_join_different_regs_sample(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rbx, 0x2a\nsub rbx, rax"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rcx, 0x2b\nsub rdx, rcx"))

    ab = AbstractBlock(acfg, bb1)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(AbstractBlock(acfg, bb1))
    assert ab.subsumes(AbstractBlock(acfg, bb2))

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb1)
    for new, old in zip(new_bb, bb1):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(acfg, new_bb)
    assert ab.subsumes(new_ab)


def test_join_different_deps(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rcx, 0x2a\nsub rbx, rcx"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rbx, 0x2a\nsub rbx, rcx"))

    ab = AbstractBlock(acfg, bb1)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(AbstractBlock(acfg, bb1))
    assert ab.subsumes(AbstractBlock(acfg, bb2))


def test_join_different_deps_sample(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rcx, 0x2a\nsub rbx, rcx"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rbx, 0x2a\nsub rbx, rcx"))

    ab = AbstractBlock(acfg, bb1)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(AbstractBlock(acfg, bb1))
    assert ab.subsumes(AbstractBlock(acfg, bb2))

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb1)
    for new, old in zip(new_bb, bb1):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(acfg, new_bb)
    assert ab.subsumes(new_ab)


def test_join_equal_len(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rcx, 0x2a\nsub rbx, rcx"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("adc rbx, 0x2a\ntest rbx, rcx"))

    ab = AbstractBlock(acfg, bb1)
    ab.join(bb2)

    print(ab)
    assert ab.abs_insns[0].features['exact_scheme'].is_top
    assert ab.abs_insns[1].features['exact_scheme'].is_top

    assert ab.subsumes(ab)
    assert ab.subsumes(AbstractBlock(acfg, bb1))
    assert ab.subsumes(AbstractBlock(acfg, bb2))


def test_join_equal_len_sample(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rcx, 0x2a\nsub rbx, rcx"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("adc rbx, 0x2a\ntest rbx, rcx"))

    ab = AbstractBlock(acfg, bb1)
    ab.join(bb2)

    print(ab)
    assert ab.abs_insns[0].features['exact_scheme'].is_top
    assert ab.abs_insns[1].features['exact_scheme'].is_top

    assert ab.subsumes(ab)
    assert ab.subsumes(AbstractBlock(acfg, bb1))
    assert ab.subsumes(AbstractBlock(acfg, bb2))

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(new_bb) == len(bb1)

    new_ab = AbstractBlock(acfg, new_bb)
    assert ab.subsumes(new_ab)


def test_join_shorter(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rax, 0x2a"))

    ab = AbstractBlock(acfg, bb1)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(AbstractBlock(acfg, bb1))
    assert ab.subsumes(AbstractBlock(acfg, bb2))


def test_join_shorter_sample(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rax, 0x2a"))

    ab = AbstractBlock(acfg, bb1)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(AbstractBlock(acfg, bb1))
    assert ab.subsumes(AbstractBlock(acfg, bb2))

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(bb1) >= len(new_bb) >= len(bb2)
    for new, old in zip(new_bb, bb1):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(acfg, new_bb)
    assert ab.subsumes(new_ab)


def test_join_same_mnemonic(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rbx, 0x2a"))

    ab = AbstractBlock(acfg, bb1)
    ab.join(bb2)

    new_bb = ab.sample(ctx)

    print(ab)
    assert ctx.extract_mnemonic(new_bb.insns[0]) == "add"


def test_join_longer(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(acfg, bb1)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(AbstractBlock(acfg, bb1))
    assert ab.subsumes(AbstractBlock(acfg, bb2))


def test_join_longer_sample(ctx):
    acfg = AbstractionConfig(ctx, 4)

    bb1 = iwho.BasicBlock(ctx)
    bb1.append(ctx.parse_asm("add rax, 0x2a"))

    bb2 = iwho.BasicBlock(ctx)
    bb2.append(ctx.parse_asm("add rax, 0x2a\nsub rbx, rax"))

    ab = AbstractBlock(acfg, bb1)
    ab.join(bb2)

    print(ab)
    assert ab.subsumes(ab)
    assert ab.subsumes(AbstractBlock(acfg, bb1))
    assert ab.subsumes(AbstractBlock(acfg, bb2))

    new_bb = ab.sample(ctx)
    print(new_bb)

    assert len(bb1) <= len(new_bb) <= len(bb2)
    for new, old in zip(new_bb, bb2):
        assert new.scheme == old.scheme

    new_ab = AbstractBlock(acfg, new_bb)
    assert ab.subsumes(new_ab)

