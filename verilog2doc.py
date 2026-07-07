import argparse
import glob
import os
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

import graphviz

theme = "blue"

# default theme: green
table_color = "#9bbb59"
row_colors = ["#d7e4bc", "#eaf1dd"]
th_font_color = "white"
td_font_color = "black"

if theme == "blue":
    table_color = "#4f81bd"
    row_colors = ["#b8cce4", "#dbe5f1"]
elif theme == "red":
    table_color = "#c0504d"
    row_colors = ["#e6b9b8", "#f2dddc"]
elif theme == "softgreen":
    table_color = "#80c2b4"
    row_colors = ["#e7f3f1", "#cfe8e2"]
elif theme == "navi":
    table_color = "#8c9b94"
    row_colors = ["#e9ebea", "#d1d7d3"]
elif theme == "ozean":
    table_color = "#505f80"
    row_colors = ["#dedee6", "#b8becc"]
elif theme == "pink":
    table_color = "#ebbdda"
    row_colors = ["#fbf2f7", "#f8e6f2"]


html_begin = """
<html>
  <header>
    <link rel='stylesheet' href='styles/default.min.css'>
    <script src='highlight.min.js'></script>
    <script src='languages/verilog.min.js'></script>
    <style>

        body {font-family: Arial;}

        /* Style the tab */
        .tab {
          overflow: hidden;
          border: 1px solid #ccc;
          background-color: #f1f1f1;
        }

        /* Style the buttons inside the tab */
        .tab button {
          background-color: inherit;
          float: left;
          border: none;
          outline: none;
          cursor: pointer;
          padding: 14px 16px;
          transition: 0.3s;
          font-size: 17px;
        }

        /* Change background color of buttons on hover */
        .tab button:hover {
          background-color: #ddd;
        }

        /* Create an active/current tablink class */
        .tab button.active {
          background-color: #ccc;
        }

        /* Style the tab content */
        .tabcontent {
          //display: none;
          padding: 6px 12px;
          border: 1px solid #ccc;
          border-top: none;
        }

        table {{
            border: 1px solid white;
            border-collapse: collapse;
            background: {table_color};
        }}
        th {{
            border: 1px solid white;
            border-collapse: collapse;
            padding: 5px;
            color: {th_font_color};
        }}
        td {{
            border: 1px solid white;
            border-collapse: collapse;
            padding: 5px;
            color: {td_font_color};
        }}
    </style>
  </header>
  <body>
"""

html_end = """
  </body>
  <script>hljs.highlightAll();</script>
  <!---
  <script>
    function openSection(evt, sectionName) {
      var i, tabcontent, tablinks;
      tabcontent = document.getElementsByClassName("tabcontent");
      for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
      }
      tablinks = document.getElementsByClassName("tablinks");
      for (i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
      }
      document.getElementById(sectionName).style.display = "block";
      evt.currentTarget.className += " active";
    }
    openSection(event, 'CONFIG');
  </script>
  ---!>
</html>
"""


def dependsGraph2menuNew(modules, dependsGraph, prefix=""):
    result = ""
    for module in dependsGraph:
        filename = modules[module]["filename"]
        basename = filename.split("/")[-1]
        # result += f"{prefix}<a target='main' href='{basename}.html#{module}'>{module}</a><br/>\n"
        # result += f"<button class=\"tablinks\" onclick=\"openSection(event, '{basename}_{module}')\">{module}</button>"
        result += f'<button class="tablinks" onclick="window.location = \'{basename}.html#{module}\';">{module}</button>'
        result += dependsGraph2menuNew(modules, dependsGraph[module], prefix + "")
    return result


def html_row(color, port, title):
    return f'<tr><td bgcolor="{color}" port="{port}"><font color="{td_font_color}">{title}</font></td></tr>'


def html_node(title, rows1, rows2=None):
    if not rows2:
        rows2 = []
    return f'<<table bgcolor="{table_color}" border="0" cellborder="0" cellspacing="1" style="rounded"><tr><td><font color="{th_font_color}">{title}</font></td></tr>{"".join(rows1)}<tr><td><FONT POINT-SIZE="1"> </FONT></td></tr>{"".join(rows2)}<tr><td><FONT POINT-SIZE="4"> </FONT></td></tr></table>>'


def vparser(filepath):
    patternComment = re.compile(r"\s*(?P<comment>\/\*(\*(?!\/)|[^*])*\*\/)")
    patternComment2 = re.compile(r"\s*(?P<comment>\/\/.*\n)")
    patternModule = re.compile(r"\s*((?P<attribs>\([^\)]*\))?)\s*module\s+(?P<name>\w+)(?P<params>\s*#\([^\)]*\))?\s*\((?P<args>[^;]*)\s*(?P<inline>[\s\S]*?(?=endmodule))endmodule")
    patternArg = re.compile(r"\s*((?P<attr>\(\*(\*(?!\))|[^*])*\*\))*)\s*((?P<comment>\/\/.*)*)((?P<comment2>\/\*(\*(?!\/)|[^*])*\*\/)*)\s*(?P<dir>output|input|inout)(?P<type>\s+wire|\s+reg)?(?P<signed>\s*signed)?(?P<size>\s\[[^\]]*\])?(?P<name>\s\w+)\s*((?P<default>=\s*\w+)?)\s*((?P<comment3>\/\/.*)*)((?P<comment4>\/\*(\*(?!\/)|[^*])*\*\/)*)")
    patternParam = re.compile(r"(?P<name>\w*)\s*=\s*((?P<default>{[^}]*})?)((?P<default2>\w)?),*")
    patternSub = re.compile(r"^(?P<module>\w*) +((?P<params>#\(.*\) +)?)(?P<instance>\w*) (?P<args>\([^;]*)$")
    patternSubParam = re.compile(r"((?P<name>\.\w+)\s*\((?P<value>[^\)]*)\)|(?P<value2>\w+)),*\s*((?P<comment>\/\/.*)?)")

    data = open(filepath, "r").read()

    modules = {}
    comments = []
    last_block = ""
    for char in data:
        last_block += char
        if matches := patternComment.match(last_block):
            comments.append(last_block.strip().lstrip("/*").rstrip("*/").strip())
            last_block = ""
        elif matches := patternComment2.match(last_block):
            comments.append(last_block.strip().lstrip("/").strip())
            last_block = ""
        elif last_block.endswith("endmodule"):
            cleaned = re.sub(r"^`.*", "", last_block.strip())
            cleaned = re.sub(r"\(.*\)\s+module ", "module ", cleaned.strip())
            if cleaned.strip().startswith("module "):
                matches = patternModule.match(cleaned)
                module_name = matches["name"].strip()
                args = matches["args"]
                params = matches["params"]
                msource = matches["inline"]
                mattribs = matches["attribs"]
                if mattribs:
                    mattribs = mattribs.lstrip("(*").rstrip("*)").strip()

                mdata = {
                    "basename": os.path.basename(filepath),
                    "filepath": filepath,
                    "data": data,
                    "module_name": module_name,
                    "comments": comments,
                    "attribs": mattribs,
                    "args": [],
                    "params": [],
                    "sub": {},
                }
                modules[module_name] = mdata

                if args:
                    for anum, arg in enumerate(patternArg.finditer(args.strip())):
                        if mdata["args"]:
                            if arg["comment"]:
                                mdata["args"][-1]["comments"].append(arg["comment"])
                            if arg["comment2"]:
                                mdata["args"][-1]["comments"].append(arg["comment2"])
                        mdata["args"].append(
                            {
                                "num": anum,
                                "name": arg["name"].strip(),
                                "dir": arg["dir"],
                                "signed": arg["signed"],
                                "size": arg["size"],
                                "type": arg["type"] or "wire",
                                "default": None,
                                "comments": [],
                            }
                        )
                        if arg["default"]:
                            mdata["args"][-1]["default"] = arg["default"].split("=", 1)[1]
                        if arg["comment3"]:
                            mdata["args"][-1]["comments"].append(arg["comment3"])
                        if arg["comment4"]:
                            mdata["args"][-1]["comments"].append(arg["comment4"])

                pnum = 0
                if params:
                    for rpart in params.strip().split("parameter"):
                        part = rpart.strip().rstrip(")").strip()
                        comment = ""
                        if "//" in part:
                            comment = part.split("//", 1)[1].strip()
                        if "/*" in part:
                            comment = part.split("/*", 1)[1].strip().rstrip("*/").strip()
                        if matches := patternParam.match(part):
                            mdata["params"].append(
                                {
                                    "num": pnum,
                                    "name": matches["name"].strip(),
                                    "default": None,
                                    "comments": [comment],
                                }
                            )
                            if matches["default"]:
                                mdata["params"][-1]["default"] = matches["default"]
                            elif matches["default2"]:
                                mdata["params"][-1]["default"] = matches["default2"]
                            pnum += 1

                # for sub in re.split(r'\n', msource):
                for rsub in re.split(r"\send\s|;|\n", msource):
                    sub = rsub.strip()
                    if sub.startswith("parameter "):
                        match = patternParam.match(sub[10:])
                        if match:
                            mdata["params"].append(
                                {
                                    "num": pnum,
                                    "name": match["name"].strip(),
                                    "default": None,
                                    "comments": [],
                                }
                            )
                            if match["default"]:
                                mdata["params"][-1]["default"] = match["default"]
                            elif match["default2"]:
                                mdata["params"][-1]["default"] = match["default2"]
                            pnum += 1

                for rsub in re.split(r"\send\s|;", msource):
                    # remove comments
                    sub = re.sub(r"\s*(?P<comment>\/\*(\*(?!\/)|[^*])*\*\/)", "", rsub.strip())
                    sub = re.sub(r"\s*(?P<comment>\/\/.*\n)", "", sub)

                    subres = patternSub.search(sub.strip().replace("\n", " "))
                    if subres:
                        module_name = subres["module"]
                        instance_name = subres["instance"]
                        if module_name in {"begin", "else", "end", "if", "generate", "endcase", "restrict"}:
                            continue

                        mdata["sub"][instance_name] = {
                            "instance_name": instance_name,
                            "module_name": module_name,
                            "params": [],
                            "args": [],
                        }
                        sub_params = subres["params"] or ""

                        for pnum, part in enumerate(patternSubParam.finditer(sub_params)):
                            if part["value"]:
                                pname = part["name"].strip().lstrip(".")
                                mdata["sub"][instance_name]["params"].append({"num": pnum, "name": pname, "value": part["value"]})
                            elif part["value2"]:
                                mdata["sub"][instance_name]["params"].append({"num": pnum, "value": part["value2"]})

                        sub_args = subres["args"] or ""
                        for anum, rpart in enumerate(sub_args.strip().lstrip("(").rstrip(")").split(",")):
                            part = rpart.strip()
                            if part and part[0] == ".":
                                pname = part.split("(")[0][1:].strip().lstrip(".")
                                value = part.split("(")[1].rstrip(")").strip()
                                mdata["sub"][instance_name]["args"].append({"num": anum, "name": pname, "value": value})
                            else:
                                mdata["sub"][instance_name]["args"].append({"num": anum, "value": part})

                last_block = ""
                comments = []
    if last_block.strip():
        print("--------------")
        print(last_block.strip())
        print("--------------")

    return modules


def verilog2doc(args):
    verilogs = args.verilog
    top = args.top
    output = args.output
    netlist = args.netlist
    inline = args.inline
    pin_file = args.pins
    linter = args.linter
    fpga_type = ""

    if len(args.verilog) == 1 and args.verilog[0].endswith(".gprj"):
        print(f"reading files from gowin project: {os.path.basename(args.verilog[0])}")
        verilogs = []
        gprjdir = os.path.dirname(args.verilog[0])
        tree = ET.parse(args.verilog[0])
        root = tree.getroot()

        device = root.find("Device")
        if device is not None:
            fpga_type = device.get("pn", device.text)

        for fileentry in root.findall("FileList/File"):
            if fileentry.get("enable", "1") != "1":
                continue
            if fileentry.get("type") == "file.verilog":
                verilogs.append(os.path.join(gprjdir, fileentry.get("path")))
            elif fileentry.get("type") == "file.cst" and not pin_file:
                pin_file = os.path.join(gprjdir, fileentry.get("path"))

    elif len(args.verilog) == 1 and args.verilog[0].endswith(".prj"):
        print(f"reading files from ise prj: {os.path.basename(args.verilog[0])}")
        verilogs = []
        prjdir = os.path.dirname(args.verilog[0])
        data = open(args.verilog[0], "r").read()
        for line in data.split("\n"):
            if line.startswith("verilog work "):
                verilogs.append(os.path.join(prjdir, line.split('"')[1]))

    elif len(args.verilog) == 1 and args.verilog[0].endswith(".xst"):
        print(f"reading files from xst: {os.path.basename(args.verilog[0])}")
        verilogs = []
        prjdir = os.path.dirname(args.verilog[0])
        xstdata = open(args.verilog[0], "r").read()
        for line in xstdata.split("\n"):
            if line.startswith("-p "):
                fpga_type = line.split()[-1]
            elif line.startswith("-ifn "):
                prjfile = os.path.join(prjdir, line.split()[-1])
                data = open(prjfile, "r").read()
                for vline in data.split("\n"):
                    if vline.startswith("verilog work "):
                        verilogs.append(os.path.join(prjdir, vline.split('"')[1]))

    vmodules = {}
    globals_v = ""
    for verilog_file in verilogs:
        if os.path.basename(verilog_file) == "globals.v":
            globals_v = verilog_file

    for verilog_file in verilogs:
        if verilog_file == globals_v:
            continue
        vmodules.update(vparser(verilog_file))

    if top not in vmodules:
        if "rio" in vmodules:
            top = "rio"
            print(f"FALLBACK: setting top module to '{top}'")
        elif "top" in vmodules:
            top = "top"
            print(f"FALLBACK: setting top module to '{top}'")
        else:
            print(f"ERROR: top '{top}' module not found")
            print(f"Modules: {', '.join(vmodules.keys())}")
            if not vmodules:
                exit(1)
            print(f"FALLBACK: setting top module to '{list(vmodules)[0]}'")
            top = list(vmodules)[0]

    if output is None:
        if "/" in vmodules[top]["filepath"]:
            output = "/".join(vmodules[top]["filepath"].split("/")[0:-1]) + "/Documentation"
        else:
            output = "./Documentation"
        print(f"setting output directory to {output}")
        os.makedirs(output, exist_ok=True)

    # read pins
    pinmapping = {}
    for suffix in ("cst", "pcf", "lpf", "ucf"):
        if not pin_file:
            for filepath in glob.glob(os.path.join(os.path.dirname(vmodules[top]["filepath"]), f"*.{suffix}")):
                pin_file = filepath
                break

    if pin_file:
        print(f"using pin-file: {pin_file}")
        pin_type = pin_file.split(".")[-1]
        if pin_type == "cst":
            for line in open(pin_file, "r").read().split("\n"):
                if line.startswith("IO_LOC "):
                    realpin = line.strip(";").split()[-1]
                    pin_name = line.strip(";").split()[1].strip('"')
                    pinmapping[pin_name] = {
                        "pin": realpin,
                    }
        elif pin_type == "pcf":
            for line in open(pin_file, "r").read().split("\n"):
                if line.startswith("set_io "):
                    realpin = line.split()[-1]
                    pin_name = line.split()[-2]
                    pinmapping[pin_name] = {
                        "pin": realpin,
                    }
        elif pin_type in {"qsf", "qdf"}:
            for line in open(pin_file, "r").read().split("\n"):
                if line.startswith("set_location_assignment "):
                    print(line.split())
                    realpin = line.split()[-1]
                    pin_name = line.split()[1]
                    pinmapping[pin_name] = {
                        "pin": realpin,
                    }
        elif pin_type == "lpf":
            for line in open(pin_file, "r").read().split("\n"):
                if line.startswith("LOCATE COMP "):
                    realpin = line.split()[-1].strip('";')
                    pin_name = line.split()[-3].strip('";')
                    pinmapping[pin_name] = {
                        "pin": realpin,
                    }
        elif pin_type == "ucf":
            patternUCF = re.compile(r"NET\s+\"(?P<name>[^\"]+)\".*LOC\s*=\s*\"(?P<pin>[^\"]+)\"")
            for line in open(pin_file, "r").read().split("\n"):
                if line.startswith("NET "):
                    netline = patternUCF.search(line)
                    if netline:
                        realpin = netline["pin"]
                        pin_name = netline["name"]
                        pinmapping[pin_name] = {
                            "pin": realpin,
                        }
        else:
            print("unsupported pin format:", pin_file)

    list_pins = []
    for pinname, pindata in pinmapping.items():
        color = row_colors[len(list_pins) % 2]
        list_pins.append(f'<tr><td bgcolor="{color}"><font color="{td_font_color}">{pinname}</font></td><td bgcolor="{color}" port="{pinname}"><font color="{td_font_color}">{pindata["pin"]}</font></td></tr>')

    gPins = graphviz.Digraph("G", format="svg")
    gPins.attr(rankdir="LR")
    gPins.node(
        "Pins",
        shape="none",
        label=f'<<table bgcolor="{table_color}" border="0" cellborder="0" cellspacing="1" style="rounded"><tr><td><font color="{th_font_color}">PINS</font></td></tr>{"".join(list_pins)}<tr><td><FONT POINT-SIZE="4"> </FONT></td></tr></table>>',
        fontsize="11pt",
        tooltip="Pins",
        href="Pins.html",
    )

    def menu(mtree, mlist, module):
        mlist.append(module)
        if module not in mtree:
            mtree[module] = {}
        for instance_name, instance_data in vmodules.get(module, {}).get("sub", {}).items():
            menu(mtree[module], mlist, instance_data["module_name"])

    def menudraw(fd, mtree, prefix=""):
        for module in mtree:
            fd.write(f"{prefix}<a target='main' href=\"module_{module}.html\">{module}</a><br/>\n")
            menudraw(fd, mtree[module], f"{prefix}&nbsp;&nbsp;&nbsp;")

    # build menu-tree
    mtree = {}
    mlist = []
    menu(mtree, mlist, top)
    # print(json.dumps(mtree, indent=2))

    fd = open(f"{output}/Menu.html", "w")
    fd.write("<html>")
    fd.write("<a target='main' href='Main.html'>Overview</a><br/>\n")
    fd.write("<a target='main' href='Pins.html'>Pins</a><br/>\n")
    fd.write("<br/>\n")
    fd.write("Modules:<br/>\n")

    menudraw(fd, mtree)
    fd.write("<br/>")

    # find missing modules
    for module in vmodules:
        if module not in mlist:
            fd.write(f"<a target='main' href=\"module_{module}.html\">{module}</a><br/>\n")

    fd.write("<br/>")
    if linter:
        fd.write("<a target='main' href='linter.html'>Linter-Output</a><br/>\n")
    fd.write("<br/>")
    fd.write("</html>")
    fd.close()

    dotsvgs = {}
    if netlist:
        for verilog_file in verilogs:
            verilog_basename = os.path.basename(verilog_file)
            if verilog_basename == "globals.v":
                continue
            pre_options = ""
            post_options = ""
            if globals_v:
                pre_options += f' -p "read_verilog -sv -formal {globals_v}"'
            post_options += ' -p "opt; fsm; opt; memory; opt"'
            if not os.path.exists(f"{output}/{verilog_basename}.dot"):
                os.system(f'yosys {pre_options} -p "read_verilog -sv -formal {globals_v}" -p "read_verilog -sv -formal {verilog_file}" -p "proc" {post_options} -p "show -prefix {output}/{verilog_basename} -notitle -colors 2 -width -format dot" >/dev/null')
            if not os.path.exists(f"{output}/{verilog_basename}.svg"):
                os.system(f"dot -Tsvg -o {output}/{verilog_basename}.svg {output}/{verilog_basename}.dot")
            dotsvgs[verilog_file] = f"{output}/{verilog_basename}.svg"

    zip_obj = zipfile.ZipFile("highlight.zip", "r")
    zip_obj.extractall(output)
    zip_obj.close()

    def svg_img(graph, name):
        open(f"{output}/{name}.dot", "w").write(str(graph))
        svgdata = graph.pipe().decode()
        svgdata = re.sub('width="[0-9pt]+"', 'width="100%"', svgdata)
        svgdata = re.sub('height="[0-9pt]+"', 'height="100%"', svgdata)
        # svgdata = re.sub('height="[0-9pt]+"', 'height="800px"', svgdata)
        open(f"{output}/{name}.svg", "w").write(svgdata)
        if inline:
            fd.write(f'<a target="_blank" href="{name}.svg">[ZOOM]</a>')
            fd.write(svgdata)
        else:
            fd.write(f'<a target="_blank" href="{name}.svg">')
            fd.write(f'<img width="100%" src="{name}.svg" />')
            fd.write("</a>")

    fileerrors = {}
    if linter:
        verilator = ["verilator", "--lint-only", "-Wno-WIDTHEXPAND", *verilogs]
        result = subprocess.run(verilator, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.stderr:
            outputs = []
            for line in result.stderr.decode().split("\n"):
                if "no search path specified with" in line:
                    continue
                if line and line[0] == "%":
                    # msgtype = line.split()[0]
                    filename = ":".join(line.split()[1].split(":")[:-3])
                    if filename not in fileerrors:
                        fileerrors[filename] = []
                    outputs = fileerrors[filename]
                    outputs.append("")
                    outputs.append("")
                    outputs.append(line)
                else:
                    outputs.append(line)

        fd = open(f"{output}/linter.html", "w")
        fd.write("<html>")
        fd.write(html_begin)
        fd.write("\n")

        fd.write("<h3>Linter-Output</h3>\n")
        for filename, errors in fileerrors.items():
            if filename:
                # fd.write(f'filename: <a href="module_{os.path.basename(filename)}.html">{filename}</a><br/>')
                fd.write(f"filename: {filename}<br/>")
            fd.write("<pre><code>")
            for error in errors:
                fd.write(error.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
                fd.write("\n")
            fd.write("</code></pre>")
        fd.write(html_end)
        fd.close()

    def link_modules(graph, module, name_from, name_to):
        for param in module["params"]:
            pname = param.get("name") or param.get("value")
            graph.edge(
                f"{name_from}:{pname}",
                f"{name_to}:{pname}",
                dir="none",
                fontsize="11pt",
            )
        for arg in module["args"]:
            graph.edge(
                f"{name_from}:{arg.get('name')}",
                f"{name_to}:{arg.get('name')}",
                dir="none",
                fontsize="11pt",
            )

    def node_module(graph, module, name=None, title=None, link=None, group=None):
        if name is None:
            name = module["module_name"]
        if title is None:
            title = module["module_name"]
        if link is None:
            link = module["module_name"]
        if group is None:
            group = ""
        list_params = []
        if params := module["params"]:
            rn = 0
            for param in params:
                color = row_colors[rn % 2]
                pname = param.get("name") or param.get("value")
                list_params.append(html_row(color, pname, f"{param.get('name')}={param.get('default')}"))
                rn += 1
        list_args = []
        if args := module["args"]:
            rn = 0
            for arg in args:
                color = row_colors[rn % 2]
                list_args.append(html_row(color, arg.get("name"), arg.get("name")))
                rn += 1
        graph.node(
            name,
            shape="none",
            label=html_node(title, list_params, list_args),
            fontsize="11pt",
            tooltip=f"module: {module['module_name']}",
            href=f"module_{link}.html",
            group=group,
        )

    # generate module pages and graphs
    gAll = graphviz.Digraph("G", format="svg")
    gAll.attr(rankdir="LR")
    gAll.node(
        "Pins",
        shape="none",
        label=f'<<table bgcolor="{table_color}" border="0" cellborder="0" cellspacing="1" style="rounded"><tr><td><font color="{th_font_color}">Pins</font></td></tr>{"".join(list_pins)}<tr><td><FONT POINT-SIZE="4"> </FONT></td></tr></table>>',
        fontsize="11pt",
        tooltip="Pins",
        href="Pins.html",
    )
    for pinname in pinmapping:
        gAll.edge(
            f"Pins:{pinname}",
            f"{top}:{pinname}",
            dir="none",
            fontsize="11pt",
        )

    gAllClusterN = 0
    for _name, module in vmodules.items():
        filepath = module["filepath"]
        basename = module["basename"]
        module_name = module["module_name"]
        # module graph
        gModule = graphviz.Digraph("G", format="svg")
        gModule.attr(rankdir="LR")
        with gModule.subgraph(name="cluster_0") as c:
            c.attr(style="filled,rounded", color="#CDCDCD")
            c.attr(label=module["module_name"])
            c.attr(margin="10")
            node_module(c, module, group="g1")

            # pins for the top module
            if module_name == top:
                gModule.node(
                    "Pins",
                    shape="none",
                    label=f'<<table bgcolor="{table_color}" border="0" cellborder="0" cellspacing="1" style="rounded"><tr><td><font color="{th_font_color}">Pins</font></td></tr>{"".join(list_pins)}<tr><td><FONT POINT-SIZE="4"> </FONT></td></tr></table>>',
                    fontsize="11pt",
                    tooltip="Pins",
                    href="Pins.html",
                )
                for pinname in pinmapping:
                    gModule.edge(
                        f"Pins:{pinname}",
                        f"{module_name}:{pinname}",
                        dir="none",
                        fontsize="11pt",
                    )

            # source modules
            for source_name, source_module in vmodules.items():
                for sinstance_name, sinstance in source_module["sub"].items():
                    if sinstance["module_name"] == module["module_name"]:
                        node_module(gModule, sinstance, sinstance_name, sinstance_name, source_name)
                        link_modules(gModule, sinstance, sinstance_name, module["module_name"])
            # sub modules
            if subs := module["sub"]:
                snum = 0
                for instance_name, instance in subs.items():
                    submodule_name = instance["module_name"]
                    submodule = vmodules[submodule_name]
                    group = ""
                    if snum == 0:
                        group = "g1"
                    node_module(c, instance, name=instance_name, group=group)
                    # invisable link for better layout inside cluster
                    c.edge(
                        module["module_name"],
                        instance_name,
                        dir="none",
                        style="invis",
                        fontsize="11pt",
                    )
                    node_module(gModule, submodule)
                    link_modules(gModule, instance, instance_name, submodule_name)
                    snum += 1

        # complete graph
        with gAll.subgraph(name=f"cluster_{gAllClusterN}") as c:
            gAllClusterN += 1
            c.attr(style="filled,rounded", color="#CDCDCD")
            c.attr(label=module["module_name"])
            c.attr(margin="10")
            node_module(c, module, group="g1")
            # sub modules
            if subs := module["sub"]:
                snum = 0
                for instance_name, instance in subs.items():
                    submodule_name = instance["module_name"]
                    submodule = vmodules[submodule_name]
                    group = ""
                    if snum == 0:
                        group = "g1"
                    node_module(c, instance, name=instance_name, group=group)
                    # invisable link for better layout inside cluster
                    c.edge(
                        module["module_name"],
                        instance_name,
                        dir="none",
                        style="invis",
                        fontsize="11pt",
                    )
                    link_modules(gAll, instance, instance_name, submodule_name)
                    snum += 1

        # module page
        fd = open(f"{output}/module_{module['module_name']}.html", "w")
        fd.write(html_begin)
        fd.write(f"<h1>{module['module_name']} ({basename})</h1>\n")
        fd.write("<table width=100%><tr><td width=40% valign=top>\n")
        if comments := module["comments"]:
            for comment in comments:
                fd.write("<pre>")
                fd.write(comment)
                fd.write("</pre>")
            fd.write("<hr/>\n")
        if params := module["params"]:
            fd.write("<h3>Module-Parameter</h3>\n")
            fd.write("<table width=90%>\n")
            fd.write(f'<tr bgcolor="{table_color}"><th>name</th><th>default</th><th>comment</th></tr>\n')
            rn = 0
            for param in params:
                color = row_colors[rn % 2]
                fd.write(f'<tr bgcolor="{color}"><td>{param.get("name") or ""}</td><td>{param.get("default") or ""}</td><td>{param.get("comments") or ""}</td></tr>\n')
                rn += 1
            fd.write("</table>\n")
            fd.write("<br>\n")
        if args := module["args"]:
            fd.write("<h3>Module-Ports</h3>\n")
            fd.write("<table width=90%>\n")
            fd.write(f'<tr bgcolor="{table_color}"><th>direction</th><th>type</th><th>name</th><th>size</th><th>default</th><th>comment</th></tr>\n')
            rn = 0
            for arg in args:
                color = row_colors[rn % 2]
                fd.write(f'<tr bgcolor="{color}"><td>{arg.get("dir") or ""}</td><td>{arg.get("signed") or ""} {arg.get("type") or ""}</td><td>{arg.get("name") or ""}</td><td>{arg.get("size") or ""}</td><td>{arg.get("default") or ""}</td><td>{arg.get("comments") or ""}</td></tr>\n')
                rn += 1
            fd.write("</table>\n")
            fd.write("<br>\n")
        if subs := module["sub"]:
            fd.write("<h3>Sub-Modules</h3>\n")
            fd.write("<table width=90%>\n")
            fd.write(f'<tr bgcolor="{table_color}"><th>Instance</th><th>Module</th><th>comment</th></tr>\n')
            rn = 0
            for subname, sub in subs.items():
                color = row_colors[rn % 2]
                fd.write(f'<tr bgcolor="{color}"><td>{subname}</td><td>{sub.get("module_name") or ""}</td><td>{sub.get("comments") or ""}</td></tr>\n')
                rn += 1
            fd.write("</table>\n")
            fd.write("<br>\n")
        fd.write("</td><td valign=top>\n")
        svg_img(gModule, f"module_{module['module_name']}")
        fd.write("</td></tr></table><br/>\n")

        if module["filepath"] in fileerrors:
            fd.write("<b>Linter-Output:</b><br/>\n")
            fd.write("<pre><code>")
            for line in fileerrors[module["filepath"]]:
                fd.write(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
                fd.write("\n")
            fd.write("</code></pre>")
            fd.write("<br/>\n")

        # module source
        fd.write("<b>Source:</b><br/>\n")
        fd.write("<pre><code class='language-verilog'>")
        fd.write(module["data"])
        fd.write("</code></pre>")
        fd.write("<hr/>\n")
        fd.write(html_end)
        fd.close()

    fd = open(f"{output}/Pins.html", "w")
    fd.write("<html>")
    fd.write(html_begin)
    fd.write("\n")
    svg_img(gPins, "Pins")
    fd.write("<br>\n")
    fd.write("\n")

    if fpga_type:
        fd.write("<h3>FPGA</h3>\n")
        fd.write(f"Type: {fpga_type}<br/>\n")
        fd.write("<br/>\n")

    fd.write("<table>\n")
    fd.write(f'<tr bgcolor="{table_color}"><th>Name</th><th>Pin</th></tr>\n')
    rn = 0
    for pinname, pindata in pinmapping.items():
        color = row_colors[rn % 2]
        fd.write(f'<tr bgcolor="{color}"><td>{pinname}</td><td>{pindata["pin"]}</td></tr>\n')
        rn += 1
    fd.write("</table>\n")
    fd.write("<br>\n")

    fd.write("<br>\n")
    fd.write(html_end)
    fd.close()

    fd = open(f"{output}/Main.html", "w")
    fd.write("<html>")
    fd.write(html_begin)
    fd.write("<center><table width=70% height=70%><tr><td>")
    svg_img(gAll, "main")
    fd.write("</td></tr></table></center>")
    fd.write("\n")
    fd.write("<br>\n")
    fd.write(html_end)
    fd.close()

    fd = open(f"{output}/index.html", "w")
    fd.write("<html>")
    fd.write('  <frameset cols="200, *">')
    fd.write('    <frame src="Menu.html" name="menu">')
    fd.write('    <frame src="Main.html" name="main">')
    fd.write("  </frameset>")
    fd.write("</html>")
    fd.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("verilog", type=str, nargs="+")
    parser.add_argument("--output", "-o", help="output directory", type=str, default=None)
    parser.add_argument("--top", "-t", help="top module", type=str, default="top")
    parser.add_argument("--netlist", "-n", help="gen netlist graphs (yosys dot)", type=int, default=0)
    parser.add_argument("--inline", "-i", help="inline svg", type=int, default=1)
    parser.add_argument("--pins", "-p", help="pins file (cst/pcf/lpf)", type=str, default="")
    parser.add_argument("--linter", "-l", help="add verilator linter output", type=int, default=0)
    sargs = parser.parse_args()

    verilog2doc(sargs)
