
from collections import defaultdict
import functools
import textwrap
import time

import inspect

import logging


class TimerDeco:
    @staticmethod
    def Timer(**timer_args):
        """TODO document"""
        def timer_deco_impl(func):
            @functools.wraps(func)
            def timer_wrapper_impl(*inner_args, **inner_kwargs):
                with Timer(func.__qualname__, **timer_args):
                    res = func(*inner_args, **inner_kwargs)
                return res
            return timer_wrapper_impl
        return timer_deco_impl

    @staticmethod
    def Sub(func):
        return TimerDeco.Timer(log=False, register_parent=True, accumulate=True)(func)

class Timer:

    parent_stack = []

    enabled = False

    def __init__(self, identifier, log=True, register_parent=True, accumulate=False):
        self.identifier = identifier

        self.log = log
        self.logger_name = None

        self.register_parent = register_parent
        self.accumulate = accumulate

        self.start = None
        self.seconds_passed = None

        self.sub_results = defaultdict(_init_sub_results)

    @staticmethod
    def Sub(identifier):
        return Timer(identifier, log=False, register_parent=True, accumulate=True)

    def __enter__(self):
        if not self.enabled:
            return
        frm = inspect.stack()[1]
        mod = inspect.getmodule(frm[0])
        if self.log:
            self.logger_name = mod.__name__

        if self.register_parent:
            self.parent_stack.append(self)

        self.start = time.perf_counter()
        return self

    def get_result(self):
        assert self.seconds_passed is not None
        res = "time for '{}': {} s".format(self.identifier, self.seconds_passed)
        for l in _str_sub_results(self.sub_results).split('\n'):
            if len(l) > 0:
                res += '\n' + l
        return res

    def __exit__(self, exc_type, exc_value, trace):
        if not self.enabled:
            return

        end = time.perf_counter()
        secs = (end - self.start)
        self.seconds_passed = secs

        if self.log:
            logger = logging.getLogger(self.logger_name)
            logger.info("time for '{}': {} s".format(self.identifier, secs))
            for l in _str_sub_results(self.sub_results).split('\n'):
                if len(l) > 0:
                    logger.info(l)

        self.start = None
        self.logger_name = None

        if self.register_parent:
            self.parent_stack.pop()

        if self.accumulate and len(self.parent_stack) > 0:
            self.parent_stack[-1]._add_sub_result(key=self.identifier, time=secs, sub_sub_results=self.sub_results)

    def _add_sub_result(self, key, time, sub_sub_results):
        entry = self.sub_results[key]
        entry['time'] += time
        entry['num'] += 1
        _merge_sub_results(entry['sub_results'], sub_sub_results)

def _merge_sub_results(target, sub_results):
        for k, v in sub_results.items():
            target[k]['time'] += v['time']
            target[k]['num'] += v['num']
            _merge_sub_results(target[k]['sub_results'], v["sub_results"])

def _init_sub_results():
    return {'time': 0.0, 'num': 0, 'sub_results': defaultdict(_init_sub_results)}

def _str_sub_results(sub_results):
    if len(sub_results) == 0:
        return ""

    res = []
    for k, v in sub_results.items():
        secs = v['time']
        num = v['num']
        res.append("  - acc time for '{}' ({} execuctions): {} s".format(k, num, secs))
        res.append(textwrap.indent(_str_sub_results(v['sub_results']), '  '))

    return "\n".join(res)


