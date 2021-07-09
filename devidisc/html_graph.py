
from copy import deepcopy
import json
from multiprocessing import Pool
from pathlib import Path
import textwrap
import os
import shutil

from .witness import WitnessTrace

def prettify_absinsn(absinsn, hl_feature=None):
    if all(map(lambda x: (x[0] == 'present' and x[1].val == False) or x[1].is_bottom(), absinsn.features.items())):
        res = "not present"
        if hl_feature is not None:
            res = '<div class="highlightedcomponent">' + res + '</div>'
    elif all(map(lambda x: x[1].is_top(), absinsn.features.items())):
        res = "TOP"
        if hl_feature is not None:
            res = '<div class="highlightedcomponent">' + res + '</div>'
    else:
        list_entries = []
        for k, v in absinsn.features.items():
            entry = f"{k}: {v}"
            if hl_feature is not None and hl_feature[0] == k:
                entry = '<div class="highlightedcomponent">' + entry + "</div>"
            entry = "<li>" + entry + "</li>"
            list_entries.append(entry)
        res = "\n".join(list_entries)
        res = '<ul class="featurelist">' + res + "</ul>"
    return res

def prettify_absblock(absblock, hl_expansion=None):
    res = ""
    res += "<b>Abstract Instructions:</b>\n"
    res += "<table>\n"
    for idx, ai in enumerate(absblock.abs_insns):
        res += "<tr>"
        res += f"<th>{idx}</th>\n"
        hl_feature = None
        if hl_expansion is not None and hl_expansion[0] == 0 and hl_expansion[1] == idx:
            hl_feature = hl_expansion[2]
        insn_str = prettify_absinsn(ai, hl_feature)
        res += f"<td>{insn_str}</td>\n"
        res += "</tr>"

    res += "</table>\n"

    res += "<b>Abstract Aliasing:</b>"

    highlight_key = None
    if hl_expansion is not None and hl_expansion[0] == 1:
        highlight_key = absblock.acfg.resolve_json_references(hl_expansion[1])

    entries = []
    for ((iidx1, oidx1), (iidx2,oidx2)), absval in absblock._abs_aliasing.items():
        highlighted = highlight_key == ((iidx1, oidx1), (iidx2,oidx2))
        if absval.is_top():
            if highlighted:
                valtxt = "TOP"
            else:
                continue
        elif absval.is_bottom():
            valtxt = "BOTTOM"
        elif absval.val is False:
            valtxt = "must not alias"
        elif absval.val is True:
            valtxt = "must alias"
        else:
            assert False

        div = "", ""
        if highlighted:
            div = '<div class="highlightedcomponent">', "</div>"
        entries.append((f"<tr><td>{div[0]}{iidx1}:{oidx1} - {iidx2}:{oidx2}{div[1]}</td> <td>{div[0]} {valtxt} {div[1]} </td></tr>\n", f"{iidx1}:{oidx1} - {iidx2}:{oidx2}"))

    if len(entries) > 0:
        entries.sort(key=lambda x: x[1])
        res += "\n<table>"
        res += "\n" + "\n".join(map(lambda x: x[0], entries))
        res += "</table>"
    else:
        res += " TOP"

    return res

def trace_to_html_graph(witness: WitnessTrace, acfg=None, measurement_db=None):
    g = HTMLGraph("DeviDisc Visualization", acfg=acfg)

    abb = deepcopy(witness.start)

    parent = g.add_block(text=prettify_absblock(abb), link="empty_witness.html", kind="start")
    g.new_row()

    for witness in witness.trace:
        meas_id = witness.measurements
        if meas_id is not None and measurement_db is not None:
            measdict = measurement_db.get_series(meas_id)
            link = g.add_measurement_site(meas_id, measdict)
        else:
            link = "empty_witness.html"

        if witness.terminate:
            new_node = g.add_block(text="Terminated: " + witness.comment, link=link, kind="end")
            g.add_edge(parent, new_node)
            continue

        if witness.taken:
            abb.apply_expansion(witness.expansion)

            new_node = g.add_block(text=prettify_absblock(abb, witness.expansion), link=link, kind="interesting")
            g.add_edge(parent, new_node)

            parent = new_node
            g.new_row()
        else:
            tmp_abb = deepcopy(abb)
            tmp_abb.apply_expansion(witness.expansion)

            new_node = g.add_block(text=prettify_absblock(tmp_abb, witness.expansion), link=link, kind="notinteresting")
            g.add_edge(parent, new_node)
    g.new_row()

    return g


_measurement_frame = """
    <div class="measurement">
      <h3> Measurement #{meas_id} </h3>
      <table class="meastable">
        <tr> <th> assembly </th>
          <td>
            <div class="asmblock">{asmblock}</div>
          </td>
        </tr>
        <tr> <th> hex </th>
          <td>
            <div class="hexblock">{hexblock}</div>
          </td>
        </tr>
        {predictor_runs}
      </table>
    </div>
"""

_predictor_run_frame = """
        <tr>
          <th> {predictor} </th>
          <td> {result} </td>
        </tr>
"""

def _generate_measurement_site(acfg, frame_str, measdict):
    series_id = measdict.get("series_id", "N")
    series_date = measdict["series_date"]
    source_computer = measdict["source_computer"]

    measurement_texts = []

    num_interesting = 0
    num_measurements = len(measdict["measurements"])

    for m in measdict["measurements"]:
        meas_id = m.get("measurement_id", "N")
        hexblock = m["input"]
        asmblock = m["asm_str"]
        predictor_run_texts = []
        for r in m["predictor_runs"]:
            predictor_text = ", ".join(r["predictor"]) + ", " + r["uarch"]
            results = []
            if r["result"] is not None:
                results.append(r["result"])
            if r["remark"] is not None:
                remark = r["remark"]
                try:
                    json_dict = json.loads(remark)
                    if "error" in json_dict:
                        results.append("\n<div class='code'>" + json_dict["error"] + "</div>")
                except:
                    results.append(remark)
            result_text = ", ".join(map(str, results))
            predictor_run_texts.append(_predictor_run_frame.format(predictor=predictor_text, result=result_text))

        # compute interestingness to sort by it
        eval_res = {x: {"TP": r.get("result", None)} for x, r in enumerate(m["predictor_runs"])}
        interestingness = acfg.compute_interestingness(eval_res)
        if acfg.is_interesting(eval_res):
            num_interesting += 1

        full_predictor_run_text = "\n".join(predictor_run_texts)

        full_predictor_run_text = _predictor_run_frame.format(predictor="interestingness", result=f"{interestingness:.3f}") + full_predictor_run_text

        meas_text = _measurement_frame.format(meas_id=meas_id, asmblock=asmblock, hexblock=hexblock , predictor_runs=full_predictor_run_text)
        measurement_texts.append((interestingness, meas_text))

    measurement_texts.sort(key=lambda x: x[0], reverse=True)

    full_meas_text = "\n".join(map(lambda x: x[1], measurement_texts))

    interesting_percentage = (num_interesting / num_measurements) * 100

    comment_str = f"{num_interesting} out of {num_measurements} measurements ({interesting_percentage:.1f}%) are interesting."

    return frame_str.format(
            series_id=series_id,
            series_date=series_date,
            comment=comment_str,
            source_computer=source_computer,
            measurement_text=full_meas_text)

def _asm_decode_fun(task):
    return (task[0], task[1], "\n".join(task[3].hex2asm(task[2])))

def add_asm_to_measdicts(acfg, series_dicts):
    ctx = acfg.ctx
    coder = ctx.coder

    # this takes some time, but is trivially parallelizable
    tasks = []
    for series_idx, series_dict in enumerate(series_dicts):
        for meas_idx, meas_dict in enumerate(series_dict["measurements"]):
            tasks.append((series_idx, meas_idx, meas_dict["input"], coder))

    with Pool() as pool:
        results = pool.imap(_asm_decode_fun, tasks)

        for series_idx, meas_idx, asm_str in results:
            series_dicts[series_idx]["measurements"][meas_idx]["asm_str"] = asm_str


class HTMLGraph:
    class Block:
        def __init__(self, ident, text, link, kind):
            self.ident = ident
            self.text = text
            self.link = link
            self.kind = kind

    def __init__(self, title, acfg=None):
        self.title = title

        self.acfg = acfg

        self.rows = []
        self.current_row = []

        self.next_ident = 0

        self.ident2block = dict()

        self.edges = []

        self.html_resources_path = Path(__file__).parent.parent / "html_resources"

        self.measurement_sites = []

    def new_row(self):
        self.rows.append(self.current_row)
        self.current_row = []

    def add_block(self, text, link, kind):
        ident = "block_{}".format(self.next_ident)
        self.next_ident += 1

        block = HTMLGraph.Block(ident, text, link, kind)

        self.current_row.append(block)

        self.ident2block[ident] = block
        return ident

    def add_edge(self, src_ident, dst_ident):
        self.edges.append((src_ident, dst_ident))

    def add_measurement_site(self, meas_id, measdict):
        link = "measurements/series_{}.html".format(meas_id)
        self.measurement_sites.append((link, measdict))
        return link

    def generate(self, dest):
        dest_path = Path(dest)

        # make sure that the directory exists and is empty
        shutil.rmtree(dest_path, ignore_errors=True)
        os.makedirs(dest_path)

        if len(self.measurement_sites) > 0:
            add_asm_to_measdicts(self.acfg, [measdict for link, measdict in self.measurement_sites])

            meas_dir = dest_path / "measurements"
            os.makedirs(meas_dir)
            with open(self.html_resources_path / "meas_frame.html") as f:
                meas_frame_str = f.read()

            for link, measdict in self.measurement_sites:
                site_str = _generate_measurement_site(self.acfg, meas_frame_str, measdict)
                with open(dest_path / link, "w") as f:
                    f.write(site_str)

        # copy style file
        shutil.copy(self.html_resources_path / "style.css", dest_path)
        shutil.copy(self.html_resources_path / "meas_style.css", dest_path)
        shutil.copy(self.html_resources_path / "empty_witness.html", dest_path)

        # compute the grid components
        grid_content = ""
        for row in self.rows:
            grid_content += textwrap.indent('<div class="gridsubcontainer">\n', 16*' ')
            for block in reversed(row):
                link = 'null' if block.link is None else f"\'{block.link}\'"
                grid_content += textwrap.indent(f'<div id="{block.ident}" class="griditem block_{block.kind}" onclick="clickHandler(\'{block.ident}\', {link})">\n', 18*' ')
                grid_content += f'<div class="abstractbb">{block.text}</div>\n'
                grid_content += textwrap.indent('</div>\n', 18*' ')
            grid_content += textwrap.indent('</div>\n', 16*' ')

        # load the html frame
        with open(self.html_resources_path / "frame.html", 'r') as f:
            frame = f.read()

        html_text = frame.format(title=self.title, grid_content=grid_content)

        with open(dest_path / "index.html", "w") as f:
            f.write(html_text)

        # arrows go to the script file
        connectors = []
        for src, dst in self.edges:
            connectors.append(f'drawConnector("{src}", "{dst}")')
        connector_str = "\n".join(connectors)
        connector_str = textwrap.indent(connector_str, 4*' ')

        with open(self.html_resources_path / "script.js", 'r') as f:
            script_frame = f.read()

        script = script_frame.replace('[[ARROWS]]', connector_str, 1)

        with open(dest_path / "script.js", "w") as f:
            f.write(script)

