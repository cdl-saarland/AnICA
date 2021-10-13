""" TODO document
"""

from collections import defaultdict
from datetime import datetime
import json
import os
import pathlib
import random
import socket
from timeit import default_timer as timer

import iwho
import iwho.x86 as x86

def explore(ctx, schemes, predman, result_base_path, *, max_num_insns=10, num_batches=10, batch_size=10):
    instor = x86.RandomRegisterInstantiator(ctx)

    base_dir = pathlib.Path(result_base_path)
    timestamp = datetime.now().replace(microsecond=0).isoformat()
    curr_result_dir = base_dir / "results_{}".format(timestamp)
    os.makedirs(curr_result_dir, exist_ok=True)

    source_computer = socket.gethostname()
    print(f"Running on source machine {source_computer}")

    for batch_idx in range(num_batches):
        print(f"batch no. {batch_idx}")

        series_date = datetime.now().isoformat()

        # sample basic blocks and run them through the predictors
        start = timer()
        bbs = []
        for x in range(batch_size):
            num_insns = random.randrange(2, max_num_insns + 1)
            bb = ctx.make_bb()
            for n in range(num_insns):
                ischeme = random.choice(schemes)
                bb.append(instor(ischeme))
            bbs.append(bb)

        end = timer()
        diff = end - start
        print(f"generated {len(bbs)} blocks in {diff:.2f} seconds")

        results = dict()
        for pkey, pred in predman.predictors:
            pred_name = pkey
            start = timer()
            results[pred_name] = predman.do(pred, bbs)
            end = timer()
            diff = end - start
            print(f"started all {pred_name} jobs in {diff:.2f} seconds")

        total_tool_time = defaultdict(lambda: 0.0)

        measurements = []
        start = timer()

        keys = results.keys()
        for x, (rs, bb) in enumerate(zip(zip( *(results[k] for k in keys )), bbs)):
            predictions = dict()
            for y, k in enumerate(keys):
                res = rs[y]
                predictions[k] = res
                total_tool_time[k] += res['rt']

                tp = res.get('TP', -1.0)
                if tp < 0:
                    tp = None

                remark = json.dumps(res)

                predmap_entry = predman.predictor_map[k]
                record = {
                        "predictor": (predmap_entry["toolname"], predmap_entry["version"]),
                        "uarch": predmap_entry["uarch"],
                        "input": bb.get_hex(),
                        "result": tp,
                        "remark": remark
                    }
                measurements.append(record)


        end = timer()
        diff = end - start

        measdict = {
                "series_date": series_date,
                "source_computer": source_computer,
                "measurements": measurements,
                }

        result_file_name = curr_result_dir / f"results_batch_{batch_idx}.json"
        with open(result_file_name, "w") as f:
            json.dump(measdict, f, indent=2)

        print(f"evaluation done in {diff:.2f} seconds")
        for k, v in total_tool_time.items():
            print(f"total time spent in {k}: {v:.2f} seconds")


