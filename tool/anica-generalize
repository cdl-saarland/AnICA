#!/usr/bin/env python3

"""AnICA: Analyzing Inconsistencies of Code Analyzers
"""

import argparse
import json
import multiprocessing
from pathlib import Path
import random
import os
import sys
import textwrap

from datetime import datetime

import iwho
from iwho.configurable import load_json_config
from iwho.predictors import Predictor
from iwho.utils import parse_args_with_logging


import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from anica.abstractioncontext import AbstractionContext
from anica.abstractblock import AbstractBlock
import anica.discovery as discovery


import logging
logger = logging.getLogger(__name__)

try:
    import readline
except ImportError:
    logger.warning('Readline is not available!')


commands = [
        (('expand', 'e', 'ex'), "apply an expansion"),
        (('finish',), "finish with random expansions"),
        (('exit', 'quit'), "end here"),
        # (('expansions', 'es'), "show the possible expansions"),
        # (('undo', 'u'), "undo the last expansion"),
        # (('store', 's'), "store the current trace to disk"),
        # (('load', 'l'), "apply the operations from a trace on disk"),
    ]

def command_index(key):
    for idx, (ks, ht) in enumerate(commands):
        if key in ks:
            return ks[0]
    return None

def print_help():
    print("Usage:")
    for ks, ht in commands:
        print("  {} :  {}".format(",".join(ks), ht))

def colorize(s, col):
    if col == 'green':
        return "\u001b[32m" + s + "\u001b[0m"
    elif col == 'blue':
        return "\u001b[34m" + s + "\u001b[0m"
    assert False

def print_expansions(expansions):
    for idx, (exp, benefit) in enumerate(expansions):
        print("  ({}): {} (benefit: {})".format(colorize(str(idx), 'blue'), exp, benefit))


finish_interactive = False

class EndInteractive(Exception):
    def __init__(self, message, ab):
        super().__init__(message)
        self.ab = ab

def interact(ab, expansions):
    # TODO this is hacked and should be improved!
    global finish_interactive
    if finish_interactive:
        return random.choice(expansions)

    while True:
        print(colorize("\nCurrent abstract block:", 'green'))
        print(textwrap.indent(str(ab), '  '))

        print(colorize("\nAvailable expansions:", 'green'))
        print_expansions(expansions)

        print(colorize("\nChoose an expansion:", 'green'))
        cmd = input("> ")

        tokens = cmd.split()

        if len(tokens) == 0:
            continue

        key = tokens[0]
        cmd_idx = command_index(key)
        if cmd_idx == 'expand':
            if len(tokens) != 2:
                print("invalid number of arguments for 'expand', expected 1")
                continue
            try:
                exp_idx = int(tokens[1])
            except ValueError:
                print("invalid argument for 'expand', expected a number")
                continue
            if exp_idx < 0 or exp_idx >= len(expansions):
                print("invalid argument for 'expand', expected the index of an expansion.")
                continue
            return expansions[exp_idx]
        elif cmd_idx == "finish":
            finish_interactive = True
            return random.choice(expansions)
        elif cmd_idx == "exit":
            raise EndInteractive("Terminated because of user command", ab=ab)
        # elif cmd_idx == 'expansions':
        #     print_expansions(expansions)
        # elif cmd_idx == 'undo':
        #     pass
        # elif cmd_idx == 'store':
        #     pass
        # elif cmd_idx == 'load':
        #     pass
        else:
            try:
                exp_idx = int(tokens[0])
            except ValueError:
                print_help()
                continue
            if exp_idx < 0 or exp_idx >= len(expansions):
                print("invalid expansion index: out of range")
                continue
            return expansions[exp_idx]



def main():
    HERE = Path(__file__).parent

    default_seed = 424242

    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-c', '--config', metavar="CONFIG", default=None,
            help='abstraction context configuration file in json format')

    argparser.add_argument('-s', '--seed', type=int, default=default_seed, metavar="N",
            help='seed for the rng')

    argparser.add_argument('--no-minimize', action='store_true', help='do not minimize the basic block before generalization')

    argparser.add_argument('-i', '--interactive', action='store_true', help='interactively choose the expansion order')

    argparser.add_argument('--trace-output', metavar='trace file', default=None, help='path to a file where the generalization trace should be saved to')

    argparser.add_argument('--json-output', metavar='gen file', default=None, help='path to a file where the generalized abstract basic block should be dumped to')

    argparser.add_argument('generalize', metavar='asm file', help='path to a file containing the assembly of a basic block to generalize')

    argparser.add_argument('predictors', nargs="+", metavar="PREDICTOR_ID", help='one or more identifiers of predictors specified in the config')

    args = parse_args_with_logging(argparser, "info")

    random.seed(args.seed)

    actx_config = load_json_config(args.config)

    actx = AbstractionContext(config=actx_config)
    actx.predmanager.set_predictors(args.predictors)

    iwho_ctx = actx.iwho_ctx

    with open(args.generalize, 'r') as f:
        asm_str = f.read()
    bb = iwho.BasicBlock(iwho_ctx, iwho_ctx.parse_asm(asm_str))

    if not args.no_minimize:
        min_bb = discovery.minimize(actx, bb)
        print("Pruned {} instructions in the minimization step:".format(len(bb) - len(min_bb)))
        print(textwrap.indent(min_bb.get_asm(), '  '))
        bb = min_bb

    abb = AbstractBlock(actx, bb)
    if args.interactive:
        strategy = "interactive"
        interact_fun = interact
    else:
        strategy = actx.discovery_cfg.generalization_strategy[0][0]
        interact_fun = None
    try:
        res_abb, trace, result_ref = discovery.generalize(actx, abb, strategy=strategy, interact=interact_fun)
        print("Generalization Result:\n" + textwrap.indent(str(res_abb), '  '))
    except EndInteractive as e:
        print("generalization terminated early")
        res_abb = e.ab
        trace = None


    if args.json_output is not None:
        filename = args.json_output
        res_abb.dump_json(filename)
        print(f"generalization result written to: {filename}")

    if args.trace_output is not None and trace is not None:
        filename = args.trace_output
        trace.dump_json(filename)
        print(f"witness trace written to: {filename}")

    sys.exit(0)


if __name__ == "__main__":
    main()
