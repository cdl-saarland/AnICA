"""TODO document"""

import json
import os
from pathlib import Path
import shutil
from statistics import geometric_mean

from .abstractblock import AbstractBlock
from .abstractioncontext import AbstractionContext
from .configurable import load_json_config, pretty_print
from .html_utils import prettify_absblock

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

def generate_table_entry(actx, base_dir, discovery):
    absblock, result_ref = load_absblock(base_dir / 'discoveries' / discovery, actx=actx)

    meas_series = actx.measurement_db.get_series(result_ref)

    ints = []
    for entry in meas_series['measurements']:
        eval_res = dict()
        for r in entry['predictor_runs']:
            eval_res[r['predictor']] = r['result']
        ints.append(actx.interestingness_metric.compute_interestingness(eval_res))

    mean_interestingness = geometric_mean(ints)

    res = dict()
    res['id'] = discovery
    res['pretty_str'] = prettify_absblock(absblock, skip_top=True)
    res['num_insns'] = len(absblock.abs_insns)
    res['coverage'] = 42
    res['mean_interestingness'] = mean_interestingness
    res['witness_length'] = 42
    res['witness_link'] = "foo"
    return res

def format_abstraction_config(abstraction_config):
    res = "<div class=\"code\">"
    res += pretty_print(abstraction_config, filter_doc=True)
    # TODO this could be imporoved with a proper structure and using the docs for mouseover hints
    res += "</div>"
    return res

def make_report(campaign_dir, out_dir):
    base_dir = Path(campaign_dir)
    out_dir = Path(out_dir)

    html_resources_path = Path(__file__).parent.parent / "html_resources" / "campaign_site"


    # make sure that the directory exists and is empty
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)

    shutil.copy(html_resources_path / "style.css", out_dir / "style.css")
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
    with open(html_resources_path / "frame.html", 'r') as f:
        html_frame = f.read()
    for k, v in replacements.items():
        html_frame = html_frame.replace(f'[[{k}]]', str(v), 1)

    with open(out_dir / 'index.html', 'w') as f:
        f.write(html_frame)

    table_data = []
    for fn in os.listdir(base_dir / 'discoveries')[:50]:
        table_data.append(generate_table_entry(actx, base_dir, fn))

    table_str = json.dumps(table_data, indent=2)

    with open(html_resources_path / "script.js", 'r') as f:
        js_frame = f.read()
    js_frame = js_frame.replace('[[table_data]]', table_str, 1)

    with open(out_dir / 'script.js', 'w') as f:
        f.write(js_frame)

