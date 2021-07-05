from copy import deepcopy
import json

from devidisc.abstractionconfig import AbstractionConfig

class WitnessTrace:
    class Witness:
        def __init__(self, component_token, expansion, taken: bool, terminate: bool, measurements):
            self.component_token = component_token
            self.expansion = expansion
            self.taken = taken
            self.terminate = terminate
            self.measurements = measurements

        def to_json_dict(self):
            # TODO that's wrong!
            return {k: repr(v) for k, v in vars(self).items()}

        @staticmethod
        def from_json_dict(json_dict):
            # TODO that's wrong!
            return WitnessTrace.Witness(**json_dict)

    def __init__(self, abs_block):
        self.start = deepcopy(abs_block)
        self.trace = []

    def __len__(self):
        return len(self.trace)

    def add_taken_expansion(self, component_token, expansion, measurements):
        witness = WitnessTrace.Witness(component_token=component_token,
                expansion=expansion,
                taken=True,
                terminate=False,
                measurements=measurements)
        self.trace.append(witness)

    def add_nontaken_expansion(self, component_token, expansion, measurements):
        witness = WitnessTrace.Witness(component_token=component_token,
                expansion=expansion,
                taken=False,
                terminate=False,
                measurements=measurements)
        self.trace.append(witness)

    def add_termination(self, measurements):
        witness = WitnessTrace.Witness(component_token=None,
                expansion=None,
                taken=False,
                terminate=True,
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
            res.apply_expansion(witness.component_token, witness.expansion)
            if validate:
                assert res.subsumes(check_tmp)
                check_tmp = None

        return res

    def __str__(self):
        return json.dumps(self.to_json_dict(), indent=2, separators=(',', ':'))

    def to_json_dict(self):
        res = dict()
        res['start'] = self.start.to_json_dict()
        trace = []
        for v in self.trace:
            trace.append(v.to_json_dict())
        res['trace'] = trace
        return res

    @staticmethod
    def from_json_dict(acfg, json_dict):
        start_bb = AbstractBlock.from_json_dict(acfg, json_dict['start'])
        res = WitnessTrace(start_bb)
        for v in json_dict['trace']:
            res.trace.append(WitnessTrace.Witness.from_json_dict(v))
        return res

    def to_dot(self):
        # TODO
        pass


