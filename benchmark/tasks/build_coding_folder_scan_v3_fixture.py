#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SECONDS_PER_DAY = 86400


@dataclass(frozen=True)
class FileSpec:
    relative_path: str
    size_bytes: int
    modified_days_ago: int


def write_bytes_file(path: Path, size_bytes: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    chunk = b"x" * 4096
    remaining = size_bytes
    with path.open("wb") as handle:
        while remaining > 0:
            take = min(len(chunk), remaining)
            handle.write(chunk[:take])
            remaining -= take


def set_file_mtime(path: Path, modified_days_ago: int) -> None:
    now = int(time.time())
    ts = now - (modified_days_ago * SECONDS_PER_DAY)
    os.utime(path, (ts, ts))


def build_file_specs() -> list[FileSpec]:
    specs: list[FileSpec] = []

    recent_day_pattern = [0, 1, 2, 3, 4, 5, 6]
    old_day_pattern = [10, 12, 15, 18, 21, 25, 30, 35]

    extension_blocks: list[tuple[str, list[int], str]] = [
        ("txt", [420, 780, 950, 1200, 1600, 2400, 3200, 4800], "docs/readme"),
        ("md", [610, 890, 1400, 2100, 2800, 3600], "docs/note"),
        ("csv", [1024, 1536, 2048, 3072, 4096, 6144, 8192, 12288], "data/table"),
        ("json", [700, 1200, 2200, 3400, 5100], "data/blob"),
        ("log", [5000, 7200, 11000, 18000, 25000], "logs/app"),
        ("bin", [65536, 131072, 262144], "bin/blob"),
        ("jpg", [24576, 36864, 49152], "images/pic"),
    ]

    idx = 0
    for ext, sizes, stem in extension_blocks:
        for block_index, size in enumerate(sizes, start=1):
            repeat = 4 if ext in {"txt", "csv", "log"} else 3
            for repeat_index in range(1, repeat + 1):
                subdir = f"set_{(idx % 8) + 1}/branch_{((idx // 2) % 6) + 1}"
                rel = f"{subdir}/{stem}_{block_index:02d}_{repeat_index:02d}.{ext}"
                if idx % 3 == 0:
                    days = recent_day_pattern[idx % len(recent_day_pattern)]
                else:
                    days = old_day_pattern[idx % len(old_day_pattern)]
                specs.append(FileSpec(rel, size + (repeat_index - 1) * 11, days))
                idx += 1

    duplicate_sizes = [7777, 16000, 33333, 65555, 88888, 120000]
    for group_index, dup_size in enumerate(duplicate_sizes, start=1):
        for member_index in range(1, 4):
            rel = f"duplicates/group_{group_index}/dup_{member_index}.dat"
            days = recent_day_pattern[(group_index + member_index) % len(recent_day_pattern)]
            specs.append(FileSpec(rel, dup_size, days))

    largest_block = [
        ("archives/big_a.bin", 1_300_000, 2),
        ("archives/big_b.bin", 980_000, 12),
        ("archives/big_c.bin", 760_000, 4),
        ("archives/big_d.bin", 540_000, 20),
        ("archives/big_e.bin", 350_000, 1),
    ]
    for rel, size, days in largest_block:
        specs.append(FileSpec(rel, size, days))

    return specs


def size_bucket_label(size_bytes: int) -> str:
    if size_bytes <= 1024:
        return "0-1KB"
    if size_bytes <= 10 * 1024:
        return "1-10KB"
    if size_bytes <= 100 * 1024:
        return "10-100KB"
    if size_bytes <= 1024 * 1024:
        return "100KB-1MB"
    return ">1MB"


def extension_of(path_str: str) -> str:
    suffix = Path(path_str).suffix.lower()
    return suffix if suffix else "[no_ext]"


def build_fixture(root_dir: Path) -> dict[str, Any]:
    if root_dir.exists():
        shutil.rmtree(root_dir)
    root_dir.mkdir(parents=True, exist_ok=True)

    specs = build_file_specs()

    total_size = 0
    recent_files: list[str] = []
    ext_counts: dict[str, int] = {}
    size_buckets: dict[str, int] = {
        "0-1KB": 0,
        "1-10KB": 0,
        "10-100KB": 0,
        "100KB-1MB": 0,
        ">1MB": 0,
    }
    size_groups: dict[int, list[str]] = {}
    direct_dir_file_counts: dict[str, int] = {}
    direct_dir_total_sizes: dict[str, int] = {}

    for spec in specs:
        full_path = root_dir / spec.relative_path
        write_bytes_file(full_path, spec.size_bytes)
        set_file_mtime(full_path, spec.modified_days_ago)

        rel_path = spec.relative_path.replace("\\", "/")
        total_size += spec.size_bytes

        if spec.modified_days_ago <= 6:
            recent_files.append(rel_path)

        ext = extension_of(rel_path)
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
        size_buckets[size_bucket_label(spec.size_bytes)] += 1
        size_groups.setdefault(spec.size_bytes, []).append(rel_path)

        parent = Path(rel_path).parent
        parent_key = "." if str(parent) in {"", "."} else str(parent).replace("\\", "/")
        direct_dir_file_counts[parent_key] = direct_dir_file_counts.get(parent_key, 0) + 1
        direct_dir_total_sizes[parent_key] = direct_dir_total_sizes.get(parent_key, 0) + spec.size_bytes

    all_dirs = [p for p in root_dir.rglob("*") if p.is_dir()]
    total_directories_including_root = len(all_dirs) + 1
    total_files = len(specs)

    extension_distribution = sorted(
        ext_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )

    largest_files = sorted(
        [(spec.relative_path.replace("\\", "/"), spec.size_bytes) for spec in specs],
        key=lambda item: (-item[1], item[0]),
    )[:20]

    top_directories_by_file_count = sorted(
        direct_dir_file_counts.items(),
        key=lambda item: (-item[1], item[0]),
    )[:10]

    top_directories_by_total_size = sorted(
        direct_dir_total_sizes.items(),
        key=lambda item: (-item[1], item[0]),
    )[:10]

    duplicate_size_groups = sorted(
        [
            {"size_bytes": size, "paths": sorted(paths)}
            for size, paths in size_groups.items()
            if len(paths) >= 2
        ],
        key=lambda item: (-len(item["paths"]), -item["size_bytes"], item["paths"][0]),
    )[:10]

    checksum_mod_1m = total_size % 1_000_000

    fixture = {
        "fixture_version": "coding_folder_scan_v3_fixture_v2",
        "root_path": str(root_dir),
        "total_files": total_files,
        "total_directories_including_root": total_directories_including_root,
        "total_size_bytes": total_size,
        "extension_distribution": [
            {"extension": ext, "count": count}
            for ext, count in extension_distribution
        ],
        "size_distribution": size_buckets,
        "largest_files": [
            {"path": rel_path, "size_bytes": size}
            for rel_path, size in largest_files
        ],
        "top_directories_by_file_count": [
            {"path": path, "file_count": count}
            for path, count in top_directories_by_file_count
        ],
        "top_directories_by_total_size": [
            {"path": path, "total_size_bytes": size}
            for path, size in top_directories_by_total_size
        ],
        "recent_files": sorted(recent_files),
        "duplicate_size_groups": duplicate_size_groups,
        "checksum_mod_1m": checksum_mod_1m,
        "generation_notes": {
            "recent_file_rule_days": 7,
            "directory_stats_mode": "direct_only_non_recursive",
            "duplicate_group_count_total": len([1 for paths in size_groups.values() if len(paths) >= 2]),
            "size_bucket_labels": list(size_buckets.keys()),
        },
    }
    return fixture


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic fixture for coding_folder_scan_v3_measurement."
    )
    parser.add_argument(
        "--root-dir",
        required=True,
        help="Directory where the synthetic fixture tree will be created.",
    )
    parser.add_argument(
        "--out-json",
        required=True,
        help="Path to write the computed ground-truth fixture JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root_dir = Path(args.root_dir).expanduser().resolve()
    out_json = Path(args.out_json).expanduser().resolve()

    fixture = build_fixture(root_dir)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "success": True,
        "fixture_root": str(root_dir),
        "ground_truth_json": str(out_json),
        "total_files": fixture["total_files"],
        "total_directories_including_root": fixture["total_directories_including_root"],
        "total_size_bytes": fixture["total_size_bytes"],
        "checksum_mod_1m": fixture["checksum_mod_1m"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
