from time import sleep
from typing import Optional

import psutil

from time_util import get_current_time, get_start_time


def monitor(pid: int, logfile: str, interval: Optional[float]):
    """Monitor the disk usage of the supplied process id
    The interval defaults to ??? if not supplied"""  # TODO
    # change None to reasonable default
    if interval is None:
        interval = 0.1  # TODO

    process = psutil.Process(pid)

    # Record start time
    starting_point = get_start_time()
    start_time = get_current_time()

    disk_before = process.io_counters()

    with open(logfile, "w") as handle:
        # add header
        handle.write(
            "# {0:12s} {1:12s} {2:12s} {3:12s} {4}\n".format(
                "Elapsed time".center(12),
                "ReadChars (per sec)".center(12),
                "WriteChars (per sec)".center(12),
                "ReadBytes (per sec)".center(12),
                "WriteBytes (per sec)".center(12),
            )
        )
        handle.write("START_TIME: {}\n".format(starting_point))

        # main event loop
        try:
            while True:
                try:
                    # update information
                    current_time = get_current_time()
                    disk_after = process.io_counters()

                    # calculate amount per second
                    read_char_per_sec = (disk_after.read_chars - disk_before.read_chars) / interval
                    write_char_per_sec = (disk_after.write_chars - disk_before.write_chars) / interval

                    read_byte_per_sec = (disk_after.read_bytes - disk_before.read_bytes) / interval
                    write_byte_per_sec = (disk_after.write_bytes - disk_before.write_bytes) / interval

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
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break  # all done

                if interval > 0.0:
                    sleep(interval)
        except KeyboardInterrupt:  # pragma: no cover
            print(f"killing process being monitored [PID={process.pid}]:", " ".join(process.cmdline()))
            process.kill()
