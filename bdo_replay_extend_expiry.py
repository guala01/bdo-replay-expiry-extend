#!/usr/bin/env python3
"""Extend the local expiry timestamp in a downloaded BDO Solare replay."""

from __future__ import annotations

import argparse
import shutil
import struct
import time
from datetime import datetime, timezone
from pathlib import Path


ONE_WEEK_SECONDS = 7 * 24 * 60 * 60


def utc_text(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def find_expiry_pair(data: bytes) -> tuple[int, int, int]:
    candidates: list[tuple[int, int, int]] = []
    now = int(time.time())
    plausible_start = now - 5 * 365 * 24 * 60 * 60
    plausible_end = now + 5 * 365 * 24 * 60 * 60

    for offset in range(4, len(data) - 15):
        recorded_at, expires_at = struct.unpack_from("<QQ", data, offset)
        if (
            expires_at - recorded_at == ONE_WEEK_SECONDS
            and plausible_start <= recorded_at <= plausible_end
        ):
            candidates.append((offset, recorded_at, expires_at))

    if len(candidates) != 1:
        raise ValueError(
            f"expected one recorded/expiry timestamp pair, found {len(candidates)}"
        )
    return candidates[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay_folder", type=Path)
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Days from now before the replay expires (default: 365).",
    )
    args = parser.parse_args()

    if args.days < 1:
        parser.error("--days must be at least 1")

    replay_folder = args.replay_folder.resolve()
    info_path = replay_folder / "instanceInfo.txt"
    if not info_path.is_file():
        parser.error(f"instanceInfo.txt not found in {replay_folder}")

    original = info_path.read_bytes()
    if not original.startswith(b"PABR"):
        parser.error(f"{info_path} is not a plain PABR file")

    offset, recorded_at, old_expiry = find_expiry_pair(original)
    new_expiry = int(time.time()) + args.days * 24 * 60 * 60

    backup_path = info_path.with_name("instanceInfo.txt.expiry-backup")
    if not backup_path.exists():
        shutil.copy2(info_path, backup_path)

    updated = bytearray(original)
    struct.pack_into("<Q", updated, offset + 8, new_expiry)
    info_path.write_bytes(updated)

    changed = [index for index, pair in enumerate(zip(original, updated)) if pair[0] != pair[1]]
    if not changed or any(index < offset + 8 or index >= offset + 16 for index in changed):
        raise RuntimeError("unexpected bytes changed while patching expiry")

    print(f"Replay: {replay_folder.name}")
    print(f"Recorded: {utc_text(recorded_at)}")
    print(f"Old expiry: {utc_text(old_expiry)}")
    print(f"New expiry: {utc_text(new_expiry)}")
    print(f"Expiry offset: 0x{offset + 8:x}")
    print(f"Changed bytes: {len(changed)}")
    print(f"Backup: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
