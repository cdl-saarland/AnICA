import pytest


import os
import random as rand
import sys

import iwho



import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from anica.abstractioncontext import AbstractionContext

@pytest.fixture
def random():
    rand.seed(0)

@pytest.fixture(scope="module")
def actx():
    config = {
        "insn_feature_manager": {
            "features": [
                ["exact_scheme", "singleton"],
                ["mnemonic", "singleton"],
                ["opschemes", "subset"],
            ]
        },
        "iwho": { "context_specifier": "x86_uops_info" },
        "interestingness": None,
        "measurement_db": None,
        "predmanager": None,
    }
    return AbstractionContext(config)

@pytest.fixture(scope="module")
def actx_complex():
    config = {
        "insn_feature_manager": {
            "features": [
                ["exact_scheme", "singleton"],
                ["mnemonic", "singleton"],
                ["opschemes", "subset"],
                ["memory_usage", "subset_or_definitely_not"],
                ["uops_on_SKL", ["log_ub", 5]],
            ]
        },
        "iwho": { "context_specifier": "x86_uops_info" },
        "interestingness": None,
        "measurement_db": None,
        "predmanager": None,
    }
    return AbstractionContext(config)

def havoc_alias_part(absblock):
    # this sets the aliasing part of the abstract block to top
    absblock.abs_aliasing.havoc()
    return absblock

def make_bb(ctx, asm):
    if isinstance(ctx, AbstractionContext):
        ctx = ctx.iwho_ctx
    return iwho.BasicBlock(ctx, ctx.parse_asm(asm))


