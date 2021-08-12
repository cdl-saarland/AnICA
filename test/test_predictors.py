#!/usr/bin/env -S pytest -s

import pytest
import os
import sys

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

