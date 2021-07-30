#!/usr/bin/env python3

""" TODO document
"""

import argparse
import os
import sys

from iwho.utils import parse_args_with_logging

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from devidisc.html_report import make_report

def main():
    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-o', '--output', metavar='DIR', required=True, help='path to the destination directory')

    argparser.add_argument('campaigndir', metavar='DIR', help='path to a campaign result directory')

    args = parse_args_with_logging(argparser, "info")

    make_report(args.campaigndir, args.output)

if __name__ == "__main__":
    main()
