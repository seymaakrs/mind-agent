from __future__ import annotations

import argparse
import sys
from typing import Any

from src.app.orchestrator_runner import run_orchestrator


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Orchestrator agenti CLI uzerinden calistirir."
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="user_input",
        help="Kullanici girdisi. Bos birakilirsa stdin'den okunur.",
    )
    parser.add_argument(
        "-f",
        "--task-file",
        dest="task_file",
        default="task.txt",
        help="Girdi okunacak dosya yolu. -i/--input verilmemisse kullanilir. Varsayilan: task.txt",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    user_input: str | None = args.user_input
    if not user_input:
        # Dosyadan oku, yoksa stdin'den dene
        try:
            with open(args.task_file, "r", encoding="utf-8") as f:
                user_input = f.read().strip()
        except FileNotFoundError:
            user_input = ""

        if not user_input:
            user_input = sys.stdin.read().strip()
        if not user_input:
            print(
                f"Girdi alinmadi. -i/--input ile, {args.task_file} dosyasinda veya stdin uzerinden metin gonderin."
            )
            return 1

    output: str = run_orchestrator(user_input=user_input, context={})
    try:
        print(output)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        safe = output.encode(enc, errors="backslashreplace").decode(enc, errors="ignore")
        print(safe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
