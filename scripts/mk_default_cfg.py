#!/usr/bin/env python3

""" TODO document
"""

import argparse
import json
import os
import sys

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)


from devidisc.abstractioncontext import AbstractionContext

def main():
    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('resultfile', metavar='FILENAME', help='path where the config in json format should be saved')

    args = argparser.parse_args()

    with open(args.resultfile, 'w') as f:
        default_cfg = AbstractionContext.get_default_config()
        json.dump(default_cfg, f, indent=2)

if __name__ == "__main__":
    main()
