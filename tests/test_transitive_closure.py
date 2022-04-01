#!/usr/bin/env pytest

import pytest

import os
import sys

import logging

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from anica.abstractblock import _transitive_closure


def check_tc(mapping, expected):
    _transitive_closure(mapping)
    assert mapping == expected

def test_tc_01():
    check_tc(
            mapping={
                0: set(),
                1: set(),
            },
            expected={
                0: set(),
                1: set(),
            },
        )

def test_tc_02():
    check_tc(
            mapping={
                0: {1},
                1: {0},
            },
            expected={
                0: {1},
                1: {0},
            },
        )

def test_tc_03():
    check_tc(
            mapping={
                0: {2},
                1: {2},
                2: {0, 1},
            },
            expected={
                0: {1, 2},
                1: {0, 2},
                2: {0, 1},
            },
        )

def test_tc_04():
    check_tc(
            mapping={
                0: {1, 2},
                1: {0, 2},
                2: {0, 1},
            },
            expected={
                0: {1, 2},
                1: {0, 2},
                2: {0, 1},
            },
        )

def test_tc_05():
    check_tc(
            mapping={
                0: {1},
                1: {2},
                2: {0},
            },
            expected={
                0: {1, 2},
                1: {0, 2},
                2: {0, 1},
            },
        )

def test_tc_06(caplog):
    caplog.set_level(logging.DEBUG)
    upper = 42
    for n in range(3, upper):
        mapping = { k: { k + 1} for k in range(n - 1)}
        mapping[n-1] = {0}
        expected = { k : set(range(n)) - {k} for k in range(n) }
        check_tc(
                mapping=mapping,
                expected=expected,
            )

def test_tc_07(caplog):
    caplog.set_level(logging.DEBUG)
    upper = 42
    for n in range(3, upper):
        mapping = { k: { k - 1} for k in range(1, n)}
        mapping[0] = {n-1}
        expected = { k : set(range(n)) - {k} for k in range(n) }
        check_tc(
                mapping=mapping,
                expected=expected,
            )


def test_tc_08():
    check_tc(
            mapping={
                0: {1},
                1: {2},
                2: {0},
                3: {4},
                4: {5},
                5: {3},
            },
            expected={
                0: {1, 2},
                1: {0, 2},
                2: {0, 1},
                3: {4, 5},
                4: {3, 5},
                5: {3, 4},
            },
        )


def test_tc_09():
    check_tc(
            mapping={
                0: {1},
                1: {2},
                2: {0},
                3: set(),
            },
            expected={
                0: {1, 2},
                1: {0, 2},
                2: {0, 1},
                3: set(),
            },
        )

def test_tc_10():
    check_tc(
            mapping={
                0: {1},
                1: {2},
                2: {0},
                3: {4},
                4: {3},
            },
            expected={
                0: {1, 2},
                1: {0, 2},
                2: {0, 1},
                3: {4},
                4: {3},
            },
        )

