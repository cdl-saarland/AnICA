import pytest


import os
import random as rand
import sys

import iwho



import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractioncontext import AbstractionContext

@pytest.fixture
def random():
    rand.seed(0)

@pytest.fixture(scope="module")
def actx():
    iwho_ctx = iwho.get_context("x86")
    config = {
        "insn_feature_manager": {
            "features": [
                ["exact_scheme", "singleton"],
                ["present", "singleton"],
                ["mnemonic", "singleton"],
                ["opschemes", "subset"],
            ]
        },
        "discovery": None,
        "interestingness": None,
        "measurement_db": None,
    }
    return AbstractionContext(config, iwho_ctx=iwho_ctx)

def havoc_alias_part(absblock):
    # this sets the aliasing part of the abstract block to top
    absblock.abs_aliasing.havoc()
    return absblock

def make_bb(ctx, asm):
    if isinstance(ctx, AbstractionContext):
        ctx = ctx.iwho_ctx
    return iwho.BasicBlock(ctx, ctx.parse_asm(asm))


