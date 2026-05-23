#!/usr/bin/env python3
"""Analyze shadow-mode parity logs from Cloud Logging.

During Faz 3 of the Late->Zernio migration the publisher runs in shadow mode:
every publish call hits BOTH backends and emits a structured log line tagged
``publisher.shadow.diff``. This script pulls those entries from Cloud Logging
and prints a divergence summary.

Two modes:
  --mode=shadow      (default) Pulls Late vs Zernio diffs, expects 0
                     divergence before Faz 6 can merge.
  --mode=zernio-only Pulls Zernio-only error rates from a post-cutover
                     revision, expects error rate <1%% (configurable via
                     --max-error-rate).

Usage:
  python3 scripts/parity_check.py --since=24h
  python3 scripts/parity_check.py --since=30m --mode=zernio-only --max-error-rate=0.01

Requires:
  - gcloud CLI authenticated against the same project as the Cloud Run service
  - project id implicit from `gcloud config get-value project`

Exit codes:
  0  parity holds (or zernio-only error rate within bound)
  1  divergence detected / error rate exceeds bound
  2  no log entries in the window (likely shadow not deployed yet)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from typing import Iterable

SERVICE = "agents-sdk-api"
SHADOW_LOG_TAG = "publisher.shadow.diff"
PUBLISH_LOG_TAG = "publisher.publish"
DEFAULT_SINCE = "24h"


def parse_since(s: str) -> str:
    """Convert '24h' / '30m' / '15s' into the freshness format gcloud accepts."""
    m = re.fullmatch(r"(\d+)([smhd])", s.strip())
    if not m:
        sys.exit(f"Invalid --since {s!r} (use forms like 30m, 24h, 7d)")
    return f"{m.group(1)}{m.group(2)}"


def gcloud_logs(filter_expr: str, since: str, limit: int = 1000) -> list[dict]:
    cmd = [
        "gcloud",
        "logging",
        "read",
        filter_expr,
        f"--freshness={since}",
        f"--limit={limit}",
        "--format=json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"gcloud logging read failed: {proc.stderr[:400]}")
    try:
        return json.loads(proc.stdout or "[]")
    except json.JSONDecodeError as e:
        sys.exit(f"Cannot parse gcloud logging output: {e}")


def extract_payload(entry: dict) -> dict:
    """Cloud Logging entries put the JSON payload under jsonPayload."""
    return entry.get("jsonPayload") or {}


# ---------------------------------------------------------------------------
# Shadow parity (Late vs Zernio) — divergence detector
# ---------------------------------------------------------------------------

# Fields whose drift between Late and Zernio matters to downstream consumers.
# Other differences (timestamps, internal post ids) are expected.
CONTRACT_FIELDS = ("success", "status", "platform_post_id", "platform_post_url")


def analyze_shadow(entries: Iterable[dict]) -> tuple[int, int, Counter]:
    total = 0
    divergent = 0
    reasons: Counter = Counter()
    for e in entries:
        p = extract_payload(e)
        late = p.get("late") or {}
        zernio = p.get("zernio") or {}
        if not late and not zernio:
            continue
        total += 1
        for field in CONTRACT_FIELDS:
            lv = late.get(field)
            zv = zernio.get(field)
            if lv != zv:
                divergent += 1
                reasons[f"{field}: late={lv!r} zernio={zv!r}"] += 1
                break
    return total, divergent, reasons


def cmd_shadow(args: argparse.Namespace) -> int:
    since = parse_since(args.since)
    filter_expr = (
        f'resource.type="cloud_run_revision" '
        f'AND resource.labels.service_name="{SERVICE}" '
        f'AND jsonPayload.tag="{SHADOW_LOG_TAG}"'
    )
    print(f"[shadow] reading logs since={since}…")
    entries = gcloud_logs(filter_expr, since, limit=args.limit)
    if not entries:
        print(f"  no entries with tag={SHADOW_LOG_TAG!r} in the window.")
        print(f"  Is shadow mode deployed? See docs/ZERNIO-CUTOVER-RUNBOOK.md Stage 1.")
        return 2

    total, divergent, reasons = analyze_shadow(entries)
    print(f"  entries={total}  divergent={divergent}  "
          f"parity_rate={100 * (total - divergent) / total:.2f}%")
    if divergent:
        print("  Top divergence reasons:")
        for reason, count in reasons.most_common(5):
            print(f"    {count:5d}  {reason}")
        print()
        print("  ✗ Faz 6 merge ENGELLI — divergence sıfırlanmadan üretime almayın.")
        return 1
    print("  ✓ Faz 6 merge için parity garantisi sağlandı.")
    return 0


# ---------------------------------------------------------------------------
# Zernio-only (post-cutover canary) — error rate detector
# ---------------------------------------------------------------------------


def cmd_zernio_only(args: argparse.Namespace) -> int:
    since = parse_since(args.since)
    filter_expr = (
        f'resource.type="cloud_run_revision" '
        f'AND resource.labels.service_name="{SERVICE}" '
        f'AND jsonPayload.tag="{PUBLISH_LOG_TAG}" '
        f'AND jsonPayload.backend="zernio"'
    )
    print(f"[zernio-only] reading logs since={since}…")
    entries = gcloud_logs(filter_expr, since, limit=args.limit)
    if not entries:
        print(f"  no entries with tag={PUBLISH_LOG_TAG!r} backend=zernio in window.")
        return 2

    total = 0
    failed = 0
    for e in entries:
        p = extract_payload(e)
        total += 1
        if p.get("success") is False:
            failed += 1
    rate = failed / total if total else 0
    print(f"  entries={total}  failed={failed}  error_rate={rate * 100:.2f}%")
    if rate > args.max_error_rate:
        print(f"  ✗ Error rate {rate * 100:.2f}% > tolerable "
              f"{args.max_error_rate * 100:.2f}% — rollback gerekebilir.")
        return 1
    print(f"  ✓ Error rate {rate * 100:.2f}% kabul edilen sınırın altında.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--mode", choices=["shadow", "zernio-only"], default="shadow")
    p.add_argument("--since", default=DEFAULT_SINCE,
                   help="freshness (e.g. 30m, 24h, 7d). Default: 24h")
    p.add_argument("--limit", type=int, default=1000,
                   help="max log entries to pull. Default: 1000")
    p.add_argument("--max-error-rate", type=float, default=0.01,
                   help="zernio-only: tolerable error fraction. Default: 0.01 (1%%)")
    args = p.parse_args(argv)

    if args.mode == "shadow":
        return cmd_shadow(args)
    return cmd_zernio_only(args)


if __name__ == "__main__":
    raise SystemExit(main())
