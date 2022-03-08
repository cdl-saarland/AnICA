#!/usr/bin/env pytest

import pytest

import copy
from functools import partial
import json
import os
import sys

import iwho
from iwho.predictors.predictor_manager import PredictorManager

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from anica.abstractblock import AbstractBlock, SamplingError
from anica.abstractioncontext import AbstractionContext
from anica.discovery import sample_block_list, generalize

from test_utils import *


def load_test_case(config_dict, absblock_dict):
    actx = AbstractionContext(config_dict)
    absblock_dict = actx.json_ref_manager.resolve_json_references(absblock_dict)
    absblock = AbstractBlock.from_json_dict(actx, absblock_dict)
    return actx, absblock

default_config_dict = {
        "insn_feature_manager": {
            "features": [
                    ["exact_scheme", "singleton"],
                    ["mnemonic", ["editdistance", 3]],
                    ["opschemes", "subset"],
                    ["memory_usage", "subset_or_definitely_not"],
                    ["uops_on_SKL", ["log_ub", 5]],
                    ["category", "singleton"],
                    ["extension", "singleton"],
                    ["isa-set", "singleton"],
                    ["has_lock", "singleton"],
                ]
            },
        "iwho": { },
        "interestingness_metric": { },
        "discovery": { },
        "sampling": {},
        "measurement_db": None,
        "predmanager": {}
    }


class LoggingPredManagerWrapper:
    """ This is a hacked wrapper for a predictor manager to store all basic
    blocks evaluated for inspection in tests.
    """
    def __init__(self, pm):
        self.pm = pm
        self.evaluated_bbs = []

    def __getattribute__(self, name):
        if name in ('evaluated_bbs', 'pm', 'wrapped_eval_with_all_and_report'):
            return object.__getattribute__(self, name)

        if name == 'eval_with_all_and_report':
            return self.wrapped_eval_with_all_and_report

        attr = getattr(self.pm, name)
        return attr

    def wrapped_eval_with_all_and_report(self, bbs):
        self.evaluated_bbs.append(bbs[:])
        return self.pm.eval_with_all_and_report(bbs)


def test_sample_rep():
    absblock_dict = {
            "abs_insns": [
                {
                    "exact_scheme": "$SV:TOP",
                    "mnemonic": {"top": True, "base": "rep", "curr_dist": None, "max_dist": 3},
                    "opschemes": ["RW:rcx"],
                    "memory_usage": {"subfeature": [], "is_in_subfeature": "$SV:TOP"},
                    "uops_on_SKL": {"val": "$SV:TOP", "max_ub": 5},
                    "category": "$SV:TOP",
                    "extension": "$SV:TOP",
                    "isa-set": "$SV:TOP",
                    "has_lock": "$SV:TOP"
                }
            ],
            "abs_aliasing": {"aliasing_dict": [], "is_bot": False}
        }

    actx, absblock = load_test_case(default_config_dict, absblock_dict)

    num_not_scas = 0
    for x in range(10):
        bb = absblock.sample()
        print(bb)
        if 'scas' not in str(bb):
            num_not_scas += 1

    assert num_not_scas > 0


    bbs = sample_block_list(absblock, 10)

    num_not_scas = 0
    for bb in bbs:
        print(bb)
        if 'scas' not in str(bb):
            num_not_scas += 1

    assert num_not_scas > 0


def test_sample_rep_generalize():

    absblock_dict = {
            "abs_insns": [
                {
                    "exact_scheme": "$InsnScheme:rep scasw R:ax, word ptr R:es:[rdi]",
                    "mnemonic": {"top": False, "base": "rep", "curr_dist": 0, "max_dist": 3},
                    "opschemes": ["R:ax", "R:es:[rdi]", "R:flag_df", "RW:rcx"],
                    "memory_usage": {"subfeature": ["R", "S:16"], "is_in_subfeature": True},
                    "uops_on_SKL": {"val": 5, "max_ub": 5},
                    "category": "STRINGOP",
                    "extension": "BASE",
                    "isa-set": "I86",
                    "has_lock": False
                }
            ],
            "abs_aliasing": {"aliasing_dict": [], "is_bot": False}
        }

    actx, absblock = load_test_case(default_config_dict, absblock_dict)

    log_pm = LoggingPredManagerWrapper(actx.predmanager)
    actx.predmanager = log_pm
    actx.interestingness_metric.predmanager = log_pm

    num_not_scas = 0
    for x in range(10):
        bb = absblock.sample()
        print(bb)
        if 'scas' not in str(bb):
            num_not_scas += 1

    assert num_not_scas == 0

    actx.predmanager.set_predictors(['llvm-mca.13-r+a.skl', 'iaca.skl'])

    gen_ab = generalize(actx, absblock, strategy="max_benefit")

    last_series = log_pm.evaluated_bbs[-1]
    print("\n".join(map(str, last_series)))

    assert not all(map(lambda bb: 'scas' in str(bb), last_series))

    assert False
