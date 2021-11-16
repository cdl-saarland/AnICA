#!/usr/bin/env python3

""" Check how many of the BHive basic blocks are covered by our instruction
schemes.
"""

import argparse
from collections import Counter
import csv
import json
import os
import sys
import textwrap

import multiprocessing
from multiprocessing import Pool
from functools import partial

import iwho
from iwho.utils import parse_args_with_logging


import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from anica.abstractioncontext import AbstractionContext
from anica.configurable import load_json_config, pretty_print

import logging
logger = logging.getLogger(__name__)


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def decode_batch(bbs, actx_config):
    actx = AbstractionContext(config=actx_config)
    iwho_ctx = actx.iwho_ctx

    coder_errors = 0
    instantiation_errors = 0
    passes = 0
    scheme2num_bbs = Counter()
    required_schemes = []

    for idx, hex_str in enumerate(bbs):
        if len(hex_str) == 0:
            continue
        try:
            insns = iwho_ctx.decode_insns(hex_str, skip_instantiation_errors=True)
        except iwho.ASMCoderError:
            coder_errors += 1
            continue

        schemes = set()
        no_inst_error_yet = True
        for i in insns:
            if i is None:
                if no_inst_error_yet:
                    instantiation_errors += 1
                    no_inst_error_yet = False
                continue
            scheme_str = str(i.scheme)
            scheme2num_bbs[scheme_str] += 1
            schemes.add(scheme_str)

        if no_inst_error_yet:
            passes += 1
            required_schemes.append(schemes)

    return scheme2num_bbs, coder_errors, instantiation_errors, passes, required_schemes



def main():
    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-c', '--config', metavar="CONFIG", default=None,
            help='abstraction context configuration file in json format')

    argparser.add_argument('bhivecsv', metavar="CSV", help='path to a csv file with hex basic blocks in its first column')

    args = parse_args_with_logging(argparser, "info")

    actx_config = load_json_config(args.config)
    actx_config['predmanager'] = {'num_processes': None}

    actx = AbstractionContext(config=actx_config)
    iwho_ctx = actx.iwho_ctx

    bbs = []
    with open(args.bhivecsv, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            bbs.append(row[0])

    # bbs = bbs[:100]

    total = len(bbs)
    print(f'total: {total}')

    num_processes = multiprocessing.cpu_count()

    chunk_size = (total // num_processes) + 1

    proc_pool = Pool(num_processes)

    results = proc_pool.imap(partial(decode_batch, actx_config=actx_config), chunks(bbs, chunk_size))

    scheme2num_bbs = Counter()
    coder_errors = 0
    instantiation_errors = 0
    passes = 0
    required_schemes = []

    for res in results:
        scheme2num_bbs += res[0]
        coder_errors += res[1]
        instantiation_errors += res[2]
        passes += res[3]
        required_schemes += res[4]

    proc_pool.close()

    print(f"coder errors: {coder_errors}")
    print(f"instantiation errors: {instantiation_errors}")
    print(f"passes: {passes}")

    num_schemes = len(iwho_ctx.filtered_insn_schemes)

    available_schemes = set()
    not_yet_90 = True
    for idx, (scheme, n) in enumerate(scheme2num_bbs.most_common(), start=1):
        available_schemes.add(scheme)
        num_covered_so_far = 0
        for s in required_schemes:
            if s.issubset(available_schemes):
                num_covered_so_far += 1

        percentage_covered = 100 * num_covered_so_far / total
        if percentage_covered >= 99:
            print(f"99% of bbs covered with {idx} insn schemes ({100 * idx/ num_schemes:.1f}%)")
            break

        if percentage_covered >= 90 and not_yet_90:
            print(f"90% of bbs covered with {idx} insn schemes ({100 * idx/ num_schemes:.1f}%)")
            not_yet_90 = False

    num_schemes_not_covered = 0

    for scheme in iwho_ctx.filtered_insn_schemes:
        if scheme2num_bbs[str(scheme)] == 0:
            num_schemes_not_covered += 1

    print(f"total schemes: {num_schemes}")
    percentage = 100 * num_schemes_not_covered / num_schemes
    print(f"not covered by any passing bb: {num_schemes_not_covered} ({percentage:.1f}%)")



if __name__ == "__main__":
    main()

