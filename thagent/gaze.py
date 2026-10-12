"""Dò hướng nhìn cho clip đơn → work/gaze.json (cam=true: nhìn thẳng ống kính). Dùng chung bộ dò với clips.py."""
from __future__ import annotations

import json
import sys

from . import clips as C, pipeline as P


def run(c: "P.Ctx", force: bool = False):
    dst = c.path("work", "gaze.json")
    if dst.exists() and not force:
        return dst
    src = c.project.source.path
    g = C._gaze(src, P.probe_source(src), c.log if hasattr(c, "log") else print)
    dst.write_text(json.dumps(g))
    return dst


def main():
    print(run(P.Ctx(sys.argv[1]), "--force" in sys.argv))


if __name__ == "__main__":
    main()
