
from pathlib import Path
import textwrap
import os
import shutil

class HTMLGraph:
    class Block:
        def __init__(self, ident, text, link, kind):
            self.ident = ident
            self.text = text
            self.link = link
            self.kind = kind

    def __init__(self, title):
        self.title = title

        self.rows = []
        self.current_row = []

        self.next_ident = 0

        self.ident2block = dict()

        self.html_resources_path = Path(__file__).parent.parent / "html_resources"

    def new_row(self):
        self.rows.append(self.current_row)
        self.current_row = []

    def add_block(self, text, link, kind):
        ident = self.next_ident
        self.next_ident += 1

        block = HTMLGraph.Block(ident, text, link, kind)

        self.current_row.append(block)

        self.ident2block[ident] = block
        return ident

    def add_edge(self, src_ident, dst_ident):
        # TODO
        pass

    def generate(self, dest):
        dest_path = Path(dest)

        # make sure that the directory exists and is empty
        shutil.rmtree(dest_path, ignore_errors=True)
        os.makedirs(dest_path)

        # copy style and script file
        shutil.copy(self.html_resources_path / "style.css", dest_path)
        shutil.copy(self.html_resources_path / "script.js", dest_path)

        # compute the grid components
        grid_content = ""
        for row in self.rows:
            grid_content += textwrap.indent('<div class="gridsubcontainer">', 16*' ')
            for block in reversed(row):
                grid_content += textwrap.indent(f'<div id="{block.ident}" class="griditem block_{block.kind}" onclick="clickHandler(\'{block.ident}\', \'{block.link}\')">', 18*' ')
                grid_content += f'<div class="abstractbb">{block.text}</div>'
                grid_content += textwrap.indent('</div>', 18*' ')
            grid_content += textwrap.indent('</div>', 16*' ')

        # TODO arrows

        # load the html frame
        with open(self.html_resources_path / "frame.html", 'r') as f:
            frame = f.read()

        html_text = frame.format(title=self.title, grid_content=grid_content)

        with open(dest_path / "index.html", "w") as f:
            f.write(html_text)

