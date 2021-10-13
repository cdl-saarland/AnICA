from copy import deepcopy
import json
from typing import Optional

from graphviz import Digraph

from .abstractblock import AbstractBlock
from .configurable import store_json_config

class WitnessTrace:
    class Witness:
        def __init__(self, expansion, taken: bool, terminate: bool, comment: Optional[str], measurements):
            self.expansion = expansion
            self.taken = taken
            self.terminate = terminate
            self.comment = comment
            self.measurements = measurements

        def to_json_dict(self):
            return {k: v for k, v in vars(self).items()}

        @staticmethod
        def from_json_dict(json_dict):
            return WitnessTrace.Witness(**json_dict)

    def __init__(self, abs_block):
        # TODO this should probably contain the config as well
        self.start = deepcopy(abs_block)
        self.trace = []

    def __len__(self):
        return len(self.trace)

    def add_taken_expansion(self, expansion, measurements):
        witness = WitnessTrace.Witness(
                expansion=expansion,
                taken=True,
                terminate=False,
                comment=None,
                measurements=measurements)
        self.trace.append(witness)

    def add_nontaken_expansion(self, expansion, measurements):
        witness = WitnessTrace.Witness(
                expansion=expansion,
                taken=False,
                terminate=False,
                comment=None,
                measurements=measurements)
        self.trace.append(witness)

    def add_termination(self, comment, measurements):
        witness = WitnessTrace.Witness(
                expansion=None,
                taken=False,
                terminate=True,
                comment=comment,
                measurements=measurements)
        self.trace.append(witness)

    def replay(self, index=None, validate=False):
        if index is None:
            trace = self.trace
        else:
            trace = self.trace[:index]

        res = deepcopy(self.start)
        for witness in trace:
            if witness.terminate:
                break
            if not witness.taken:
                continue
            if validate:
                check_tmp = deepcopy(res)
            res.apply_expansion(witness.expansion)
            if validate:
                assert res.subsumes(check_tmp)
                check_tmp = None

        return res

    def __str__(self):
        actx = self.start.actx
        json_dict = actx.json_ref_manager.introduce_json_references(self.to_json_dict())
        return json.dumps(json_dict, indent=2, separators=(',', ':'))

    def to_json_dict(self):
        res = dict()
        res['start'] = self.start.to_json_dict()
        trace = []
        for v in self.trace:
            trace.append(v.to_json_dict())
        res['trace'] = trace
        return res

    @staticmethod
    def from_json_dict(actx, json_dict):
        start = AbstractBlock.from_json_dict(actx, json_dict['start'])
        res = WitnessTrace(start)
        for v in json_dict['trace']:
            res.trace.append(WitnessTrace.Witness.from_json_dict(v))
        return res

    def dump_json(self, filename):
        actx = self.start.actx
        out_data = dict()
        out_data['config'] = actx.get_config()
        out_data['trace'] = actx.json_ref_manager.introduce_json_references(self.to_json_dict())
        store_json_config(out_data, filename)

    def to_dot(self):
        g = Digraph()

        running_id = 0
        node_fmt = "n_{}"

        def new_node():
            nonlocal running_id
            running_id += 1
            return node_fmt.format(running_id)

        def abb_node(g, node_id, abb, color, comment=None):
            label = ""
            if comment is not None:
                label += comment
                label += '\n'
            label += str(abb)
            g.node(node_id,
                    label=label.replace('\n', r'\l'),
                    shape='rectangle',
                    fontname='Monospace',
                    color=color)

        abb = deepcopy(self.start)

        parent = new_node()
        abb_node(g, parent, abb, color="blue")

        for witness in self.trace:
            next_node = new_node()
            if witness.terminate:
                g.node(next_node, label="Terminated: " + witness.comment, color='blue')
                g.edge(parent, next_node)
                continue

            if witness.taken:
                abb.apply_expansion(witness.expansion)

                abb_node(g, next_node, abb, color="#07c400", comment="Interesting (cf. exp series #{})".format(witness.measurements))
                g.edge(parent, next_node)
                parent = next_node
            else:
                tmp_abb = deepcopy(abb)
                tmp_abb.apply_expansion(witness.expansion)
                abb_node(g, next_node, tmp_abb, color="#f00000", comment="Not Interesting (cf. exp series #{})".format(witness.measurements))
                g.edge(parent, next_node)

        return g


