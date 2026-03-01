"""
RFC-routable filesystem operations for the text_editor plugin.

These functions run inside the Docker container when invoked via
runtime.call_development_function. They use only stdlib — no
framework dependencies (no tiktoken, no agent context, etc.).

All args and return values must be JSON-serializable.
"""

import os
import shutil
import tempfile

_BINARY_PEEK = 8192


# ------------------------------------------------------------------
# Internal
# ------------------------------------------------------------------

def _count_content_lines(content: str) -> int:
    return content.count("\n") + (
        1 if content and not content.endswith("\n") else 0
    )


# ------------------------------------------------------------------
# Binary detection
# ------------------------------------------------------------------

def is_binary_impl(path: str) -> bool:
    """Check for null bytes in the first 8 KiB."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(_BINARY_PEEK)
        return b"\x00" in chunk
    except OSError:
        return False


# ------------------------------------------------------------------
# Read
# ------------------------------------------------------------------

def read_file_raw_impl(path: str) -> dict:
    """
    Read a text file and return raw lines plus metadata.

    Returns dict with:
      - lines: list[str] (raw lines including newlines)
      - total_lines: int
      - error: str (empty on success)
    """
    path = os.path.expanduser(path)

    if not os.path.isfile(path):
        return {"lines": [], "total_lines": 0, "error": "file not found"}

    # Binary check inline to avoid extra RFC round-trip
    try:
        with open(path, "rb") as f:
            chunk = f.read(_BINARY_PEEK)
        if b"\x00" in chunk:
            return {"lines": [], "total_lines": 0,
                    "error": "file appears binary, use terminal instead"}
    except OSError:
        pass

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except OSError as exc:
        return {"lines": [], "total_lines": 0, "error": str(exc)}

    return {"lines": all_lines, "total_lines": len(all_lines), "error": ""}


# ------------------------------------------------------------------
# Write
# ------------------------------------------------------------------

def write_file_impl(path: str, content: str) -> dict:
    """
    Write content to a file, creating parent dirs as needed.

    Returns dict with:
      - total_lines: int
      - error: str (empty on success)
    """
    path = os.path.expanduser(path)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        return {"total_lines": 0, "error": str(exc)}

    total = content.count("\n") + (
        1 if content and not content.endswith("\n") else 0
    )
    return {"total_lines": total, "error": ""}


# ------------------------------------------------------------------
# Patch
# ------------------------------------------------------------------

def apply_patch_impl(path: str, edits: list) -> dict:
    """
    Apply sorted, validated edits to a file.

    Returns dict with:
      - total_lines: int
      - error: str (empty on success)
    """
    path = os.path.expanduser(path)

    # Ensure content always ends with newline to prevent line merging
    for e in edits:
        if e["content"] and not e["content"].endswith("\n"):
            e["content"] += "\n"

    dir_name = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with (
            open(path, "r", encoding="utf-8", errors="replace") as src,
            os.fdopen(fd, "w", encoding="utf-8") as dst,
        ):
            edit_idx = 0
            line_no = 1
            total_written = 0

            for raw_line in src:
                while (
                    edit_idx < len(edits)
                    and edits[edit_idx]["insert"]
                    and edits[edit_idx]["from"] == line_no
                ):
                    edit = edits[edit_idx]
                    if edit["content"]:
                        dst.write(edit["content"])
                        total_written += _count_content_lines(edit["content"])
                    edit_idx += 1

                if edit_idx < len(edits) and not edits[edit_idx]["insert"]:
                    edit = edits[edit_idx]
                    if edit["from"] <= line_no <= edit["to"]:
                        if line_no == edit["from"] and edit["content"]:
                            dst.write(edit["content"])
                            total_written += _count_content_lines(
                                edit["content"]
                            )
                        if line_no == edit["to"]:
                            edit_idx += 1
                        line_no += 1
                        continue

                dst.write(raw_line)
                total_written += 1
                line_no += 1

            while edit_idx < len(edits):
                edit = edits[edit_idx]
                if edit["content"]:
                    dst.write(edit["content"])
                    total_written += _count_content_lines(edit["content"])
                edit_idx += 1

        shutil.move(tmp_path, path)
        return {"total_lines": total_written, "error": ""}
    except Exception as exc:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return {"total_lines": 0, "error": str(exc)}


# ------------------------------------------------------------------
# File info
# ------------------------------------------------------------------

def file_info_impl(path: str) -> dict:
    """
    Return file metadata needed by the host for mtime tracking.

    Returns dict with:
      - exists: bool
      - is_file: bool
      - realpath: str
      - expanded: str  (expanduser result)
      - mtime: float | None
    """
    path = os.path.expanduser(path)
    rp = os.path.realpath(path)
    exists = os.path.exists(path)
    is_file = os.path.isfile(path)
    mtime = None
    if exists:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            pass
    return {
        "exists": exists,
        "is_file": is_file,
        "realpath": rp,
        "expanded": path,
        "mtime": mtime,
    }
