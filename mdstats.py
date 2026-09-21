"""mdstats — Markdown repository statistics and link auditor CLI.

Reads one or more Markdown files and reports per-file and aggregate
statistics: headings (count and distribution by level), word count, external
link count, broken internal link check, and the largest section by word count.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

# Matches Markdown headings: leading # count, optional trailing whitespace.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")

# Matches Markdown links: [text](target)
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

# Matches URLs with a scheme (external links). Case-insensitive.
_EXTERNAL_RE = re.compile(r"https?://", re.IGNORECASE)

# Matches common URI schemes that should not be treated as relative file links.
_URI_SCHEME_RE = re.compile(
    r"^(?:mailto|tel|data|javascript|file|ftp|sftp|ssh|ws|wss):",
    re.IGNORECASE,
)


def _collect_links(text: str) -> list[tuple[int, str]]:
    """Return list of (line_number, target) for every link in `text`.

    Lines are 1-indexed.
    """
    links: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for _text, target in _LINK_RE.findall(line):
            links.append((lineno, target.strip()))
    return links


def _is_external(target: str) -> bool:
    return bool(_EXTERNAL_RE.match(target))


def _is_relative_file_link(target: str) -> bool:
    """Return True if target looks like a relative file path (no scheme, not
    an anchor-only or absolute URL, and not a non-file URI scheme)."""
    if _EXTERNAL_RE.match(target):
        return False
    if target.startswith("/"):
        return False
    if not target or target.startswith("#"):
        return False
    if _URI_SCHEME_RE.match(target):
        return False
    return True


def _resolve_internal_target(link_target: str, source_dir: Path) -> Path:
    """Resolve a relative link target against `source_dir`, stripping hashes
    and query strings for filesystem existence checks."""
    path_part = link_target.split("#", 1)[0].split("?", 1)[0]
    return (source_dir / path_part).resolve()


def scan_file(path: Path) -> dict[str, Any]:
    """Scan a single Markdown file and return a structured report.

    Raises FileNotFoundError if the path does not exist.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    heading_levels: Counter[int] = Counter()
    heading_texts: list[str] = []
    words = 0
    section_words: list[tuple[str, int]] = []
    external_links: list[tuple[int, str]] = []
    internal_links: list[tuple[int, str]] = []
    current_heading: str | None = None
    current_section_word_count = 0

    for lineno, line in enumerate(lines, start=1):
        # Headings
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            heading_levels[level] += 1
            heading_text = m.group(2).strip()
            # Close previous section
            if current_heading is not None:
                section_words.append((current_heading, current_section_word_count))
            current_heading = heading_text
            current_section_word_count = 0
            heading_texts.append(heading_text)
            continue

        # Words
        words += len(line.split())

        # Section body word accumulation
        if current_heading is not None:
            current_section_word_count += len(line.split())

        # Links
        for _t, target in _LINK_RE.findall(line):
            target = target.strip()
            if _is_external(target):
                external_links.append((lineno, target))
            elif _is_relative_file_link(target):
                internal_links.append((lineno, target))

    # Close final section
    if current_heading is not None:
        section_words.append((current_heading, current_section_word_count))

    # Broken internal link check
    broken: list[dict[str, Any]] = []
    for lineno, target in internal_links:
        resolved = _resolve_internal_target(target, path.parent)
        if not resolved.exists():
            broken.append(
                {
                    "line": lineno,
                    "target": target,
                    "resolved": str(resolved),
                }
            )

    # Largest section
    largest: dict[str, Any] = {}
    if section_words:
        name, count = max(section_words, key=lambda x: x[1])
        largest = {"heading": name, "words": count}

    return {
        "path": str(path),
        "headings": dict(heading_levels),
        "words": words,
        "external_links": len(external_links),
        "internal_links": len(internal_links),
        "broken": broken,
        "largest": largest,
        "heading_texts": heading_texts,
    }


def _heading_distribution(headings: dict[int, int]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for level in range(1, 7):
        dist[f"H{level}"] = headings.get(level, 0)
    return dist


def build_report(paths: Sequence[Path], stdin_text: str | None = None) -> dict[str, Any]:
    """Build a report from the given file paths."""
    files: list[dict[str, Any]] = []
    for p in paths:
        files.append(scan_file(p))

    aggregate: dict[str, Any] = {
        "files_scanned": len(files),
        "total_headings": 0,
        "total_words": 0,
        "total_external_links": 0,
        "total_broken_internal_links": 0,
        "heading_distribution": _heading_distribution({}),
    }

    agg_headings: Counter[int] = Counter()
    for f in files:
        aggregate["total_headings"] += sum(f["headings"].values())
        aggregate["total_words"] += f["words"]
        aggregate["total_external_links"] += f["external_links"]
        aggregate["total_broken_internal_links"] += len(f["broken"])
        for level, count in f["headings"].items():
            agg_headings[level] += count
    aggregate["heading_distribution"] = _heading_distribution(dict(agg_headings))

    return {
        "files": files,
        "aggregate": aggregate,
    }


def render_plain(report: dict[str, Any]) -> str:
    """Render a report as plain text."""
    parts: list[str] = []
    for f in report["files"]:
        parts.append(f"## {f['path']}")
        headings = _heading_distribution(f["headings"])
        parts.append(
            "Headings: {} (H1: {}, H2: {}, H3: {}, H4: {}, H5: {}, H6: {})".format(
                sum(headings.values()),
                headings["H1"],
                headings["H2"],
                headings["H3"],
                headings["H4"],
                headings["H5"],
                headings["H6"],
            )
        )
        parts.append(f"Words: {f['words']}")
        parts.append(f"External links: {f['external_links']}")
        parts.append(f"Broken internal links: {len(f['broken'])}")
        for b in f["broken"]:
            parts.append(f"  line {b['line']}: {b['target']}")
        if f["largest"]:
            parts.append(
                f"Largest section: {f['largest']['heading']!r} ({f['largest']['words']} words)"
            )
        parts.append("")
    agg = report["aggregate"]
    parts.append("## Aggregate")
    parts.append(f"Files scanned: {agg['files_scanned']}")
    parts.append(f"Total headings: {agg['total_headings']}")
    parts.append(f"Total words: {agg['total_words']}")
    parts.append(f"Total external links: {agg['total_external_links']}")
    parts.append(f"Total broken internal links: {agg['total_broken_internal_links']}")
    return "\n".join(parts)


def render_json(report: dict[str, Any]) -> str:
    """Render a report as JSON."""
    out: dict[str, Any] = {"files": [], "aggregate": report["aggregate"]}
    for f in report["files"]:
        out["files"].append(
            {
                "path": f["path"],
                "headings": _heading_distribution(f["headings"]),
                "words": f["words"],
                "external_links": f["external_links"],
                "broken": f["broken"],
                "largest": f["largest"],
            }
        )
    return json.dumps(out, indent=2)


def main(argv: Sequence[str] | None = None, stdin: str | None = None) -> int:
    """CLI entrypoint. Returns exit code (0 success, 1 bad links when --check)."""
    parser = argparse.ArgumentParser(
        prog="mdstats",
        description="Markdown repository statistics and link auditor.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Markdown files to scan. If omitted, reads stdin.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["plain", "json"],
        default="plain",
        help="Output format (default: plain).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 0 when no broken internal links, 1 otherwise.",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        # Let --help and usage errors propagate by returning the code.
        return e.code if isinstance(e.code, int) else 2

    files: list[Path] = []
    stdin_text: str | None = stdin

    if args.files:
        for p in args.files:
            files.append(Path(p).expanduser().resolve())
    else:
        # No files given: try stdin
        if stdin_text is None:
            stdin_text_bytes = sys.stdin.read()
            stdin_text = stdin_text_bytes
        if stdin_text:
            # Write stdin to a temp file so scan_file can resolve relative
            # links against it. Use a temp file under /tmp.
            import tempfile

            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False, encoding="utf-8"
            )
            try:
                tmp.write(stdin_text)
                tmp.flush()
                tmp_path = Path(tmp.name)
                files.append(tmp_path)
            except BaseException:
                tmp.close()
                raise
        else:
            print("mdstats: no input provided", file=sys.stderr)
            return 1

    report = build_report(files)
    rendered: str
    if args.format == "json":
        rendered = render_json(report)
    else:
        rendered = render_plain(report)

    has_broken = any(len(f["broken"]) for f in report["files"])
    if args.check and has_broken:
        # Still emit output before exiting so the user can see what broke.
        sys.stdout.write(rendered)
        return 1

    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
