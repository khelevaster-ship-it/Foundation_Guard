"""FoundationGuard: the programs the kit starts get no keyboard (AI-made, Claude, 2026-11-15).

The owner, 15 Nov: "type FGED and press Enter" came up in Windows Terminal, and then the window took no keys at all, not
even Ctrl+C. The kit's own git calls just before it shared the window's keyboard, and a program git starts (Git LFS, a
login helper, a file watcher) can keep it. Every program the kit starts now gets an empty input unless the kit hands it
one; the kit's own questions still read the owner's keyboard themselves. Loaded by fg/paths.py, which every kit command
loads.
"""
import os, subprocess

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k


class _Quiet(subprocess.Popen):
    def __init__(self, args, *a, **k):
        if not a and k.get("stdin") is None and not BREAK("quiet_stdin"):
            k["stdin"] = subprocess.DEVNULL
        super().__init__(args, *a, **k)


def install():
    if not isinstance(subprocess.Popen, type) or not issubclass(subprocess.Popen, _Quiet):
        subprocess.Popen = _Quiet                      # subprocess.run and friends start their programs through it


install()
