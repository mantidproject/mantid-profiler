# children_util.py - helper functions for dealing with child processes
#
######################################################################


import psutil


def all_children(pr: psutil.Process) -> list[psutil.Process]:
    try:
        return pr.children(recursive=True)
    except Exception:  # noqa: BLE001
        return []


def update_children(old_children: dict[int, psutil.Process], new_children: list[psutil.Process]):
    new_dct = {}
    for ch in new_children:
        new_dct.update({ch.pid: ch})

    todel = []
    for pid in old_children.keys():
        if pid not in new_dct.keys():
            todel.append(pid)

    for pid in todel:
        del old_children[pid]

    updct = {}
    for pid in new_dct.keys():
        if pid not in old_children.keys():
            updct.update({pid: new_dct[pid]})
    old_children.update(updct)
