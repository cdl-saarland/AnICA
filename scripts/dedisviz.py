#!/usr/bin/env python3

""" TODO document
"""

import argparse
import json
import os
import sys

from iwho.utils import parse_args_with_logging

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractioncontext import AbstractionContext
from devidisc.discovery import WitnessTrace
from devidisc.html_graph import trace_to_html_graph


def main():
    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # TODO mode of operation: dot, html, end result, ...
    argparser.add_argument('tracefile', metavar='TRACEFILE', help='path to a witness trace file in json format')

    args = parse_args_with_logging(argparser, "info")

    with open(args.tracefile) as f:
        json_dict = json.load(f)

    config_dict = json_dict['config']

    config_dict['predmanager'] = None # we don't need that one here

    actx = AbstractionContext(config=config_dict)

    trace_dict = actx.json_ref_manager.resolve_json_references(json_dict['trace'])
    tr = WitnessTrace.from_json_dict(actx, trace_dict)

    with actx.measurement_db as mdb:
        g = trace_to_html_graph(tr, actx=actx, measurement_db=mdb)

        g.generate("./generated_html")


if __name__ == "__main__":
    main()
