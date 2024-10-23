from pathlib import Path
from time import sleep
from typing import Optional

import numpy as np
import psutil
from children_util import all_children, update_children
from time_util import get_current_time, get_start_time


def monitor(pid: int, logfile: Path, interval: Optional[float], show_bytes: bool = False) -> None:
    """Monitor the disk usage of the supplied process id
    The interval defaults to 0.05 if not supplied"""
    # change interval to reasonable default
    # being too small doesn't aid in understanding performance
    DEFAULT_INTERVAL = 0.05
    if interval is None:
        interval = DEFAULT_INTERVAL
    else:
        interval = max(DEFAULT_INTERVAL, interval)

    process = psutil.Process(pid)

    # Record start time
    starting_point = get_start_time()
    start_time = get_current_time()
    last_time = start_time

    disk_before = process.io_counters()

    with open(logfile, "w") as handle:
        # add header
        handle.write(
            "# {0:12s} {1:12s} {2:12s} {3:12s} {4}\n".format(
                "Elapsed time".center(12),
                "ReadChars (Mbit per sec)".center(12),
                "WriteChars (Gbit per sec)".center(12),
                "ReadBytes (Gbit per sec)".center(12),
                "WriteBytes (Gbit per sec)".center(12),
            )
        )
        handle.write("START_TIME: {}\n".format(starting_point))

        children = {}
        for ch in all_children(process):
            children.update({ch.pid: {"process": ch, "disk_before": ch.io_counters()}})

        # conversion factor of bytes per sec to Giga-bits per second - 8 bits in a byte
        conversion_to_size = 1e-9
        if not show_bytes:
            conversion_to_size = 8.0 * conversion_to_size

        # main event loop
        try:
            while True:
                try:
                    # update information
                    current_time = get_current_time()
                    disk_after = process.io_counters()

                    delta_time = current_time - last_time
                    if delta_time <= 0.0:
                        continue

                    # calculate bytes amount per second
                    read_char_per_sec = (
                        conversion_to_size * (disk_after.read_chars - disk_before.read_chars) / delta_time
                    )
                    write_char_per_sec = (
                        conversion_to_size * (disk_after.write_chars - disk_before.write_chars) / delta_time
                    )

                    read_byte_per_sec = (
                        conversion_to_size * (disk_after.read_bytes - disk_before.read_bytes) / delta_time
                    )
                    write_byte_per_sec = (
                        conversion_to_size * (disk_after.write_bytes - disk_before.write_bytes) / delta_time
                    )

                    # get information from children
                    update_children(children, all_children(process))
                    for child in children.values():
                        try:
                            child_disk_after = child["process"].io_counters()

                            read_char_per_sec += (
                                conversion_to_size
                                * (child_disk_after.read_chars - child["disk_before"].read_chars)
                                / delta_time
                            )

                            write_char_per_sec += (
                                conversion_to_size
                                * (child_disk_after.write_chars - child["disk_before"].write_chars)
                                / delta_time
                            )

                            read_byte_per_sec += (
                                conversion_to_size
                                * (child_disk_after.read_bytes - child["disk_before"].read_bytes)
                                / delta_time
                            )

                            write_byte_per_sec += (
                                conversion_to_size
                                * (child_disk_after.write_bytes - child["disk_before"].write_bytes)
                                / delta_time
                            )

                            child["disk_before"] = child_disk_after

                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue

                    # write information to the log file
                    handle.write(
                        "{0:12.6f} {1:12.3f} {2:12.3f} {3:12.3f} {4}\n".format(
                            current_time - start_time + starting_point,
                            read_char_per_sec,
                            write_char_per_sec,
                            read_byte_per_sec,
                            write_byte_per_sec,
                        )
                    )

                    # copy over information to new previous
                    disk_before = disk_after
                    last_time = current_time
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break  # all done

                if interval > 0.0:
                    sleep(interval)
        except KeyboardInterrupt:  # pragma: no cover
            print(f"killing process being monitored [PID={process.pid}]:", " ".join(process.cmdline()))
            process.kill()


def parse_log(filename: Path, cleanup: bool = True):
    rows = []
    start_time = 0.0
    with open(filename, "r") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith("#") or not line:  # skip comment and empty lines
                continue
            elif line.startswith("START_TIME:"):
                start_time = float(line.split()[-1])
                continue

            # parse the line
            rows.append([float(value) for value in line.split()])

    # remove the file
    if cleanup and filename.exists():
        filename.unlink()

    # return results
    return start_time, np.array(rows)
