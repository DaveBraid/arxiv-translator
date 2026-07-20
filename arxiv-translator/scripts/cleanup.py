#!/usr/bin/env python3
"""
Remove temporary files for one paper.
Usage: python cleanup.py <base_dir>

Removes <base_dir>/.tmp_arxiv, a managed LOCAL_WORK_DIR recorded in
download.env, download.env itself, and inspect_*.txt files.
Call this only after all papers have been compiled.
"""
import os
import re
import shlex
import shutil
import sys
import tempfile


INSPECT_OUTPUT_RE = re.compile(r"^inspect_.*\.txt$")
DOWNLOAD_ENV = "download.env"
LOCAL_WORK_MARKER = ".arxiv-translator-local-work"


def read_download_env(base_dir):
    env_path = os.path.join(base_dir, DOWNLOAD_ENV)
    values = {}
    if not os.path.isfile(env_path):
        return values
    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = shlex.split(line, posix=True)
            if len(parts) == 1 and "=" in parts[0]:
                key, value = parts[0].split("=", 1)
                values[key] = value
    return values


def remove_local_work_dir(path):
    if not path:
        return False
    target = os.path.realpath(os.path.abspath(os.path.expanduser(path)))
    temp_root = os.path.realpath(tempfile.gettempdir())
    try:
        inside_temp = os.path.commonpath((target, temp_root)) == temp_root
    except ValueError:
        inside_temp = False
    marker = os.path.join(target, LOCAL_WORK_MARKER)
    if not inside_temp or not os.path.isfile(marker):
        print(f"Skipped unmanaged LOCAL_WORK_DIR: {target}", file=sys.stderr)
        return False
    shutil.rmtree(target)
    print(f"✅ Removed: {target}")
    return True


def remove_inspect_outputs(base_dir):
    removed = []
    for entry in os.listdir(base_dir):
        path = os.path.join(base_dir, entry)
        if not os.path.isfile(path):
            continue
        if not INSPECT_OUTPUT_RE.fullmatch(entry):
            continue
        os.remove(path)
        removed.append(path)
    return removed


def cleanup(base_dir):
    base_dir = os.path.abspath(base_dir)
    env_path = os.path.join(base_dir, DOWNLOAD_ENV)
    env_values = read_download_env(base_dir)
    target = os.path.join(base_dir, ".tmp_arxiv")
    if os.path.exists(target):
        shutil.rmtree(target)
        print(f"✅ Removed: {target}")
    else:
        print(f"Nothing to remove: {target}")

    removed_outputs = remove_inspect_outputs(base_dir)
    if removed_outputs:
        for path in removed_outputs:
            print(f"✅ Removed: {path}")
    else:
        print(f"Nothing to remove: {base_dir}/inspect_*.txt")

    local_work_dir = env_values.get("LOCAL_WORK_DIR")
    local_removed = remove_local_work_dir(local_work_dir)
    local_cleanup_complete = (
        not local_work_dir
        or local_removed
        or not os.path.exists(os.path.abspath(os.path.expanduser(local_work_dir)))
    )
    if local_cleanup_complete and os.path.isfile(env_path):
        os.remove(env_path)
        print(f"✅ Removed: {env_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python cleanup.py <base_dir>", file=sys.stderr)
        sys.exit(2)
    cleanup(sys.argv[1])
