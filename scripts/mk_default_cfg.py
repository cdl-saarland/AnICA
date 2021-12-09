#!/usr/bin/env python3

""" TODO document
"""

import argparse
import json
import os
import sys

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)


from anica.abstractioncontext import AbstractionContext
from iwho.configurable import pretty_print

def main():
    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-f', '--filter-doc', action='store_true', help='do not emit documentation entries')

    argparser.add_argument('-o', '--outfile', metavar='FILENAME', help='path where the config in json format should be saved')

    args = argparser.parse_args()

    default_cfg = AbstractionContext.get_default_config()
    if args.outfile is not None:
        with open(args.outfile, 'w') as f:
            print(pretty_print(default_cfg, filter_doc=args.filter_doc), file=f)
    else:
        print(pretty_print(default_cfg, filter_doc=args.filter_doc))

if __name__ == "__main__":
    main()
