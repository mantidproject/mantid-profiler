import time


def get_start_time() -> float:
    return time.time()


def get_current_time() -> float:
    try:
        return time.perf_counter()
    except AttributeError:
        return time.time()
