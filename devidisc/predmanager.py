""" TODO document
"""

import multiprocessing
from multiprocessing import Pool


from functools import partial


def evaluate_bb(bb, pred):
    try:
        result = pred.evaluate(bb, disable_logging=True)
    except Exception as e:
        result = "an exception occured: " + str(e)
    return result

def evaluate_multiple(bb, preds):
    res = dict()
    for pred in preds:
        res[pred.key] = evaluate(bb, pred)
    return res


class LightBBWrapper:
    """ Light-weight wrapper of all things necessary to get the hex
    representation of a BasicBlock.

    The key is the execution time distribution:
    Creating this wrapper is fast, serializing it is efficient (since nothing
    unnecessary from the iwho context is present), and `get_hex()` does the
    heavy lifting (i.e. calls to the coder, which might require expensive
    subprocesses).

    This makes this very effective to use as a task for a PredictorManager,
    since all expensive things can be done by the process pool.

    This could be considered a hack.
    """
    def __init__(self, bb):
        self.asm_str = bb.get_asm()
        self.coder = bb.context.coder
        self.hex = None

    def get_hex(self):
        if self.hex is None:
            self.hex = self.coder.asm2hex(self.asm_str)
        return self.hex

    def get_asm(self):
        return self.asm_str


class PredictorManager:
    def __init__(self, num_threads=None):
        if num_threads is None:
            num_threads = multiprocessing.cpu_count()
        self.pool = Pool(num_threads)

        self.predictors = []

    def do(self, pred, bbs, lazy=True):
        """ Use the given predictor to predict inverse throughputs for all
        basic blocks in the given list.

        If lazy is true, return an asynchronous iterator for the results and
        return before they are all predicted.
        If lazy is false, return a complete list of predictions (awaiting all
        results).
        """
        tasks = map(lambda x: LightBBWrapper(x), bbs)
        results = self.pool.imap(partial(evaluate_bb, pred=pred), tasks)
        if not lazy:
            results = list(results)
        return results # also use zip(bbs, results) here?

    def eval_with_all(self, bbs):
        """TODO document"""
        tasks = map(lambda x: LightBBWrapper(x), bbs)
        results = self.pool.imap(partial(evaluate_multiple, preds=self.predictors), tasks)
        return zip(bbs, results)



