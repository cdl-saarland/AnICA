""" TODO document
"""

from datetime import datetime
import json
import multiprocessing
from multiprocessing import Pool
import socket


from functools import partial


def evaluate_bb(bb, pred):
    try:
        result = pred.evaluate(bb, disable_logging=True)
    except Exception as e:
        result = { 'TP': None, 'error': "an exception occured: " + str(e) }
    return result

def evaluate_multiple(bb, preds):
    res = dict()
    for pkey, pred in preds:
        res[pkey] = evaluate_bb(bb, pred)
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
    """ A helper class to work with a number of iwho.Predictors, to
    conveniently support multiprocessing.

    Make sure to call `close()` when done using it or use it as a context
    manager:
    ```
    with PredictorManager() as predman:
        predman.register_predictor(...)
        ...
    ```

    If num_processes is 0 (the default) all available processes are used.
    If num_processes is None, no multiprocessing is used (faster for very small
    batch sizes, mainly for testing).

    Typical usage would register several Predictors in the manager and then use
    the PredictorManager methods to run (some of) them on a batch of basic
    blocks.
    """
    def __init__(self, num_processes=0):
        self.pool = None
        if num_processes is not None:
            if num_processes <= 0:
                num_processes = multiprocessing.cpu_count()
            self.pool = Pool(num_processes)

        self.predictor_map = dict()

        self.source_computer = socket.gethostname()

        self.next_result_ref = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        self.close()
        self.pool = None

    def close(self):
        """ This method should be called at the end of the lifetime of the
        PredictorManager.
        """
        if self.pool is not None:
            self.pool.close()

    def register_predictor(self, key, predictor, toolname, version, uarch):
        assert key not in self.predictor_map
        self.predictor_map[key] = {
                "predictor": predictor,
                "toolname": toolname,
                "version": version,
                "uarch": uarch,
            }

    @property
    def predictors(self):
        return [ (k, v['predictor']) for k, v in self.predictor_map.items() ]

    def do(self, pred, bbs, lazy=True):
        """ Use the given predictor to predict inverse throughputs for all
        basic blocks in the given list.

        If lazy is true, return an asynchronous iterator for the results and
        return before they are all predicted.
        If lazy is false, return a complete list of predictions (awaiting all
        results).
        """
        tasks = map(lambda x: LightBBWrapper(x), bbs)
        if self.pool is None:
            results = map(partial(evaluate_bb, pred=pred), tasks)
        else:
            results = self.pool.imap(partial(evaluate_bb, pred=pred), tasks)
        if not lazy:
            results = list(results)
        return results # also use zip(bbs, results) here?

    def eval_with_all(self, bbs):
        """TODO document"""
        tasks = map(lambda x: LightBBWrapper(x), bbs)
        if self.pool is None:
            results = map(partial(evaluate_multiple, preds=self.predictors), tasks)
        else:
            results = self.pool.imap(partial(evaluate_multiple, preds=self.predictors), tasks)
        return zip(bbs, results)

    def report_series(self, measdict):
        # TODO use database?
        result_ref = self.next_result_ref
        self.next_result_ref += 1

        report_file = "./measurements/report_series_{}.json".format(result_ref)

        with open(report_file, 'w') as f:
            json.dump(measdict, f, indent=2)

        return result_ref

    def eval_with_all_and_report(self, bbs):
        series_date = datetime.now().isoformat()

        eval_res = list(self.eval_with_all(bbs))

        measurements = []
        for bb, result in eval_res:
            predictor_runs = []
            for predkey, res in result.items():
                predmap_entry = self.predictor_map[predkey]
                tp = res.get('TP', -1.0)
                if tp is not None and tp < 0:
                    tp = None
                remark = json.dumps(res)
                predictor_runs.append({
                        "predictor": (predmap_entry["toolname"], predmap_entry["version"]),
                        "uarch": predmap_entry["uarch"],
                        "result": tp,
                        "remark": remark
                    })
            record = {
                    "input": bb.get_hex(),
                    "predictor_runs": predictor_runs,
                }
            measurements.append(record)

        measdict = {
                "series_date": series_date,
                "source_computer": self.source_computer,
                "measurements": measurements,
                }
        result_ref = self.report_series(measdict)

        return eval_res, result_ref

