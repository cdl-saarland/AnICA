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
from devidisc.abstractionconfig import AbstractionConfig
from devidisc.discovery import discover, generalize
from devidisc.predmanager import PredictorManager
from devidisc.witness import WitnessTrace


def extract_mnemonic(insn_str):
    ctx = iwho.get_context("x86")
    return ctx.extract_mnemonic(insn_str)

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


@pytest.fixture
def random():
    rand.seed(0)

@pytest.fixture(scope="module")
def ctx():
    return iwho.get_context("x86")

@pytest.fixture(scope="function")
def acfg(ctx):
    predman = PredictorManager(None)
    acfg = AbstractionConfig(ctx, max_block_len=4, predmanager=predman)

    acfg.generalization_batch_size = 10
    acfg.discovery_batch_size = 10
    acfg.mostly_interesting_ratio = 1.0

    yield acfg
    predman.close()

def add_preds(acfg, preds):
    predman = acfg.predmanager
    for p in preds:
        add_to_predman(predman, p)

def make_bb(ctx, asm):
    if isinstance(ctx, AbstractionConfig):
        ctx = ctx.ctx
    return iwho.BasicBlock(ctx, ctx.parse_asm(asm))


def test_interestingness_error(random, acfg):
    # errors should be handled gracefully and are interesting
    add_preds(acfg, [CountPredictor(), ErrorPredictor()])

    bbs = []
    bbs.append(make_bb(acfg, "sub rax, 0x2a"))

    assert acfg.is_mostly_interesting(bbs)


def test_interestingness_01(random, acfg):
    add_preds(acfg, [CountPredictor(), AddBadPredictor()])

    bbs = []
    bbs.append(make_bb(acfg, "add rax, 0x2a"))

    assert acfg.is_mostly_interesting(bbs)

def test_interestingness_02(random, acfg):
    add_preds(acfg, [CountPredictor(), AddBadPredictor()])

    bbs = []
    bbs.append(make_bb(acfg, "sub rax, 0x2a"))

    assert not acfg.is_mostly_interesting(bbs)

def test_interestingness_03(random, acfg):
    add_preds(acfg, [CountPredictor(), AddBadPredictor()])

    bbs = []
    bbs.append(make_bb(acfg, "add rbx, rax\nsub rax, 0x2a"))

    assert acfg.is_mostly_interesting(bbs)

def _check_trace_json(acfg, tr):
    res_ab = tr.replay(validate=True)

    json_dict = acfg.introduce_json_references(tr.to_json_dict())
    print(json_dict)
    json_str = json.dumps(json_dict)
    print(json_str)
    loaded_dict = acfg.resolve_json_references(json.loads(json_str))
    loaded_trace = WitnessTrace.from_json_dict(acfg, loaded_dict)
    loaded_ab = loaded_trace.replay(validate=True)
    assert loaded_ab.subsumes(res_ab)
    assert res_ab.subsumes(loaded_ab)

def test_witness_trace_01(random, acfg):
    bb = make_bb(acfg, "add rax, 0x2a\nsub rbx, rax")
    abb = AbstractBlock(acfg, bb)

    tr = WitnessTrace(abb)

    for i in range(10):
        token, action = abb.expand([])
        assert token is not None
        tr.add_taken_expansion(token, action, 42)

    res_ab = tr.replay(validate=True)

    assert abb.subsumes(res_ab)
    assert res_ab.subsumes(abb)

    _check_trace_json(acfg, tr)


def test_generalize_01(random, acfg):
    add_preds(acfg, [CountPredictor(), AddBadPredictor()])

    bb = make_bb(acfg, "add rax, 0x2a")

    abb = AbstractBlock(acfg, bb)

    gen_abb, trace = generalize(acfg, abb)

    print(trace)

    assert gen_abb.subsumes(abb)

    mnemonic_feature = gen_abb.abs_insns[0].features['mnemonic']
    assert mnemonic_feature.val == "add"

    trace.replay(validate=True)

    _check_trace_json(acfg, trace)

def test_generalize_02(random, acfg):
    add_preds(acfg, [CountPredictor(), AddBadPredictor()])

    # this one is not interesting in the first place, so it should not change
    bb = make_bb(acfg, "sub rax, 0x2a")

    abb = AbstractBlock(acfg, bb)

    gen_abb, trace = generalize(acfg, abb)

    print(trace)

    assert gen_abb.subsumes(abb)
    assert abb.subsumes(gen_abb)

    assert abb.abs_insns[0].features['exact_scheme'] == gen_abb.abs_insns[0].features['exact_scheme']

    res_ab = trace.replay(validate=True)

    _check_trace_json(acfg, trace)

def test_generalize_03(random, acfg):
    add_preds(acfg, [CountPredictor(), AddBadPredictor()])

    bb = make_bb(acfg, "add rax, 0x2a\nsub rbx, rax")

    abb = AbstractBlock(acfg, bb)

    gen_abb, trace = generalize(acfg, abb)

    print(trace)

    assert gen_abb.subsumes(abb)

    mnemonic_feature = gen_abb.abs_insns[0].features['mnemonic']
    assert mnemonic_feature.val == "add"

    res_ab = trace.replay(validate=True)

    _check_trace_json(acfg, trace)


if __name__ == "__main__":
    rand.seed(0)
    init_logging("info")
    predman = PredictorManager(None)
    ctx = iwho.get_context("x86")
    acfg = AbstractionConfig(ctx, max_block_len=4, predmanager=predman)

    acfg.generalization_batch_size = 10
    acfg.discovery_batch_size = 10
    acfg.mostly_interesting_ratio = 1.0

    test_generalize_03(None, acfg)

    # import cProfile
    # cProfile.run('test_generalize_03(None, acfg)')
    # predman.close()
