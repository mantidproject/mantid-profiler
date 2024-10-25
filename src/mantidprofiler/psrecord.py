# Copyright (c) 2013, Thomas P. Robitaille
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
###############################################################################
#
# 2018: Modified for Mantid profiler by Neil Vaytet & Igor Gudich
# https://github.com/astrofrog/psrecord
#
###############################################################################

import copy
from pathlib import Path
from time import sleep
from typing import Optional

import numpy as np
import psutil

from mantidprofiler.children_util import all_children, update_children
from mantidprofiler.time_util import get_current_time, get_start_time


# returns percentage for system + user time
def get_percent(process):
    return process.cpu_percent()


def get_memory(process):
    return process.memory_info()


def get_threads(process):
    return process.threads()


def monitor(pid: int, logfile: Path, interval: Optional[float]) -> None:
    # change None to reasonable default
    if interval is None:
        interval = 0.0

    pr = psutil.Process(pid)

    # Record start time
    starting_point = get_start_time()
    start_time = get_current_time()

    f = open(logfile, "w")
    f.write(
        "# {0:12s} {1:12s} {2:12s} {3:12s} {4}\n".format(
            "Elapsed time".center(12),
            "CPU (%)".center(12),
            "Real (MB)".center(12),
            "Virtual (MB)".center(12),
            "Threads info".center(12),
        )
    )
    f.write("START_TIME: {}\n".format(starting_point))

    children = {}
    for ch in all_children(pr):
        children.update({ch.pid: ch})

    try:
        # Start main event loop
        while True:
            # Find current time
            current_time = get_current_time()

            try:
                pr_status = pr.status()
            except TypeError:  # psutil < 2.0
                pr_status = pr.status
            except psutil.NoSuchProcess:  # pragma: no cover
                break

            # Check if process status indicates we should exit
            if pr_status in [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD]:
                print("Process finished ({0:.2f} seconds)".format(current_time - start_time))
                break

            # Get current CPU and memory
            try:
                current_cpu = get_percent(pr)
                current_mem = get_memory(pr)
                current_threads = get_threads(pr)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            current_mem_real = current_mem.rss / 1024.0**2
            current_mem_virtual = current_mem.vms / 1024.0**2

            # Get information for children
            update_children(children, all_children(pr))
            for key, child in children.items():
                try:
                    current_cpu += get_percent(child)
                    current_mem = get_memory(child)
                    current_threads.extend(get_threads(child))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                current_mem_real += current_mem.rss / 1024.0**2
                current_mem_virtual += current_mem.vms / 1024.0**2

            f.write(
                "{0:12.6f} {1:12.3f} {2:12.3f} {3:12.3f} {4}\n".format(
                    current_time - start_time + starting_point,
                    current_cpu,
                    current_mem_real,
                    current_mem_virtual,
                    current_threads,
                )
            )
            f.flush()

            if interval > 0.0:
                sleep(interval)

    except KeyboardInterrupt:  # pragma: no cover
        print(f"killing process being monitored [PID={pr.pid}]:", " ".join(pr.cmdline()))
        pr.kill()

    if logfile:
        f.close()


# Parse the logfile outputted by psrecord
def parse_log(filename: Path, cleanup: bool = True):
    rows: list = []
    dct1: dict = {}  # starts out uninitialized
    dct2: dict = {}
    start_time = 0.0
    with open(filename, "r") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            elif line.startswith("START_TIME:"):
                start_time = float(line.split()[-1])
                continue

            # remove unwanted characters/strings
            for item in ("[", "]", "(", ")", ",", "pthread", "id=", "user_time=", "system_time="):
                line = line.replace(item, "")
            row = []
            lst = line.split()
            for i in range(4):
                row.append(float(lst[i]))
            i = 4
            dct1 = copy.deepcopy(dct2)
            dct2.clear()
            while i < len(lst):
                idx = int(lst[i])
                i += 1
                ut = float(lst[i])
                i += 1
                st = float(lst[i])
                i += 1
                dct2.update({idx: [ut, st]})
            count = 0
            for key, val in dct2.items():
                if key not in dct1.keys():
                    count += 1
                    continue
                elem = dct1[key]
                if val[0] != elem[0] or val[1] != elem[1]:
                    count += 1
            row.append(count)
            row.append(len(dct2))
            rows.append(row)

    # remove the file
    if cleanup and filename.exists():
        filename.unlink()

    # return results
    return start_time, np.array(rows)
