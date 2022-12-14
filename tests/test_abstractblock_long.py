#!/usr/bin/env pytest

import pytest

import itertools
import os
import sys

import iwho
from iwho.x86 import DefaultInstantiator

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from anica.abstractblock import AbstractBlock

from test_utils import *


def test_join_everything(actx):
    # see what happens if we join an instance of every insnscheme together

    instor = DefaultInstantiator(actx.iwho_ctx)

    ab = havoc_alias_part(AbstractBlock(actx, None))
    ab_pre = havoc_alias_part(AbstractBlock(actx, None))

    for scheme in actx.iwho_ctx.filtered_insn_schemes:
        # create a BB with only an instruction instance of this scheme
        bb = iwho.BasicBlock(actx.iwho_ctx, [instor(scheme)])

        ab.join(bb)

        # every abstract block should subsume itself
        assert ab.subsumes(ab)

        # joining things together should only go up in the join semi-lattice
        assert ab.subsumes(ab_pre)

        ab_pre.join(bb)

        # sample a block an check that it is subsumed
        new_bb = ab.sample()
        new_ab = havoc_alias_part(AbstractBlock(actx, new_bb))
        assert ab.subsumes(new_ab)


def test_join_every_pair(actx):
    # see what happens if we join instance pairs for every pair of insn schemes
    # together.

    instor = DefaultInstantiator(actx.iwho_ctx)

    # only take every 50th insn, since this test takes a long time otherwise
    reduced_schemes = actx.iwho_ctx.filtered_insn_schemes[::50]

    for scheme1, scheme2 in itertools.combinations(reduced_schemes, 2):
        ab = havoc_alias_part(AbstractBlock(actx, None))
        bb1 = iwho.BasicBlock(actx.iwho_ctx, [instor(scheme1)])
        bb2 = iwho.BasicBlock(actx.iwho_ctx, [instor(scheme2)])
        ab.join(bb1)
        ab.join(bb2)

        assert ab.subsumes(ab)

        ab1 = havoc_alias_part(AbstractBlock(actx, bb1))
        ab2 = havoc_alias_part(AbstractBlock(actx, bb2))

        assert ab.subsumes(ab1)
        assert ab.subsumes(ab2)

        new_bb = ab.sample()
        new_ab = havoc_alias_part(AbstractBlock(actx, new_bb))
        assert ab.subsumes(new_ab)

