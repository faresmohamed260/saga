#!/usr/bin/env python3
"""Run one benchmark command while sampling aggregate process-tree RSS.

Dedicated benchmark helper only. This keeps runtime resource evidence outside
production provider contracts while still measuring nested subprocesses.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import psutil


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata-out", required=True)
    parser.add_argument("--sample-interval-ms", type=int, default=50)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("benchmark command is required after --")
    if args.sample_interval_ms < 10 or args.sample_interval_ms > 5000:
        parser.error("--sample-interval-ms must be between 10 and 5000")
    return args


def tree_rss_bytes(root: psutil.Process) -> int:
    processes = [root]
    try:
        processes.extend(root.children(recursive=True))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    total = 0
    for process in processes:
        try:
            total += process.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return total


def main() -> int:
    args = parse_args()
    metadata_out = Path(args.metadata_out).resolve()
    metadata_out.parent.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    process = psutil.Popen(args.command, stdout=None, stderr=None)
    peak_tree_rss_bytes = 0
    sample_count = 0
    interval = args.sample_interval_ms / 1000.0

    while True:
        peak_tree_rss_bytes = max(peak_tree_rss_bytes, tree_rss_bytes(process))
        sample_count += 1
        code = process.poll()
        if code is not None:
            break
        time.sleep(interval)

    duration = time.perf_counter() - started
    metadata = {
        "schemaVersion": "saga-process-tree-measurement-v1",
        "wallClockSeconds": duration,
        "peakProcessTreeRssBytes": peak_tree_rss_bytes,
        "peakProcessTreeRssMiB": peak_tree_rss_bytes / (1024 * 1024),
        "sampleIntervalMs": args.sample_interval_ms,
        "sampleCount": sample_count,
        "exitCode": process.returncode,
    }
    metadata_out.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return int(process.returncode or 0)


if __name__ == "__main__":
    raise SystemExit(main())
