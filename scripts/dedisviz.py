#!/usr/bin/env python3

""" TODO document
"""

import argparse
import json
import os
import sys

import iwho
from iwho.utils import parse_args_with_logging

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.abstractionconfig import AbstractionConfig
from devidisc.discovery import WitnessTrace
from devidisc.html_graph import trace_to_html_graph
from devidisc.measurementdb import MeasurementDB



def main():
    default_db = "measurements.db"

    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-d', '--database', metavar='database', default=default_db,
            help='path to an sqlite3 measurement database that has been initialized via dedisdb.py -c, for storing measurements to')

    # TODO acfg config, ctx config
    # TODO mode of operation: dot, html, end result, ...
    argparser.add_argument('tracefile', metavar='TRACEFILE', help='path to a witness trace file in json format')

    args = parse_args_with_logging(argparser, "info")

    ctx = iwho.get_context('x86')

    with open(args.tracefile) as f:
        json_dict = json.load(f)

    bb_len = len(json_dict['start']['abs_insns'])
    acfg = AbstractionConfig(ctx, bb_len)

    tr = WitnessTrace.from_json_dict(acfg, acfg.resolve_json_references(json_dict))

    # g = tr.to_dot()
    #
    # g.render(view=True)

    with MeasurementDB(args.database) as mdb:
        g = trace_to_html_graph(tr, mdb)

        g.generate("./generated_html")


if __name__ == "__main__":
    main()
