import argparse
import glob
import os
import re
import zipfile

import graphviz

theme = "softgreen"

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
  <!---
  </body>
  ---!>
  <script>hljs.highlightAll();</script>
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


def html_menu(modules, dependsGraph):
    result = '<div class="tab">'
    result += dependsGraph2menuNew(modules, dependsGraph, "")
    result += "</div>"

    return result


def verilog2doc(args):
    verilogs = args.verilog
    top = args.top
    output = args.output
    netlist = args.netlist
    inline = args.inline
    pin_file = args.pins
    patternModule = re.compile(r"module\s+(?P<name>\w+)(?P<params>\s*#\([^\)]*\))?\s*\((?P<args>[^\)]*)\)\s*;(?P<data>[\s\S]*?(?=endmodule))endmodule")
    patternParams = re.compile(r"(?P<parameter>parameter(\s+)(\w+)(\s*=\s*([0-9]+|{([^}]*)})?)?)")
    patternParam = re.compile(r"parameter(?P<type>\s+[a-zA-Z]+)?(?P<size>\s*\[.*\])?(?P<name>\s+\w+)\s*(?P<default>=.*)")
    patternArg = re.compile(r"(?P<dir>output|input|inout)?(?P<type>\s+wire|\s+reg)?(?P<signed>\s*signed)?(?P<size>\s\[[^\]]*\])?(?P<name>\s\w+)")
    patternSub = re.compile(r"(?P<module>\w+)\s+(?P<parameter>#\((\s*)((\.\w+(\(([^\)]*)\)(\s*)(,*)(\s*)?)?)+)\))\s+(?P<instance>\w+)\s+(?P<ports>\((\s*)((\.\w+(\s*\(([^\)]*)\)(\s*)(,*)(\s*)?)?)+)\))")
    patternSub2 = re.compile(r"(?P<module>\w+)\s+(#\(([^\)]*)\)\s*)?(?P<instance>\w+)\s*\(")
    patternInstanceName = re.compile(r"(?P<instance>\s\w+)\(")

    modules = {}
    globals_v = ""
    for verilog_file in verilogs:
        if os.path.basename(verilog_file) == "globals.v":
            globals_v = verilog_file

    for verilog_file in verilogs:
        verilog_basename = os.path.basename(verilog_file)
        if verilog_basename == "globals.v":
            continue

        verilogData = open(verilog_file, "r").read()
        verilogDataOrg = verilogData
        verilogData = re.sub(r"//.*", "", verilogData)
        verilogData = re.sub(r"/\*.*\*/", "", verilogData)
        for result in patternModule.finditer(verilogData):
            moduleName = result.group("name")
            moduleData = result.group("data")
            modules[moduleName] = {
                "filename": verilog_file,
                "args": {},
                "params": {},
                "data": moduleData,
                "filedata": verilogData,
                "sub": [],
            }

            defines = []
            moduleArgLast = {}

            args = []
            for arg in result.group("args").split("\n"):
                if arg.startswith("`"):
                    args.append(f"{arg},")
                else:
                    args.append(arg)

            for larg in " ".join(args).split(","):
                moduleArg = {}
                if not larg:
                    continue

                arg = re.sub(r"\s+", " ", larg.strip())

                # try to find comment
                if larg.strip():
                    for line in verilogDataOrg.split("\n"):
                        if "//" in line and larg.strip() in line:
                            moduleArg["comment"] = line.split("//")[-1].strip()

                if arg.startswith("`"):
                    if arg.startswith(("`ifndef", "`ifdef")):
                        defines.append(arg)
                    elif arg.startswith("`endif"):
                        defines.pop()
                else:
                    moduleArg["defines"] = defines.copy()
                    argm = patternArg.search(arg)
                    if argm:
                        if argm["dir"]:
                            moduleArg["direction"] = argm["dir"].strip()
                        if argm["type"]:
                            moduleArg["type"] = argm["type"].strip()
                        if argm["signed"]:
                            moduleArg["signed"] = argm["signed"].strip()
                        if argm["size"]:
                            moduleArg["size"] = argm["size"].strip()
                        if argm["name"]:
                            moduleArg["name"] = argm["name"].strip()
                        modules[moduleName]["args"][moduleArg["name"]] = moduleArg
                        moduleArgLast = moduleArg
                    elif len(arg.strip().split()) == 1:
                        moduleArg = moduleArgLast.copy()
                        moduleArg["name"] = arg.strip()
                        modules[moduleName]["args"][moduleArg["name"]] = moduleArg
                    else:
                        print(f"UNKNOWN ARG ({moduleName}): {arg.strip()} <br/>")

            if result.group("params"):
                pstring = result.group("params").replace("\n", " ").strip().lstrip("#(").rstrip(")").strip()
                params = patternParams.findall(pstring)
                if params:
                    for param in params:
                        mparam = patternParam.search(param[0])
                        if mparam:
                            moduleParam = {}
                            moduleParam["name"] = mparam["name"].strip()
                            if mparam["type"]:
                                moduleParam["size"] = mparam["type"].strip().replace(" ", "")
                            if mparam["size"]:
                                moduleParam["size"] = mparam["size"].strip().replace(" ", "")
                            if mparam["default"]:
                                moduleParam["default"] = mparam["default"].strip().lstrip("=").strip().replace(" ", "").replace("_", "")

                            modules[moduleName]["params"][moduleParam["name"]] = moduleParam
                        else:
                            print(f"UNKNOWN PARAMETER ({moduleName}): {arg.strip()} <br/>")

            for pattern in (patternSub, patternSub2):
                sres = pattern.finditer(result.group("data"))
                if sres:
                    for sub in sres:
                        subres = pattern.search(sub[0].replace("\n", " ").strip())
                        if subres:
                            module_name = subres["module"]
                            instance_name = subres["instance"]
                            if module_name in {"begin", "else", "end", "if", "generate", "endcase", "restrict"}:
                                continue
                            modules[moduleName]["sub"].append([module_name, sub[0]])

    if top not in modules:
        if "rio" in modules:
            top = "rio"
            print(f"FALLBACK: setting top module to '{top}'")
        elif "top" in modules:
            top = "top"
            print(f"FALLBACK: setting top module to '{top}'")
        else:
            print(f"ERROR: top '{top}' module not found")
            print(f"Modules: {', '.join(modules.keys())}")
            exit(1)

    if output is None:
        if "/" in modules[top]["filename"]:
            output = "/".join(modules[top]["filename"].split("/")[0:-1]) + "/Documentation"
        else:
            output = "./Documentation"

        print(f"setting output directory to {output}")
        os.makedirs(output, exist_ok=True)

    def mexpand(dependsGraph, module):
        dependsGraph[module] = {}
        for sub in modules[module]["sub"]:
            if sub[0] in modules:
                mexpand(dependsGraph[module], sub[0])
        return dependsGraph

    def dependsGraph2menu(fd, dependsGraph, prefix=""):
        for module in dependsGraph:
            filename = modules[module]["filename"]
            fd.write(f"{prefix}<a target='main' href='{filename.split('/')[-1]}.html#{module}'>{module}</a><br/>\n")
            dependsGraph2menu(fd, dependsGraph[module], prefix + "|&nbsp;")

    dependsGraph = mexpand({}, top)
    fd = open(f"{output}/menu.html", "w")
    fd.write("<html>")
    fd.write("<a target='main' href='main.html'>Overview</a><br/>\n")
    fd.write("<a target='main' href='pins.html'>Pins</a><br/>\n")
    fd.write("<br/>\n")
    fd.write("Modules:<br/>\n")
    dependsGraph2menu(fd, dependsGraph, "|&nbsp;")
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

    zip_obj = zipfile.ZipFile("/tmp/documentation/highlight.zip", "r")
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

    def add_edge(edges, port_from, port_to, direction="forward", style=None):
        edges[f"{port_from}--{port_to}"] = {
            "from": port_from,
            "to": port_to,
            "dir": direction,
            "style": style,
        }
        edges_all[f"{port_from}--{port_to}"] = {
            "from": port_from,
            "to": port_to,
            "dir": direction,
            "style": style,
        }

    def instance_get(sub):
        instance_name = f"{sub[0]}?"
        portmapping = {}
        paramapping = {}
        subres = patternSub.search(sub[1].replace("\n", " ").strip())
        if subres:
            instance_name = subres["instance"]
            for port in subres["parameter"].strip().lstrip("(").rstrip(")").split(","):
                splitted = port.strip().lstrip(".").rstrip(")").split("(")
                if len(splitted) == 2 and splitted[0] != splitted[1]:
                    paramapping[splitted[0]] = splitted[1]

            for port in subres["ports"].strip().lstrip("(").rstrip(")").split(","):
                splitted = port.strip().lstrip(".").rstrip(")").split("(")
                portmapping[splitted[0]] = splitted[1]
        else:
            instres = patternInstanceName.search(sub[1].replace("\n", " ").strip())
            if instres:
                instance_name = instres["instance"]
        return instance_name, portmapping, paramapping

    gPins = graphviz.Digraph("G", format="svg")
    gPins.attr(rankdir="LR")

    gAll = graphviz.Digraph("G", format="svg")
    gAll.attr(rankdir="LR")

    cluster_n = 0
    edges_all = {}

    for verilog_file in verilogs:
        basename = verilog_file.split("/")[-1]
        fd = open(f"{output}/{basename}.html", "w")
        fd.write(html_begin)
        # fd.write(html_menu(modules, dependsGraph))
        # fd.write(f"<div id=\"{basename}\" class=\"tabcontent\">")
        fd.write(f"<h1>{verilog_file.split('/')[-1]}</h1>\n")

        for moduleName, module in modules.items():
            if module["filename"] != verilog_file:
                continue

            fd.write(f"<h2 id='{moduleName}'>{moduleName}</h2>\n")
            fd.write("<hr/>\n")
            params = []
            for argName, arg in module["params"].items():
                default = arg.get("default", "?")
                color = row_colors[len(params) % 2]
                params.append(f'<tr><td bgcolor="{color}" port="{argName}"><font color="{td_font_color}"><I>{argName}={default}</I></font></td></tr>')

            ports = []
            for argName, arg in module["args"].items():
                if not arg.get("defines"):
                    color = row_colors[len(ports) % 2]
                    ports.append(f'<tr><td bgcolor="{color}" port="{argName}"><font color="{td_font_color}">{argName}{arg.get("size") or ""}</font></td></tr>')

            gSub = graphviz.Digraph("G", format="svg")
            gSub.attr(rankdir="LR")
            sub_edges = {}

            if top == moduleName:
                # read and link pins
                pinmapping = {}
                for suffix in ("cst", "pcf", "lpf"):
                    if not pin_file:
                        for filepath in glob.glob(os.path.join(os.path.dirname(module["filename"]), f"*.{suffix}")):
                            pin_file = filepath
                            break

                if pin_file:
                    print(f"using pin-file: {pin_file}")
                    pin_filename = os.path.basename(pin_file)
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
                    elif pin_type == "lpf":
                        for line in open(pin_file, "r").read().split("\n"):
                            if line.startswith("LOCATE COMP "):
                                realpin = line.split()[-1].strip('";')
                                pin_name = line.split()[-3].strip('";')
                                pinmapping[pin_name] = {
                                    "pin": realpin,
                                }
                    else:
                        print("unsupported pin format:", pin_file)

                if pinmapping:
                    pins = []
                    for argName, arg in module["args"].items():
                        if not arg.get("defines"):
                            pin = pinmapping.get(argName, {}).get("pin", "?")
                            direction = arg.get("direction")
                            color = row_colors[len(pins) % 2]
                            pins.append(f'<tr><td bgcolor="{color}"><font color="{td_font_color}">{direction}</font></td><td bgcolor="{color}" port="{argName}"><font color="{td_font_color}">{pin}</font></td></tr>')
                            arrow = ""
                            if direction == "input":
                                arrow = ""
                            elif direction == "inout":
                                arrow = "both"
                            else:
                                arrow = "back"
                            gSub.edge(f"PINS:{argName}", f"{moduleName}:{argName}", dir=arrow)
                            gAll.edge(f"PINS:{argName}", f"{moduleName}:{argName}", dir=arrow)
                            gPins.edge(f"PINS:{argName}", f"{moduleName}:{argName}", dir=arrow)
                    label = f'<<table color="#FFFFFF" bgcolor="{table_color}" border="0" cellborder="0" cellspacing="1" style="rounded"><tr><td colspan="2"><font color="{th_font_color}">{pin_filename}</font></td></tr>{"".join(pins)}<tr><td><FONT POINT-SIZE="4"> </FONT></td></tr></table>>'
                    gSub.node(
                        "PINS",
                        shape="none",
                        label=label,
                        fontsize="11pt",
                        tooltip=f"FPGA-Pins: {pin_filename}",
                        href="pins.html",
                    )
                    gAll.node(
                        "PINS",
                        shape="none",
                        label=label,
                        fontsize="11pt",
                        tooltip=f"FPGA-Pins: {pin_filename}",
                        href="pins.html",
                    )
                    gPins.node(
                        "PINS",
                        shape="none",
                        label=label,
                        fontsize="11pt",
                        tooltip=f"FPGA-Pins: {pin_filename}",
                        href="pins.html",
                    )

            with gSub.subgraph(name="cluster_0") as c:
                c.attr(style="filled,rounded", color="lightgrey")
                c.attr(label=f"{os.path.basename(verilog_file)} / {moduleName}")
                c.attr(margin="10")

                label = f'<<table color="#FFFFFF" bgcolor="{table_color}" border="0" cellborder="0" cellspacing="1" style="rounded"><tr><td><font color="{th_font_color}">{moduleName}</font></td></tr>{"".join(params)}<tr><td><FONT POINT-SIZE="1"> </FONT></td></tr>{"".join(ports)}<tr><td><FONT POINT-SIZE="4"> </FONT></td></tr></table>>'
                c.node(
                    moduleName,
                    shape="none",
                    label=label,
                    fontsize="11pt",
                    href=f"{verilog_file.split('/')[-1]}.html#{moduleName}",
                    tooltip=f"Module-Header: {moduleName}\\nFilename: {os.path.basename(verilog_file)}",
                    group="g1",
                )
                if top == moduleName:
                    gPins.node(
                        moduleName,
                        shape="none",
                        label=label,
                        fontsize="11pt",
                        href=f"{verilog_file.split('/')[-1]}.html#{moduleName}",
                        tooltip=f"Module-Header: {moduleName}\\nFilename: {os.path.basename(verilog_file)}",
                    )
                sub_first = None
                for sub in module["sub"]:
                    if sub[0] in modules:
                        instance_name, portmapping, paramapping = instance_get(sub)
                        sargs = []
                        for argName, arg in modules[sub[0]]["params"].items():
                            default = arg.get("default", "?")
                            pvalue = paramapping.get(argName, default)
                            color = row_colors[len(sargs) % 2]
                            sargs.append(f'<tr><td bgcolor="{color}" port="{argName}"><font color="{td_font_color}"><I>{argName}={pvalue}</I></font></td></tr>')
                        sports = []
                        for argName, arg in modules[sub[0]]["args"].items():
                            if not arg.get("defines"):
                                ptitle = portmapping.get(argName, argName).replace("&", "AND")
                                color = row_colors[len(sports) % 2]
                                sports.append(f'<tr><td bgcolor="{color}" port="{argName}"><font color="{td_font_color}">{ptitle}</font></td></tr>')

                        label = f'<<table color="#FFFFFF" bgcolor="{table_color}" border="0" cellborder="0" cellspacing="1" style="rounded"><tr><td><font color="{th_font_color}">{instance_name}</font></td></tr>{"".join(sargs)}<tr><td><FONT POINT-SIZE="1"> </FONT></td></tr>{"".join(sports)}<tr><td><FONT POINT-SIZE="4"> </FONT></td></tr></table>>'

                        group = ""
                        if not sub_first:
                            sub_first = instance_name
                            group = "g1"

                        c.node(
                            f"{moduleName}_{instance_name}",
                            shape="none",
                            label=label,
                            fontsize="11pt",
                            href=f"{verilog_file.split('/')[-1]}.html#{moduleName}",
                            tooltip=f"Instance: {instance_name} -> {sub[0]}",
                            group=group,
                        )
                        c.edge(
                            moduleName,
                            f"{moduleName}_{instance_name}",
                            dir="none",
                            style="invis",
                            fontsize="11pt",
                        )
                    else:
                        # unknown modules
                        instance_name, portmapping, paramapping = instance_get(sub)
                        sargs = []
                        for argName, arg in paramapping.items():
                            ptitle = f"{argName.replace('&', 'AND')}={arg.replace('&', 'AND')}"
                            color = row_colors[len(sargs) % 2]
                            sargs.append(f'<tr><td bgcolor="{color}" port="{argName}"><font color="{td_font_color}">{ptitle}</font></td></tr>')
                        sports = []
                        for argName, arg in portmapping.items():
                            ptitle = f"{argName.replace('&', 'AND')}={arg.replace('&', 'AND')}"
                            color = row_colors[len(sports) % 2]
                            sports.append(f'<tr><td bgcolor="{color}" port="{argName}"><font color="{td_font_color}">{ptitle}</font></td></tr>')
                        instance_name = sub[0]
                        label = f'<<table color="#FFFFFF" bgcolor="{table_color}" border="0" cellborder="0" cellspacing="1" style="rounded"><tr><td><font color="{th_font_color}">{instance_name}</font></td></tr>{"".join(sargs)}<tr><td><FONT POINT-SIZE="1"> </FONT></td></tr>{"".join(sports)}<tr><td><FONT POINT-SIZE="4"> </FONT></td></tr></table>>'
                        c.node(
                            f"{moduleName}_{instance_name}",
                            shape="none",
                            label=label,
                            fontsize="11pt",
                            href=f"{verilog_file.split('/')[-1]}.html#{moduleName}",
                            tooltip=f"Instance: {instance_name} -> {sub[0]}",
                            # group=group,
                        )

            cluster_n += 1
            with gAll.subgraph(name=f"cluster_{cluster_n}") as c:
                c.attr(style="filled,rounded", color="lightgrey")
                c.attr(label=f"{os.path.basename(verilog_file)} / {moduleName}")
                c.attr(margin="10")

                label = f'<<table color="#FFFFFF" bgcolor="{table_color}" border="0" cellborder="0" cellspacing="1" style="rounded"><tr><td><font color="{th_font_color}">{moduleName}</font></td></tr>{"".join(ports)}<tr><td><FONT POINT-SIZE="4"> </FONT></td></tr></table>>'
                c.node(
                    moduleName,
                    shape="none",
                    label=label,
                    fontsize="11pt",
                    href=f"{verilog_file.split('/')[-1]}.html#{moduleName}",
                    tooltip=f"Module-Header: {moduleName}\\nFilename: {os.path.basename(verilog_file)}",
                    group="g1",
                )
                sub_first = None
                for sub in module["sub"]:
                    if sub[0] in modules:
                        instance_name, portmapping, paramapping = instance_get(sub)
                        sargs = []
                        for argName, arg in modules[sub[0]]["params"].items():
                            default = arg.get("default", "?")
                            pvalue = paramapping.get(argName, default)
                            color = row_colors[len(sargs) % 2]
                            sargs.append(f'<tr><td bgcolor="{color}" port="{argName}"><font color="{td_font_color}"><I>{argName}={pvalue}</I></font></td></tr>')
                        sports = []
                        for argName, arg in modules[sub[0]]["args"].items():
                            if not arg.get("defines"):
                                ptitle = portmapping.get(argName, argName).replace("&", "AND")
                                color = row_colors[len(sports) % 2]
                                sports.append(f'<tr><td bgcolor="{color}" port="{argName}"><font color="{td_font_color}">{ptitle}</font></td></tr>')

                        label = f'<<table color="#FFFFFF" bgcolor="{table_color}" border="0" cellborder="0" cellspacing="1" style="rounded"><tr><td><font color="{th_font_color}">{instance_name}</font></td></tr>{"".join(sports)}<tr><td><FONT POINT-SIZE="4"> </FONT></td></tr></table>>'

                        group = ""
                        if not sub_first:
                            sub_first = instance_name
                            group = "g1"

                        c.node(
                            f"{moduleName}_{instance_name}",
                            shape="none",
                            label=label,
                            fontsize="11pt",
                            href=f"{verilog_file.split('/')[-1]}.html#{moduleName}",
                            tooltip=f"Instance: {instance_name} -> {sub[0]}",
                            group=group,
                        )
                        c.edge(
                            moduleName,
                            f"{moduleName}_{instance_name}",
                            dir="none",
                            style="invis",
                            fontsize="11pt",
                        )

            # linked instances
            for moduleNameFrom, moduleFrom in modules.items():
                for subFrom in moduleFrom["sub"]:
                    if subFrom[0] == moduleName:
                        instance_name, portmapping, paramapping = instance_get(subFrom)
                        mname = f"{moduleNameFrom}_{instance_name}"
                        subres = patternSub.search(subFrom[1].replace("\n", " ").strip())
                        portmapping = {}
                        new_params = []
                        new_ports = ports.copy()

                        if subres:
                            instance_name = subres["instance"]

                            for param in subres["parameter"].strip().lstrip("(").rstrip(")").split(","):
                                splitted = param.strip().lstrip(".").rstrip(")").split("(")
                                if len(splitted) == 2:
                                    paramapping[splitted[0]] = splitted[1]

                            for argName, arg in module["params"].items():
                                default = arg.get("default", "?")
                                pvalue = paramapping.get(argName, default)
                                color = row_colors[len(new_params) % 2]
                                new_params.append(f'<tr><td bgcolor="{color}" port="{argName}"><font color="{td_font_color}"><I>{argName}={pvalue}</I></font></td></tr>')
                                add_edge(
                                    sub_edges,
                                    f"{mname}:{argName}",
                                    f"{moduleName}:{argName}",
                                    style="dashed",
                                )

                            for port in subres["ports"].strip().lstrip("(").rstrip(")").split(","):
                                splitted = port.strip().lstrip(".").rstrip(")").split("(")
                                portmapping[splitted[0]] = splitted[1]
                                for n, np in enumerate(new_ports):
                                    new_ports[n] = np.replace(f">{splitted[0]}", f">{splitted[1]}")

                        filename = moduleFrom["filename"]
                        label = f'<<table color="#FFFFFF" bgcolor="{table_color}" border="0" cellborder="0" cellspacing="1" style="rounded"><tr><td><font color="{th_font_color}">{moduleNameFrom}/{instance_name}</font></td></tr>{"".join(new_params)}<tr><td><FONT POINT-SIZE="1"> </FONT></td></tr>{"".join(new_ports)}<tr><td><FONT POINT-SIZE="4"> </FONT></td></tr></table>>'
                        gSub.node(
                            mname,
                            shape="none",
                            label=label,
                            href=f"{filename.split('/')[-1]}.html#{moduleNameFrom}",
                            fontsize="11pt",
                            tooltip=f"Source-Instance: {moduleNameFrom} / {instance_name}",
                        )

                        for argName, arg in module["args"].items():
                            if not arg.get("defines"):
                                if arg.get("direction") == "input":
                                    add_edge(
                                        sub_edges,
                                        f"{mname}:{argName}",
                                        f"{moduleName}:{argName}",
                                    )
                                elif arg.get("direction") == "inout":
                                    add_edge(
                                        sub_edges,
                                        f"{mname}:{argName}",
                                        f"{moduleName}:{argName}",
                                        "both",
                                    )
                                else:
                                    add_edge(
                                        sub_edges,
                                        f"{mname}:{argName}",
                                        f"{moduleName}:{argName}",
                                        "back",
                                    )

            # linked sub modules
            for sub in module["sub"]:
                if sub[0] in modules:
                    instance_name, portmapping, paramapping = instance_get(sub)
                    sargs = []
                    for argName, arg in modules[sub[0]]["params"].items():
                        default = arg.get("default", "?")
                        color = row_colors[len(sargs) % 2]
                        sargs.append(f'<tr><td bgcolor="{color}" port="{argName}"><font color="{td_font_color}"><I>{argName}={default}</I></font></td></tr>')
                        add_edge(
                            sub_edges,
                            f"{moduleName}_{instance_name}:{argName}",
                            f"{sub[0]}:{argName}",
                            style="dashed",
                        )

                    sports = []
                    for argName, arg in modules[sub[0]]["args"].items():
                        if not arg.get("defines"):
                            color = row_colors[len(sports) % 2]
                            sports.append(f'<tr><td bgcolor="{color}" port="{argName}"><font color="{td_font_color}">{argName}{arg.get("size") or ""}</font></td></tr>')
                            if arg.get("direction") == "input":
                                add_edge(
                                    sub_edges,
                                    f"{moduleName}_{instance_name}:{argName}",
                                    f"{sub[0]}:{argName}",
                                )
                            elif arg.get("direction") == "inout":
                                add_edge(
                                    sub_edges,
                                    f"{moduleName}_{instance_name}:{argName}",
                                    f"{sub[0]}:{argName}",
                                    "both",
                                )
                            else:
                                add_edge(
                                    sub_edges,
                                    f"{moduleName}_{instance_name}:{argName}",
                                    f"{sub[0]}:{argName}",
                                    "back",
                                )

                    label = f'<<table color="#FFFFFF" bgcolor="{table_color}" border="0" cellborder="0" cellspacing="1" style="rounded"><tr><td><font color="{th_font_color}">{sub[0]}</font></td></tr>{"".join(sargs)}<tr><td><FONT POINT-SIZE="1"> </FONT></td></tr>{"".join(sports)}<tr><td><FONT POINT-SIZE="4"> </FONT></td></tr></table>>'
                    filename = modules[sub[0]]["filename"]
                    gSub.node(
                        sub[0],
                        shape="none",
                        label=label,
                        href=f"{filename.split('/')[-1]}.html#{sub[0]}",
                        fontsize="11pt",
                        tooltip=f"Module: {sub[0]}\nFilename: {filename.split('/')[-1]}",
                    )

            for name, edge in sub_edges.items():
                gSub.edge(edge["from"], edge["to"], dir=edge["dir"], style=edge["style"])

            fd.write('<table border=0 width=100%><tr><td valign="top" align="left" width=30%>')

            fd.write("<h3>Module-Ports</h3>\n")
            fd.write("<table width=90%>\n")
            fd.write(f'<tr bgcolor="{table_color}"><th>direction</th><th>type</th><th>name</th><th>size</th><th>defines</th><th>comment</th></tr>\n')
            rn = 0
            for argName, arg in module["args"].items():
                color = row_colors[rn % 2]
                fd.write(f'<tr bgcolor="{color}"><td>{arg.get("direction", "")}</td><td>{arg.get("signed", "")} {arg.get("type", "")}</td><td>{argName}</td><td>{arg.get("size", "")}</td><td>{arg.get("defines") or ""}</td><td>{arg.get("comment") or ""}</td></tr>\n')
                rn += 1
            fd.write("</table>\n")
            fd.write("<br>\n")

            if module["params"]:
                fd.write("<h3>Module-Parameter</h3>\n")
                fd.write("<table width=90%>\n")
                fd.write(f'<tr bgcolor="{table_color}"><th>name</th><th>size</th><th>default</th></tr>\n')
                rn = 0
                for argName, arg in module["params"].items():
                    color = row_colors[rn % 2]
                    fd.write(f'<tr bgcolor="{color}"><td>{arg.get("name", "")}</td><td>{arg.get("size", "")}</td><td>{arg.get("default", "")}</td></tr>\n')
                    rn += 1
                fd.write("</table>\n")
                fd.write("<br>\n")

            fd.write('</td><td valign="top" align="right">')
            svg_img(gSub, moduleName)
            fd.write("</td></tr></table>")

            if verilog_file in dotsvgs:
                # svgdata = open(dotsvgs[verilog_file], "r").read()
                # fd.write(svgdata)
                fd.write("<h3>Logic</h3>\n")
                fd.write("<hr/>\n")
                fd.write(f'<center><a target="_blank" href="{os.path.basename(dotsvgs[verilog_file])}"><img width="90%" src="{os.path.basename(dotsvgs[verilog_file])}" /></a></center>')
                fd.write("<hr/>\n")

            fd.write("<h3>Verilog-Source</h3>\n")
            fd.write(f"File: {module['filename']}<br />")
            fd.write("<pre><code class='language-verilog'>")
            fd.write(module["filedata"])
            fd.write("</code></pre>")
            fd.write("<hr/>\n")

        fd.write(html_end)
        fd.close()

    for name, edge in edges_all.items():
        if not edge["style"]:
            gAll.edge(edge["from"], edge["to"], dir=edge["dir"], style=edge["style"])

    fd = open(f"{output}/pins.html", "w")
    fd.write("<html>")
    fd.write(html_begin)
    # fd.write(html_menu(modules, dependsGraph))
    # fd.write(f"<div id=\"pins\" class=\"tabcontent\">")
    fd.write("\n")

    svg_img(gPins, "pins")

    fd.write("<br>\n")
    fd.write("\n")
    for pin_file in glob.glob(os.path.join(os.path.dirname(module["filename"]), "pins.*")):
        pindata = open(pin_file, "r").read()
        fd.write("<h3>Pin Constraints</h3>\n")
        fd.write(f"File: {pin_file}<br />")
        fd.write("<pre><code class='language-verilog'>")
        fd.write(pindata)
        fd.write("</code></pre>")
        fd.write("<hr/>\n")
    fd.write("\n")
    fd.write("<br>\n")
    fd.write(html_end)
    fd.close()

    fd = open(f"{output}/main.html", "w")
    fd.write("<html>")
    fd.write(html_begin)
    # fd.write(html_menu(modules, dependsGraph))
    # fd.write(f"<div id=\"main\" class=\"tabcontent\">")
    fd.write("\n")

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
    fd.write('    <frame src="menu.html" name="menu">')
    fd.write('    <frame src="main.html" name="main">')
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
    sargs = parser.parse_args()

    verilog2doc(sargs)
