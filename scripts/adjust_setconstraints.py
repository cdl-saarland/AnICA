#!/usr/bin/env python3

""" A small script to replace old-style (non-deterministic) set constraints
in InsnSchemes with sorted ones.
"""

import argparse
import json
import re
import os
import stat
import sys

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)

from iwho.configurable import load_json_config
import iwho

def main():
    argparser = argparse.ArgumentParser(description=__doc__)

    argparser.add_argument('-c', '--config', metavar="CONFIG", default=None,
            help='abstraction context configuration file in json format')

    argparser.add_argument('-o', '--output', metavar="OUTFILE", default="replace.sh",
        help='the output file')

    argparser.add_argument('-d', '--dryrun', action="store_true",
        help='if provided, do not overwrite the files, only list translations')

    argparser.add_argument('infiles', metavar="NAME", nargs="+",
        help='files that contain old-style insn schemes as keys')

    args = argparser.parse_args()

    # get an iwho context
    config = load_json_config(args.config)
    if 'iwho' in config:
        config = config['iwho']
    iwho_cfg = iwho.Config(config)
    ctx = iwho_cfg.context

    all_set_constraints = set()

    for ischeme in ctx.insn_schemes:
        for k, opscheme in ischeme.explicit_operands.items():
            if opscheme.is_fixed():
                continue
            constraint = opscheme.operand_constraint
            if not isinstance(constraint, iwho.SetConstraint):
                continue
            if constraint.name is not None:
                continue
            cs = tuple(sorted(map(str, constraint.acceptable_operands)))
            all_set_constraints.add(cs)

    for cs in all_set_constraints:
        print(cs)

    print(f"found {len(all_set_constraints)} relevant set constraints")


    relevant_strings = set()
    for cs in all_set_constraints:
        relevant_strings.update(cs)
    pat = re.compile(r":([^\s\"]*)(\s|$|\")")

    for infile in args.infiles:
        print(f"processing {infile}")
        with open(infile) as f:
            lines = f.readlines()

        translations = set()

        result_lines = []
        for l in lines:
            if not any(map(lambda x: x in l, relevant_strings)):
                result_lines.append(l)
                continue

            matches = pat.findall(l)
            if len(matches) == 0:
                print(f"  no matches for {l.strip()}")
                result_lines.append(l)
                continue
            replaced = False
            original = l
            for m in matches:
                old_str = m[0]
                if old_str.endswith(","):
                    old_str = old_str[:-1]
                sorted_set = tuple(sorted(old_str.split(",")))
                if len(sorted_set) == 1:
                    continue
                if sorted_set in all_set_constraints:
                    from_str = ":" + old_str
                    to_str = ":" + ",".join(sorted_set)
                    translations.add((from_str, to_str))
                    l = l.replace(from_str, to_str, 1)
                    replaced = True
            result_lines.append(l)
            if replaced:
                print(f"  transformed line:\n    from: {original.strip()}\n    to:   {l.strip()}")

        print(f"  applied {len(translations)} distinct translations:")
        for fr, to in translations:
            print(f"    {fr} -> {to}")

        if not args.dryrun:
            with open(infile, "w") as f:
                for l in result_lines:
                    f.write(l)

    return 0

if __name__ == "__main__":
    sys.exit(main())
