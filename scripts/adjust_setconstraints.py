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

    argparser.add_argument('--featurefile', metavar="NAME", required=True,
        help='a feature file of the old scheme description, or any json file with a dict using all old-style insn schemes as keys')

    argparser.add_argument('-o', '--output', metavar="OUTFILE", default="replace.sh",
        help='the output file')

    # argparser.add_argument('input', metavar="INFILE",
    #     help='the input file')

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

    with open(args.featurefile) as f:
        indict = json.load(f)

    relevant_strings = set()
    for cs in all_set_constraints:
        relevant_strings.update(cs)

    pat = re.compile(r":(\S*)(\s|$)")

    translations = set()

    for key in indict.keys():
        if not any(map(lambda x: x in key, relevant_strings)):
            continue
        matches = pat.findall(key)
        if len(matches) == 0:
            print(f"no matches for {key}")
            continue
        for m in matches:
            old_str = m[0]
            if old_str.endswith(","):
                old_str = old_str[:-1]
            old_set = tuple(sorted(old_str.split(",")))
            if len(old_set) == 1:
                continue
            if old_set in all_set_constraints:
                translations.add((":" + old_str, ":" + ",".join(old_set)))

    for fr, to in translations:
        print(f"{fr} -> {to}")

    print(f"found {len(translations)} translations")

    outfile = args.output
    with open(outfile, "w") as f:
        print("#!/usr/bin/env bash\n", file=f)
        for fr, to in translations:
            print(f'sed -i "s/{fr}/{to}/g" $*', file=f)

    st = os.stat(outfile)
    os.chmod(outfile, st.st_mode | stat.S_IEXEC)

    return 0

if __name__ == "__main__":
    sys.exit(main())
