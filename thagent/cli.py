"""CLI: python -m thagent.cli <project> --source PATH [--test A B | --full] [--replan]"""
import argparse

from . import pipeline as P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--source")
    ap.add_argument("--test", nargs=2, type=int, metavar=("FRAME_START", "FRAME_END"))
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--replan", action="store_true")
    ap.add_argument("--vocab", default="", help="từ điển tên riêng, phân cách bằng dấu phẩy")
    a = ap.parse_args()
    c = P.Ctx(a.project)
    P.step_ingest(c, a.source or c.project.source.path)
    P.step_transcribe(c, [v.strip() for v in a.vocab.split(",") if v.strip()] or None)
    P.step_matting(c)
    P.step_plan(c, force=a.replan)
    if a.test:
        print(P.step_render(c, tuple(a.test), "test"))
    elif a.full:
        print(P.step_render(c, None, "full"))


if __name__ == "__main__":
    main()
