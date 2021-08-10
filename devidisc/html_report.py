"""TODO document"""

from collections import defaultdict
import json
import os
from pathlib import Path
import shutil
from statistics import geometric_mean

from .abstractblock import AbstractBlock
from .abstractioncontext import AbstractionContext
from .configurable import load_json_config, pretty_print
from .html_utils import prettify_absblock, make_link
from . import html_graph as hg
from .witness import WitnessTrace

def load_absblock(abfile, actx=None):
    with open(abfile) as f:
        json_dict = json.load(f)

    if actx is None:
        config_dict = json_dict['config']
        config_dict['predmanager'] = None # we don't need that one here
        actx = AbstractionContext(config=config_dict)

    result_ref = json_dict['result_ref']

    ab_dict = actx.json_ref_manager.resolve_json_references(json_dict['ab'])

    ab = AbstractBlock.from_json_dict(actx, ab_dict)
    return ab, result_ref

def load_witness(trfile, actx=None):
    with open(trfile) as f:
        json_dict = json.load(f)

    if actx is None:
        config_dict = json_dict['config']
        config_dict['predmanager'] = None # we don't need that one here
        actx = AbstractionContext(config=config_dict)

    tr_dict = actx.json_ref_manager.resolve_json_references(json_dict['trace'])

    tr = WitnessTrace.from_json_dict(actx, tr_dict)
    return tr


def format_abstraction_config(abstraction_config):
    res = "<div class='absconfig'>\n"

    res += "<ul class='absconfig_ul'>\n"

    for k, v in abstraction_config.items():
        if k in ('measurement_db', 'predmanager'):
            continue
        res += "  <li class='absconfig_li'>"
        res += f"{k}:\n"
        res += "    <ul class='absconfig_ul_inner'>\n"
        for ki, vi in v.items():
            if ki.endswith(".doc"):
                continue
            doc = v.get(f'{ki}.doc', None)
            res += "      <li class='absconfig_li_inner'>"
            entry_str = f"{ki}: {json.dumps(vi)}"

            if doc is not None:
                entry_str = "<div class='tooltip'>" + entry_str + "<span class='tooltiptext'>" + doc + "</span></div>"

            res += entry_str
            res += "</li>\n"
        res += "    </ul>\n"
        res += "  </li>\n"

    res += "</ul>\n"

    # res += pretty_print(abstraction_config, filter_doc=True)
    # TODO this could be improved with a proper structure and using the docs for mouseover hints
    res += "</div>\n"
    return res

def make_report(campaign_dir, out_dir):
    reporter = HTMLReporter(campaign_dir, out_dir)
    reporter.make_report()


class HTMLReporter:
    def __init__(self, campaign_dir, out_dir):
        self.base_dir = Path(campaign_dir)
        self.out_dir = Path(out_dir)
        self.html_resources_path = Path(__file__).parent.parent / "html_resources" / "campaign_site"

    def make_report(self):
        base_dir = self.base_dir
        out_dir = self.out_dir

        # make sure that the directory exists and is empty
        shutil.rmtree(out_dir, ignore_errors=True)
        os.makedirs(out_dir)

        os.makedirs(out_dir / "witness_traces")

        shutil.copy(self.html_resources_path / "style.css", out_dir / "style.css")
        shutil.copy(base_dir / "log.txt", out_dir / "log.txt")

        campaign_config = load_json_config(base_dir / "campaign_config.json")

        replacements = dict()

        abstraction_config = campaign_config["abstraction_config"]
        replacements['abstraction_config'] = format_abstraction_config(abstraction_config)

        abstraction_config['predmanager'] = None # we don't need that one here
        actx = AbstractionContext(config=abstraction_config)

        # TODO this could be improved
        replacements['tools'] = ", ".join(campaign_config['predictors'])
        replacements['termination'] = json.dumps(campaign_config['termination'])


        # report data
        report = load_json_config(base_dir / "report.json")

        replacements["num_discovery_batches"] = report["num_batches"]
        replacements["num_total_sampled"] = report["num_total_sampled"]
        replacements["num_discoveries"] = report["num_discoveries"]
        replacements["total_time"] = report["seconds_passed"] # TODO this could be improved

        # load the html frame and fill it
        with open(self.html_resources_path / "frame.html", 'r') as f:
            html_frame = f.read()
        for k, v in replacements.items():
            html_frame = html_frame.replace(f'[[{k}]]', str(v), 1)

        with open(out_dir / 'index.html', 'w') as f:
            f.write(html_frame)

        table_data = []
        for fn in os.listdir(base_dir / 'discoveries'):
            table_data.append(self._generate_table_entry(actx, fn))

        table_str = json.dumps(table_data, indent=2)

        with open(self.html_resources_path / "script.js", 'r') as f:
            js_frame = f.read()
        js_frame = js_frame.replace('[[table_data]]', table_str, 1)

        with open(out_dir / 'script.js', 'w') as f:
            f.write(js_frame)

        self._generate_per_scheme_view(actx)

        print("Only witness sites remain")
        for fn in os.listdir(base_dir / 'discoveries'):
            self._generate_trace_site(actx, fn)


    def _generate_per_scheme_view(self, actx):
        all_discoveries = []

        for fn in os.listdir(self.base_dir / 'discoveries'):
            absblock, result_ref = load_absblock(self.base_dir / 'discoveries' / fn, actx=actx)
            all_discoveries.append(absblock)

        per_scheme = defaultdict(list)

        for ab in all_discoveries:
            for ai in ab.abs_insns:
                for ci in actx.insn_feature_manager.compute_feasible_schemes(ai.features):
                    per_scheme[ci].append(ab)

        table_data = []
        for k, vs in per_scheme.items():
            table_data.append({'scheme': str(k), 'num_discoveries': len(vs)})

        table_str = json.dumps(table_data, indent=2)

        per_scheme_path = self.html_resources_path.parent / "per_scheme_site"
        shutil.copy(per_scheme_path / "style.css", self.out_dir / "per_insnscheme_style.css")
        shutil.copy(per_scheme_path / "frame.html", self.out_dir / "per_insnscheme.html")

        with open(per_scheme_path / "script.js", 'r') as f:
            js_frame = f.read()
        js_frame = js_frame.replace('[[table_data]]', table_str, 1)

        with open(self.out_dir / 'per_insnscheme_script.js', 'w') as f:
            f.write(js_frame)

    def _generate_table_entry(self, actx, discovery):
        base_dir = self.base_dir
        out_dir = self.out_dir

        discovery, ext = os.path.splitext(discovery)
        assert ext == '.json'

        absblock, result_ref = load_absblock(base_dir / 'discoveries' / f'{discovery}.json', actx=actx)

        with actx.measurement_db as mdb:
            meas_series = mdb.get_series(result_ref)

        ints = []
        for entry in meas_series['measurements']:
            eval_res = dict()
            for r in entry['predictor_runs']:
                eval_res[r['predictor']] = {'TP': r['result']}
            ints.append(actx.interestingness_metric.compute_interestingness(eval_res))

        mean_interestingness = geometric_mean(ints)

        witness_link = f"./witness_traces/{discovery}/index.html"

        res = dict()
        res['id'] = discovery
        res['pretty_str'] = prettify_absblock(absblock, skip_top=True)
        res['num_insns'] = len(absblock.abs_insns)
        res['coverage'] = 42 # TODO
        res['mean_interestingness'] = f"{mean_interestingness:.3f}"
        res['witness_length'] = 42
        # res['witness_length'] = len(witness)
        res['witness_link'] = make_link(url=witness_link, caption="link", is_relative=True)
        return res

    def _generate_trace_site(self, actx, discovery):
        base_dir = self.base_dir
        out_dir = self.out_dir

        discovery, ext = os.path.splitext(discovery)
        assert ext == '.json'

        witness = load_witness(base_dir / 'witnesses' / f'{discovery}.json', actx=actx)
        with actx.measurement_db as mdb:
            # g = hg.trace_to_html_graph(witness, actx=actx, measurement_db=mdb) # TODO
            g = hg.trace_to_html_graph(witness, actx=actx, measurement_db=None)
            g.generate(out_dir / "witness_traces" / f"{discovery}")

