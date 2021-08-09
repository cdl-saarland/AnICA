#!/usr/bin/env python3

""" TODO document
"""

import argparse
from collections import defaultdict
import os
import random
import sys

from graphviz import Graph

import_path = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(import_path)


from devidisc.abstractioncontext import AbstractionContext
from devidisc.configurable import load_json_config

def get_entry(features, key):
    if features is None or len(features) == 0:
        return None
    else:
        return features[0].get(key, None)

class FancyDefaultDict(dict):
    def __init__(self, fun):
        super().__init__()
        self.fun = fun

    def __missing__(self, key):
        res = self[key] = self.fun(key)
        return res


def get_color():
    res = '#'
    for x in range(6):
        res += hex(random.randrange(0, 16))[2]
    return res

def main():
    argparser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    argparser.add_argument('-c', '--config', default=None, metavar="CONFIG",
            help='campaign configuration file in json format')

    args = argparser.parse_args()

    config = load_json_config(args.config)

    actx = AbstractionContext(config=config)

    iwho_ctx = actx.iwho_ctx


    data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0)))

    for ischeme in iwho_ctx.filtered_insn_schemes:
        features = iwho_ctx.get_features(ischeme)
        category_entry = get_entry(features, 'category')
        extension_entry = get_entry(features, 'extension')
        isa_set_entry = get_entry(features, 'isa-set')
        data[category_entry][extension_entry][isa_set_entry] += 1


    g = Graph()

    nodes = FancyDefaultDict(lambda k: g.node(k))

    edges = defaultdict(lambda: 0)

    for category_entry, v1 in data.items():
        category_node = f'category_{category_entry}'
        nodes[category_node]
        for extension_entry, v2 in v1.items():
            extension_node = f'extension_{extension_entry}'
            nodes[extension_node]
            for isa_set_entry, n in v2.items():
                isa_set_node = f'isa-set_{isa_set_entry}'
                nodes[isa_set_node]

                # edges[(category_node, extension_node)] += 1
                # edges[(extension_node, isa_set_node)] += 1
                # edges[(isa_set_node, category_node)] += 1

                color = get_color()
                g.edge(category_node, extension_node, label=str(n), color=color)
                g.edge(extension_node, isa_set_node, label=str(n), color=color)
                g.edge(isa_set_node, category_node, label=str(n), color=color)

    # for (k1, k2), v in edges.items():
    #     g.edge(k1, k2, label=str(v))

    g.render('features.pdf', view=True)


if __name__ == "__main__":
    main()
