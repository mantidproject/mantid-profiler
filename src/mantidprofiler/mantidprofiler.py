# Mantid algorithm profiler
# Copyright (C) 2018 Neil Vaytet & Igor Gudich, European Spallation Source
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# PYTHON_ARGCOMPLETE_OK

import argparse
from pathlib import Path
from threading import Thread

import argcomplete
import numpy as np

import mantidprofiler.algorithm_tree as at
from mantidprofiler import __version__
from mantidprofiler.diskrecord import monitor as diskmonitor
from mantidprofiler.diskrecord import parse_log as parse_disk_log
from mantidprofiler.psrecord import monitor as cpumonitor, no_monitor
from mantidprofiler.psrecord import parse_log as parse_cpu_log


# Convert string to RGB color
# This method is simple but does not guarantee uniqueness of the color.
# It is however random enough for our purposes
def stringToColor(string):
    red = 0
    grn = 0
    blu = 0
    for i in range(0, len(string), 3):
        red += ord(string[i])
    for i in range(1, len(string), 3):
        grn += ord(string[i])
    for i in range(2, len(string), 3):
        blu += ord(string[i])
    red %= 255
    grn %= 255
    blu %= 255
    return [red, grn, blu, (red + grn + blu) / 3.0]


# Generate HTML output for a tree node
def treeNodeToHtml(node, lmax, sync_time, header, count, tot_time):
    x0 = ((node.info[1] + header) / 1.0e9) - sync_time
    x1 = ((node.info[2] + header) / 1.0e9) - sync_time
    x2 = 0.5 * (x0 + x1)
    y0 = 0.0
    y1 = -(lmax - node.level + 1)
    dt = x1 - x0

    # Get unique color from algorithm name
    color = stringToColor(node.info[0].split(" ")[0])
    # Compute raw time and percentages
    rawTime = dt
    if len(node.children) > 0:
        for ch in node.children:
            rawTime -= (ch.info[2] - ch.info[1]) / 1.0e9
    percTot = dt * 100.0 / tot_time
    percRaw = rawTime * 100.0 / tot_time

    # Create the text inside hover box
    boxText = node.info[0] + " : "
    if dt < 0.1:
        boxText += "%.1E" % dt
    else:
        boxText += "%.1f" % dt
    boxText += "s (%.1f%%) | %.1fs (%.1f%%)<br>" % (percTot, rawTime, percRaw)

    if node.parent is not None:
        boxText += "Parent: " + node.parent.info[0] + "<br>"
    if len(node.children) > 0:
        boxText += "Children: <br>"
        for ch in node.children:
            boxText += "  - " + ch.info[0] + "<br>"

    # Create trace
    base_url = "https://docs.mantidproject.org/nightly/algorithms/"
    outputString = "trace%i = {\n" % count
    outputString += "x: [%f, %f, %f, %f, %f],\n" % (x0, x0, x2, x1, x1)
    outputString += "y: [%f, %f, %f, %f, %f],\n" % (y0, y1, y1, y1, y0)
    outputString += "fill: 'tozeroy',\n"
    outputString += "fillcolor: 'rgb(%i,%i,%i)',\n" % (color[0], color[1], color[2])
    outputString += "line: {\n"
    outputString += "color: '#000000',\n"
    outputString += "dash: 'solid',\n"
    outputString += "shape: 'linear',\n"
    outputString += "width: 1.0\n"
    outputString += "},\n"
    outputString += "mode: 'lines+text',\n"
    # If the background color is too bright, make the font color black.
    # Default font color is white
    if color[3] > 180:
        textcolor = "#000000"
    else:
        textcolor = "#ffffff"
    outputString += (
        "text: ['', '', '<a style=\"text-decoration: none; color: %s;\" href=\"%s%s-v1.html\">%s</a>', '', ''],\n"
        % (textcolor, base_url, node.info[0].split()[0], node.info[0])
    )
    outputString += "textposition: 'top',\n"
    outputString += "hovertext: '" + boxText + "',\n"
    outputString += "hoverinfo: 'text',\n"
    outputString += "type: 'scatter',\n"
    outputString += "xaxis: 'x',\n"
    outputString += "yaxis: 'y4',\n"
    outputString += "showlegend: false,\n"
    outputString += "};\n"

    return outputString


def writeArray(stream, array):
    stream.write("[")
    stream.write(",".join([str(value) for value in array]))
    stream.write("],\n")


def writeTrace(stream, x_axis, y_axis, x_name: str, y_name: str, label: str):
    stream.write("    x: ")
    writeArray(stream, x_axis)
    stream.write("    y: ")
    writeArray(stream, y_axis)

    stream.write("  xaxis: '{}',\n".format(x_name))
    stream.write("  yaxis: '{}',\n".format(y_name))
    stream.write("  type: 'scatter',\n")
    stream.write("  name:'{}',\n".format(label))


# Generate HTML interactive plot with Plotly library
def htmlProfile(
    filename=None,
    cpu_x=None,
    cpu_data=None,
    disk_x=None,
    disk_data=None,
    disk_in_bytes=False,
    algm_records=None,
    fill_factor=0,
    nthreads=0,
    lmax=0,
    sync_time=0,
    header=None,
    html_height=800,
):
    htmlFile = open(filename, "w")
    htmlFile.write("<head>\n")
    htmlFile.write('  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>\n')
    htmlFile.write("</head>\n")
    htmlFile.write("<body>\n")
    htmlFile.write('  <div id="myDiv"></div>\n')
    htmlFile.write("  <script>\n")

    trace_count = 0
    if cpu_data:
        # CPU
        trace_count += 1
        htmlFile.write(f"  var trace{trace_count} = {{\n")
        writeTrace(htmlFile, x_axis=cpu_x, y_axis=cpu_data[:, 1], x_name="x", y_name="y1", label="CPU")
        htmlFile.write("};\n")

        trace_count += 1
        # RAM, in GB
        htmlFile.write(f"  var trace{trace_count} = {{\n")
        writeTrace(htmlFile, x_axis=cpu_x, y_axis=cpu_data[:, 2] / 1000, x_name="x", y_name="y2", label="RAM")
        htmlFile.write("};\n")

        # Active threads
        trace_count += 1
        htmlFile.write(f"  var trace{trace_count} = {{\n")
        writeTrace(
            htmlFile, x_axis=cpu_x, y_axis=cpu_data[:, 4] * 100.0, x_name="x", y_name="y1", label="Active threads"
        )
        htmlFile.write("};\n")

    if disk_data:
        # read chars
        trace_count += 1
        htmlFile.write("  var trace{trace_count} = {{\n")
        writeTrace(htmlFile, x_axis=disk_x, y_axis=disk_data[:, 1], x_name="x", y_name="y3", label="Read")
        htmlFile.write("};\n")

        # write chars
        trace_count += 1
        htmlFile.write("  var trace{trace_count} = {{\n")
        writeTrace(htmlFile, x_axis=disk_x, y_axis=disk_data[:, 2], x_name="x", y_name="y3", label="Write")
        htmlFile.write("};\n")
    if not cpu_data:
        finish = max([x["finish"] for x in algm_records])
        start = min([x["start"] for x in algm_records])
        cpu_x = [(finish - start) / 1.0e9]
        print(cpu_x)
        print(header)
    dataString = "[" + ",".join([f"trace{i}" for i in range(1, trace_count)])  # traces that already exist
    for tree in at.toTrees(algm_records):
        for node in tree.to_list():
            print(node.info)
            if not sync_time:
                sync_time = (min([x["start"] for x in algm_records]) + header) / 1e9
            htmlFile.write(treeNodeToHtml(node, lmax, sync_time, header, trace_count, cpu_x[-1]))
            dataString += ",trace%i" % trace_count if trace_count else "trace%i" % trace_count
            trace_count += 1
    dataString += "]"

    htmlFile.write("var data = " + dataString + ";\n")
    htmlFile.write("var layout = {\n")
    htmlFile.write("  'height': {},\n".format(html_height))
    htmlFile.write("  'xaxis' : {\n")
    htmlFile.write("    'domain' : [0, 1.0],\n")
    htmlFile.write("    'title' : 'Time (s)',\n")
    htmlFile.write("    'side' : 'top',\n")
    htmlFile.write("  },\n")
    htmlFile.write("  'yaxis1': {\n")  # upper - CPU on left
    htmlFile.write("    'domain' : [0.6, 1.0],\n")
    htmlFile.write("    'title': 'CPU (%)',\n")
    htmlFile.write("    'side': 'left',\n")
    htmlFile.write("    'fixedrange': true,\n")
    htmlFile.write("    },\n")
    htmlFile.write("  'yaxis2': {\n")  # upper - RAM on right
    htmlFile.write("    'title': 'RAM (GB)',\n")
    htmlFile.write("    'overlaying': 'y1',\n")
    htmlFile.write("    'side': 'right',\n")
    htmlFile.write("    'fixedrange': true,\n")
    htmlFile.write("    'showgrid': false,\n")
    htmlFile.write("    },\n")
    htmlFile.write("  'yaxis3': {\n")  # middle - disk
    htmlFile.write("    'domain' : [0.45, 0.6],\n")
    htmlFile.write("    'anchor' : 'x',\n")
    if disk_in_bytes:
        htmlFile.write("    'title': 'GBps',\n")
    else:
        htmlFile.write("    'title': 'Gbps',\n")
    htmlFile.write("    'side': 'left',\n")
    htmlFile.write("    'fixedrange': true,\n")
    htmlFile.write("    },\n")
    htmlFile.write("  'yaxis4': {\n")  # lower - algorithm annotations
    htmlFile.write("    'domain' : [0, 0.45],\n")
    htmlFile.write("    'anchor' : 'x',\n")
    htmlFile.write("    'showgrid': false,\n")
    htmlFile.write("    'ticks': '',\n")
    htmlFile.write("    'showticklabels': false,\n")
    htmlFile.write("    'fixedrange': true,\n")
    htmlFile.write("    'side': 'left',\n")
    htmlFile.write("    },\n")
    htmlFile.write("  'hovermode' : 'closest',\n")
    htmlFile.write("  'hoverdistance' : 100,\n")
    htmlFile.write("  'legend': {\n")
    htmlFile.write("    'x' : 0,\n")
    htmlFile.write("    'y' : 1.1,\n")
    htmlFile.write("    'orientation' : 'h',\n")
    htmlFile.write("  },\n")
    htmlFile.write("  'annotations': [{\n")
    htmlFile.write("    xref: 'paper',\n")
    htmlFile.write("    yref: 'paper',\n")
    htmlFile.write("    x: 1,\n")
    htmlFile.write("    xanchor: 'right',\n")
    htmlFile.write("    y: 1.1,\n")
    htmlFile.write("    yanchor: 'bottom',\n")
    htmlFile.write("    text: 'Fill factor: %.1f%%',\n" % fill_factor)
    htmlFile.write("    showarrow: false\n")
    htmlFile.write("  }],\n")
    htmlFile.write("  'shapes': [{\n")
    htmlFile.write("      layer: 'below',\n")
    htmlFile.write("      fillcolor: '#E0E0E0',\n")
    htmlFile.write("      line : {\n")
    htmlFile.write("        width: 0,\n")
    htmlFile.write("      },\n")
    htmlFile.write("      x0: 0.0,\n")
    htmlFile.write("      x1: %f,\n" % cpu_x[-1])
    htmlFile.write("      y0: 0,\n")
    htmlFile.write("      y1: %i,\n" % (nthreads * 100))
    htmlFile.write("      xref: 'x',\n")
    htmlFile.write("      yref: 'y1',\n")
    htmlFile.write("    }],\n")
    htmlFile.write("};\n")
    htmlFile.write("Plotly.newPlot('myDiv', data, layout, {scrollZoom: true});\n")
    htmlFile.write("</script>\n</body>\n</html>\n")
    htmlFile.close()


# Main function to launch process monitor and create interactive HTML plot
def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Profile a Mantid workflow", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("pid", type=int, help="the process id")

    parser.add_argument("--outfile", type=Path, default="profile.html", help="name of output html file")

    parser.add_argument(
        "--infile", type=Path, default="algotimeregister.out", help="name of input file containing algorithm timings"
    )

    parser.add_argument(
        "--logfile", type=Path, default="mantidprofile.txt", help="name of output file containing process monitor data"
    )

    parser.add_argument(
        "--diskfile", type=Path, default="mantiddisk.txt", help="name of output file containing process disk usage data"
    )

    parser.add_argument(
        "--interval",
        type=float,
        help="how long to wait between each sample (in "
        "seconds). By default the process is sampled "
        "as often as possible.",
    )

    parser.add_argument("--noclean", action="store_true", help="remove files upon successful completion")

    parser.add_argument("--height", type=int, default=800, help="height for html plot")

    parser.add_argument("--bytes", action="store_true", help="Report disk speed in GBps rather than Gbps")

    parser.add_argument(
        "--mintime",
        type=float,
        default=0.1,
        help="minimum duration for an algorithm to appear in the profiling graph (in seconds).",
    )

    parser.add_argument("--version", action="version", version=f"mantidprofiler {__version__}")

    parser.add_argument("--nodisk", action="store_true", help="Turn off disk read, required for compatability with osx")

    parser.add_argument("--nocpu", action="store_true", help="Turn off cpu read, required for compatability with osx")

    # parse command line arguments
    argcomplete.autocomplete(parser)
    args = parser.parse_args(argv)  # allow getting them supplied to `main()` in tests

    print(f"Attaching to process {args.pid}")

    if not args.nodisk:
        # start the disk monitor in a separate thread
        diskthread = Thread(
            target=diskmonitor,
            args=(args.pid,),
            kwargs={"logfile": args.diskfile, "interval": args.interval, "show_bytes": args.bytes},
        )
        diskthread.start()

        # wait for disk monitor to finish
        diskthread.join()

    if not args.nocpu:
        # cpu monitor in main thread to prevent early exit
        cpumonitor(int(args.pid), logfile=args.logfile, interval=args.interval)
    else:
        no_monitor(int(args.pid), interval=args.interval)

    # Read in algorithm timing log and build tree
    try:
        header, records = at.fromFile(Path(args.infile), cleanup=not args.noclean)
        print(records)
        records = [x for x in records if x["finish"] - x["start"] > (args.mintime * 1.0e9)]
        print(f"Records found: {len(records)}")
        # Number of threads allocated to this run
        nthreads = int(header.split()[3])
        # Run start time
        header = int(header.split()[1])
        # Find maximum level in all trees
        lmax = 0
        for tree in at.toTrees(records):
            for node in tree.to_list():
                lmax = max(node.level, lmax)
    except FileNotFoundError as e:
        print("failed to load file:", e.filename)
        print("creating plot without algorithm annotations")

        import psutil

        nthreads = psutil.cpu_count()
        lmax = 1
        header = ""
        records = []

    # Read in disk usage - sync_time will be overwritten by cpu below
    if not args.nodisk:
        args.diskfile = Path(args.diskfile)
        sync_time, disk_data = parse_disk_log(args.diskfile, cleanup=not args.noclean)
        # Time series
        disk_x = disk_data[:, 0] - sync_time
    else:
        disk_x = disk_data = None
        sync_time = 0

    if not args.nocpu:
        # Read in CPU and memory activity log
        sync_time, cpu_data = parse_cpu_log(args.logfile, cleanup=not args.noclean)
        # Time series
        cpu_x = cpu_data[:, 0] - sync_time
        print(sync_time)

        # Integrate under the curve and compute CPU usage fill factor
        area_under_curve = np.trapz(cpu_data[:, 1], x=cpu_x)
        fill_factor = area_under_curve / ((cpu_x[-1] - cpu_x[0]) * nthreads)
    else:
        cpu_data = cpu_x = None
        fill_factor = sync_time = 0

    # Create HTML output with Plotly
    htmlProfile(
        filename=args.outfile,
        cpu_x=cpu_x,
        cpu_data=cpu_data,
        disk_x=disk_x,
        disk_data=disk_data,
        disk_in_bytes=args.bytes,
        algm_records=records,
        fill_factor=fill_factor,
        nthreads=nthreads,
        lmax=lmax,
        sync_time=sync_time,
        header=header,
        html_height=args.height,
    )

if __name__ == "__main__":
    raise SystemExit(main())
