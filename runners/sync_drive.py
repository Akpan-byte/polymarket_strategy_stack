"""Sync results and docs to Google Drive via rclone."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

RCLONE = (
    shutil.which("rclone")
    or os.path.expanduser("~/.local/bin/rclone")
    or "/config/.local/bin/rclone"
)
REMOTE = "polybacktest"


def sync(local_dir: str, remote_subdir: str, dry_run: bool = False):
    src = Path(local_dir).resolve()
    dst = f"{REMOTE}:{remote_subdir}"
    cmd = [RCLONE, "sync", "--transfers", "8", "--checkers", "16"]
    if dry_run:
        cmd.append("--dry-run")
    cmd.extend([str(src), dst])
    print(" ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="results")
    parser.add_argument("--docs", default="docs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ok = True
    ok &= sync(args.results, "results", args.dry_run)
    ok &= sync(args.docs, "docs", args.dry_run)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
