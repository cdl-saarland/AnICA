#!/usr/bin/env pytest

import pytest

import itertools
import os
import sys

import iwho
from iwho.x86 import DefaultInstantiator

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractblock import AbstractBlock
from devidisc.abstractionconfig import AbstractionConfig

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


def test_join_everything(ctx):
    # see what happens if we join an instance of every insnscheme together

    acfg = AbstractionConfig(ctx, 2)

    instor = DefaultInstantiator(ctx)

    ab = havoc_alias_part(AbstractBlock(acfg))
    ab_pre = havoc_alias_part(AbstractBlock(acfg))

    for scheme in ctx.insn_schemes:
        # create a BB with only an instruction instance of this scheme
        bb = iwho.BasicBlock(ctx, [instor(scheme)])

        ab.join(bb)

        # every abstract block should subsume itself
        assert ab.subsumes(ab)

        # joining things together should only go up in the join semi-lattice
        assert ab.subsumes(ab_pre)

        ab_pre.join(bb)

        # sample a block an check that it is subsumed
        new_bb = ab.sample()
        new_ab = havoc_alias_part(AbstractBlock(acfg, new_bb))
        assert ab.subsumes(new_ab)


def test_join_every_pair(ctx):
    # see what happens if we join instance pairs for every pair of insn schemes
    # together.

    acfg = AbstractionConfig(ctx, 2)

    instor = DefaultInstantiator(ctx)

    # only take every 50th insn, since this test takes a long time otherwise
    reduced_schemes = ctx.insn_schemes[::50]

    for scheme1, scheme2 in itertools.combinations(reduced_schemes, 2):
        ab = havoc_alias_part(AbstractBlock(acfg))
        bb1 = iwho.BasicBlock(ctx, [instor(scheme1)])
        bb2 = iwho.BasicBlock(ctx, [instor(scheme2)])
        ab.join(bb1)
        ab.join(bb2)

        assert ab.subsumes(ab)

        ab1 = havoc_alias_part(AbstractBlock(acfg, bb1))
        ab2 = havoc_alias_part(AbstractBlock(acfg, bb2))

        assert ab.subsumes(ab1)
        assert ab.subsumes(ab2)

        new_bb = ab.sample()
        new_ab = havoc_alias_part(AbstractBlock(acfg, new_bb))
        assert ab.subsumes(new_ab)

