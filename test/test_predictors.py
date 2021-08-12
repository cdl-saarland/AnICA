#!/usr/bin/env -S pytest -s

import pytest
import os
import sys
import random as rand

import iwho

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractioncontext import AbstractionContext
from devidisc.utils import Timer

from test_utils import *


def test_all():
    Timer.enabled = True

    with Timer('startup', log=False):
        actx = AbstractionContext(config={})

        test_bb = make_bb(actx, "add rax, 0x2a\nsub [rbx + 0x8], rcx")

    errors = 0
    for key in actx.predmanager.pred_registry.keys():
        actx.predmanager.set_predictors([key])

        with Timer(key, log=False) as timer:
            res = actx.predmanager.eval_with_all([test_bb])

            single_res = next(iter(res))[1]

        v = single_res[key].get('TP', None)
        if v is None or v <= 0.0:
            print(f"{key} does not work! (result: {single_res})", end='')
            errors += 1
        else:
            print(f"{key} works.", end='')

        print(f" (time: {timer.seconds_passed:.5} seconds)")

    assert errors == 0


def test_ithemal_parallel():
    rand.seed(424242)
    Timer.enabled = True

    actx = AbstractionContext(config={})

    test_bbs = [
            make_bb(actx, "add rax, 0x2a\nsub [rbx + 0x8], rcx\nadd rax, 0x2a\nsub [rbx + 0x8], rcx"),
            make_bb(actx, "sub [rbx + 0x8], rcx"),
            make_bb(actx, "add rax, 0x2a\nadd rax, 0x2a"),
            make_bb(actx, "add rax, 0x2a"),
        ]

    workload_size = 5
    # workload_size = 20
    workload = [rand.choice(test_bbs) for i in range(workload_size)]

    actx.predmanager.set_predictors(['ithemal.bhive.skl', 'ithemal.bhive.hsw'])

    pool = actx.predmanager.pool

    with Timer('parallel', log=False) as timer:
        res = actx.predmanager.eval_with_all(workload)
        parallel_results = [x[1] for x in res]

    print("\nparallel time: {}".format(timer.seconds_passed))

    # this disables multiprocessing in the predmanager
    actx.predmanager.pool = None

    with Timer('sequential', log=False) as timer:
        res = actx.predmanager.eval_with_all(workload)
        sequential_results = [x[1] for x in res]

    print("\nsequential time: {}".format(timer.seconds_passed))

    for par_res, seq_res in zip(parallel_results, sequential_results):
        assert par_res == seq_res

    assert any(map(lambda x: x['ithemal.bhive.skl']['TP'] != x['ithemal.bhive.hsw']['TP'], sequential_results))

