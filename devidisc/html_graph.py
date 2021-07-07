
from copy import deepcopy
from pathlib import Path
import textwrap
import os
import shutil

from .witness import WitnessTrace

def trace_to_html_graph(witness: WitnessTrace, acfg=None, measurement_db=None):
    g = HTMLGraph("DeviDisc Visualization", acfg=acfg)

    abb = deepcopy(witness.start)

    parent = g.add_block(text=str(abb), link="empty_witness.html", kind="start")
    g.new_row()

    for witness in witness.trace:
        meas_id = witness.measurements
        if meas_id is not None and measurement_db is not None:
            measdict = measurement_db.get_series(meas_id)
            link = g.add_measurement_site(meas_id, measdict)
        else:
            link = None

        if witness.terminate:
            new_node = g.add_block(text="Terminated: " + witness.comment, link="empty_witness.html", kind="end")
            g.add_edge(parent, new_node)
            continue

        if witness.taken:
            abb.apply_expansion(witness.component_token, witness.expansion)

            new_node = g.add_block(text=str(abb), link=link, kind="interesting")
            g.add_edge(parent, new_node)

            parent = new_node
            g.new_row()
        else:
            tmp_abb = deepcopy(abb)
            tmp_abb.apply_expansion(witness.component_token, witness.expansion)

            new_node = g.add_block(text=str(tmp_abb), link=link, kind="notinteresting")
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

    ctx = acfg.ctx

    for m in measdict["measurements"]:
        meas_id = m.get("measurement_id", "N")
        hexblock = m["input"]
        asmblock = "\n".join(map(str, ctx.decode_insns(hexblock)))
        predictor_run_texts = []
        for r in m["predictor_runs"]:
            predictor_text = ", ".join(r["predictor"]) + ", " + r["uarch"]
            results = []
            if r["result"] is not None:
                results.append(r["result"])
            if r["remark"] is not None:
                results.append(r["remark"])
            result_text = ", ".join(map(str, results))
            predictor_run_texts.append(_predictor_run_frame.format(predictor=predictor_text, result=result_text))

        # compute interestingness to sort by it
        eval_res = {x: {"TP": r.get("result", None)} for x, r in enumerate(m["predictor_runs"])}
        interestingness = acfg.compute_interestingness(eval_res)

        full_predictor_run_text = "\n".join(predictor_run_texts)
        meas_text = _measurement_frame.format(meas_id=meas_id, asmblock=asmblock, hexblock=hexblock , predictor_runs=full_predictor_run_text)
        measurement_texts.append((interestingness, meas_text))

    measurement_texts.sort(key=lambda x: x[0], reverse=True)

    full_meas_text = "\n".join(map(lambda x: x[1], measurement_texts))

    return frame_str.format(
            series_id=series_id,
            series_date=series_date,
            source_computer=source_computer,
            measurement_text=full_meas_text)

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

