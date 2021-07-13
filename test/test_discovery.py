#!/usr/bin/env pytest

import pytest

import json
import logging
import os
import random as rand
import sys

import iwho
from iwho.predictors import Predictor
from iwho.utils import init_logging

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractblock import AbstractBlock
from devidisc.abstractioncontext import AbstractionContext
from devidisc.discovery import discover, generalize
from devidisc.predmanager import PredictorManager
from devidisc.witness import WitnessTrace

from test_utils import *

def extract_mnemonic(insn_str):
    return iwho.x86.extract_mnemonic(insn_str)

def add_to_predman(predman, pred):
    predname = pred.predictor_name
    key_base = predname
    x = 0
    while True:
        x += 1
        key = key_base + "_{}".format(x)
        if key not in predman.predictor_map:
            break

    predman.register_predictor(key=key,
            predictor=pred,
            toolname=predname,
            version="0.1",
            uarch="any")


# Some naive predictors for testing
class CountPredictor(Predictor):
    predictor_name = "test_count"

    def evaluate(self, basic_block, *args, **kwargs):
        s = basic_block.get_asm()
        lines = s.split('\n')
        return {'TP': float(len(lines))}

class AddBadPredictor(Predictor):
    predictor_name = "test_addbad"

    def evaluate(self, basic_block, *args, **kwargs):
        s = basic_block.get_asm()
        lines = s.split('\n')
        res = 0.0
        for l in lines:
            if extract_mnemonic(l) == 'add':
                res += 2.0
            else:
                res += 1.0
        return {'TP': res}

class ErrorPredictor(Predictor):
    predictor_name = "test_error"

    def evaluate(self, basic_block, *args, **kwargs):
        raise RuntimeError("this predictor only causes errors")


@pytest.fixture(scope="function")
def actx_pred():
    iwho_ctx = iwho.get_context("x86")

    predman = PredictorManager(None)
    actx_pred = AbstractionContext(iwho_ctx, predmanager=predman)

    actx_pred.discovery_cfg.generalization_batch_size = 10
    actx_pred.discovery_cfg.discovery_batch_size = 10

    actx_pred.interestingness_metric.mostly_interesting_ratio = 1.0

    yield actx_pred
    predman.close()

def add_preds(actx_pred, preds):
    predman = actx_pred.predmanager
    for p in preds:
        add_to_predman(predman, p)


def test_interestingness_error(random, actx_pred):
    # errors should be handled gracefully and are interesting
    add_preds(actx_pred, [CountPredictor(), ErrorPredictor()])

    bbs = []
    bbs.append(make_bb(actx_pred, "sub rax, 0x2a"))

    assert actx_pred.interestingness_metric.is_mostly_interesting(bbs)[0]


def test_interestingness_01(random, actx_pred):
    add_preds(actx_pred, [CountPredictor(), AddBadPredictor()])

    bbs = []
    bbs.append(make_bb(actx_pred, "add rax, 0x2a"))

    assert actx_pred.interestingness_metric.is_mostly_interesting(bbs)[0]

def test_interestingness_02(random, actx_pred):
    add_preds(actx_pred, [CountPredictor(), AddBadPredictor()])

    bbs = []
    bbs.append(make_bb(actx_pred, "sub rax, 0x2a"))

    assert not actx_pred.interestingness_metric.is_mostly_interesting(bbs)[0]

def test_interestingness_03(random, actx_pred):
    add_preds(actx_pred, [CountPredictor(), AddBadPredictor()])

    bbs = []
    bbs.append(make_bb(actx_pred, "add rbx, rax\nsub rax, 0x2a"))

    assert actx_pred.interestingness_metric.is_mostly_interesting(bbs)[0]

def _check_trace_json(actx_pred, tr):
    res_ab = tr.replay(validate=True)

    json_dict = actx_pred.json_ref_manager.introduce_json_references(tr.to_json_dict())
    print(json_dict)
    json_str = json.dumps(json_dict)
    print(json_str)
    loaded_dict = actx_pred.json_ref_manager.resolve_json_references(json.loads(json_str))
    loaded_trace = WitnessTrace.from_json_dict(actx_pred, loaded_dict)
    loaded_ab = loaded_trace.replay(validate=True)
    assert loaded_ab.subsumes(res_ab)
    assert res_ab.subsumes(loaded_ab)

def test_witness_trace_01(random, actx_pred):
    bb = make_bb(actx_pred, "add rax, 0x2a\nsub rbx, rax")
    abb = AbstractBlock(actx_pred, bb)

    tr = WitnessTrace(abb)

    for i in range(10):
        expansions = sorted(abb.get_possible_expansions())
        assert len(expansions) > 0
        chosen = expansions[0][0]
        abb.apply_expansion(chosen)
        tr.add_taken_expansion(chosen, 42)

    res_ab = tr.replay(validate=True)

    assert abb.subsumes(res_ab)
    assert res_ab.subsumes(abb)

    _check_trace_json(actx_pred, tr)


def test_generalize_01(random, actx_pred):
    add_preds(actx_pred, [CountPredictor(), AddBadPredictor()])

    bb = make_bb(actx_pred, "add rax, 0x2a")

    abb = AbstractBlock(actx_pred, bb)

    gen_abb, trace = generalize(actx_pred, abb)

    print(trace)

    assert gen_abb.subsumes(abb)

    mnemonic_feature = gen_abb.abs_insns[0].features['mnemonic']
    assert mnemonic_feature.val == "add"

    trace.replay(validate=True)

    _check_trace_json(actx_pred, trace)

def test_generalize_02(random, actx_pred):
    add_preds(actx_pred, [CountPredictor(), AddBadPredictor()])

    # this one is not interesting in the first place, so it should not change
    bb = make_bb(actx_pred, "sub rax, 0x2a")

    abb = AbstractBlock(actx_pred, bb)

    gen_abb, trace = generalize(actx_pred, abb)

    print(trace)

    assert gen_abb.subsumes(abb)
    assert abb.subsumes(gen_abb)

    assert abb.abs_insns[0].features['exact_scheme'] == gen_abb.abs_insns[0].features['exact_scheme']

    res_ab = trace.replay(validate=True)

    _check_trace_json(actx_pred, trace)

def test_generalize_03(random, actx_pred):
    add_preds(actx_pred, [CountPredictor(), AddBadPredictor()])

    bb = make_bb(actx_pred, "add rax, 0x2a\nsub rbx, rax")

    abb = AbstractBlock(actx_pred, bb)

    gen_abb, trace = generalize(actx_pred, abb)

    print(trace)

    assert gen_abb.subsumes(abb)

    mnemonic_feature = gen_abb.abs_insns[0].features['mnemonic']
    assert mnemonic_feature.val == "add"

    res_ab = trace.replay(validate=True)

    _check_trace_json(actx_pred, trace)


if __name__ == "__main__":
    rand.seed(0)
    init_logging("info")

    iwho_ctx = iwho.get_context("x86")

    predman = PredictorManager(None)
    actx_pred = AbstractionContext(iwho_ctx, predmanager=predman)

    actx_pred.discovery_cfg.generalization_batch_size = 10
    actx_pred.discovery_cfg.discovery_batch_size = 10

    actx_pred.interestingness_metric.mostly_interesting_ratio = 1.0

    test_generalize_03(None, actx_pred)

    # import cProfile
    # cProfile.run('test_generalize_03(None, actx_pred)')
    # predman.close()
