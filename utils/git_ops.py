import subprocess
import os
from pathlib import Path
from typing import Optional


def get_changed_files(repo_path: str, base_branch: str = "main") -> list[str]:
    result = subprocess.run(
        ["git", "-C", repo_path, "diff", "--name-only", f"origin/{base_branch}...HEAD"],
        capture_output=True, text=True,
    )
    return [f.strip() for f in result.stdout.split("\n") if f.strip()]


def get_file_diff(repo_path: str, file_path: str, base_branch: str = "main") -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, "diff", f"origin/{base_branch}...HEAD", "--", file_path],
        capture_output=True, text=True,
    )
    return result.stdout


def get_unified_diff(repo_path: str, base_branch: str = "main") -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, "diff", f"origin/{base_branch}...HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout


def get_unstaged_diff(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, "diff"],
        capture_output=True, text=True,
    )
    return result.stdout


def get_staged_diff(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, "diff", "--cached"],
        capture_output=True, text=True,
    )
    return result.stdout


def parse_diff_to_lines(diff_text: str) -> list[dict]:
    lines = []
    current_file = ""
    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            current_file = line.split(" b/")[-1] if " b/" in line else ""
            continue
        if line.startswith("@@ "):
            m = __import__("re").match(r'@@ -(\d+),?\d* \+(\d+),?\d* @@', line)
            if m:
                old_start, new_start = int(m.group(1)), int(m.group(2))
            else:
                old_start = new_start = 0
            continue
        if line.startswith("--- ") or line.startswith("+++ "):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            lines.append({"type": "added", "content": line[1:], "file": current_file, "new_line": new_start})
            new_start += 1
        elif line.startswith("-") and not line.startswith("---"):
            lines.append({"type": "removed", "content": line[1:], "file": current_file, "old_line": old_start})
            old_start += 1
        else:
            if old_start:
                old_start += 1
            if new_start:
                new_start += 1
    return lines


def apply_patch(repo_path: str, patch_content: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "apply", "--check"],
            input=patch_content, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return False
        result = subprocess.run(
            ["git", "-C", repo_path, "apply"],
            input=patch_content, capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_current_branch(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def get_file_content(repo_path: str, file_path: str, ref: str = "HEAD") -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "show", f"{ref}:{file_path}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass
    return None
