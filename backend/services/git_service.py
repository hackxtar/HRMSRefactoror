"""
Git integration service for the Refactoring Workbench.
Provides functions to interact with Git repos via subprocess.
"""

import subprocess
import os
from typing import Optional


def _run_git(repo_path: str, *args: str, timeout: int = 60) -> dict:
    """Run a git command and return structured result."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except FileNotFoundError:
        return {"success": False, "stdout": "", "stderr": "Git is not installed or not in PATH"}
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Git command timed out"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e)}


def is_git_repo(path: str) -> bool:
    """Check if a directory is a Git repository."""
    res = _run_git(path, "rev-parse", "--is-inside-work-tree")
    return res["success"] and res["stdout"] == "true"


def get_status(repo_path: str) -> dict:
    """Get Git repo status: branch, modified files, ahead/behind."""
    if not is_git_repo(repo_path):
        return {"is_repo": False, "error": "Not a git repository"}

    branch = _run_git(repo_path, "rev-parse", "--abbrev-ref", "HEAD")
    status = _run_git(repo_path, "status", "--porcelain")
    log_ahead = _run_git(repo_path, "rev-list", "--count", "@{u}..HEAD")
    log_behind = _run_git(repo_path, "rev-list", "--count", "HEAD..@{u}")

    modified_files = []
    if status["success"] and status["stdout"]:
        for line in status["stdout"].split("\n"):
            if line.strip():
                modified_files.append({
                    "status": line[:2].strip(),
                    "file": line[3:].strip()
                })

    return {
        "is_repo": True,
        "branch": branch["stdout"] if branch["success"] else "unknown",
        "modified_files": modified_files,
        "modified_count": len(modified_files),
        "ahead": int(log_ahead["stdout"]) if log_ahead["success"] and log_ahead["stdout"].isdigit() else 0,
        "behind": int(log_behind["stdout"]) if log_behind["success"] and log_behind["stdout"].isdigit() else 0,
    }


def pull(repo_path: str) -> dict:
    """Pull latest changes from remote."""
    if not is_git_repo(repo_path):
        return {"success": False, "message": "Not a git repository"}

    result = _run_git(repo_path, "pull", "--ff-only", timeout=120)

    return {
        "success": result["success"],
        "message": result["stdout"] if result["success"] else result["stderr"],
    }


def get_recent_commits(repo_path: str, count: int = 10) -> list:
    """Get recent commit log."""
    if not is_git_repo(repo_path):
        return []

    fmt = "%H|%an|%ae|%ai|%s"
    result = _run_git(repo_path, "log", f"--max-count={count}", f"--pretty=format:{fmt}")

    if not result["success"] or not result["stdout"]:
        return []

    commits = []
    for line in result["stdout"].split("\n"):
        parts = line.split("|", 4)
        if len(parts) == 5:
            commits.append({
                "hash": parts[0][:8],
                "author": parts[1],
                "email": parts[2],
                "date": parts[3],
                "message": parts[4],
            })
    return commits


def find_git_root(path: str) -> Optional[str]:
    """Find the root directory of the Git repo containing this path."""
    result = _run_git(path, "rev-parse", "--show-toplevel")
    if result["success"]:
        return result["stdout"]
    return None
