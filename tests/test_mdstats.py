"""Tests for mdstats — Markdown repository statistics and link auditor CLI."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

import mdstats


@pytest.fixture
def tmp_markdown(tmp_path: Path) -> Path:
    """Create a small valid Markdown file in a temp directory."""
    doc = tmp_path / "doc.md"
    doc.write_text(
        """
# Title

Some words here.

## Section One

More words in this section.

### Subsection

Nested content.

## Section Two

Final words.

[external](https://example.com)
[local](other.md)
[broken](missing.md)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    # Create one of the linked files so one internal link is valid.
    (tmp_path / "other.md").write_text("# Other\n", encoding="utf-8")
    return doc


def test_scan_file_heading_counts(tmp_markdown: Path) -> None:
    report = mdstats.scan_file(tmp_markdown)
    headings = report["headings"]
    assert headings.get(1, 0) == 1
    assert headings.get(2, 0) == 2
    assert headings.get(3, 0) == 1
    assert headings.get(4, 0) == 0
    assert headings.get(5, 0) == 0
    assert headings.get(6, 0) == 0


def test_scan_file_word_count(tmp_markdown: Path) -> None:
    report = mdstats.scan_file(tmp_markdown)
    assert report["words"] > 0


def test_scan_file_external_link(tmp_markdown: Path) -> None:
    report = mdstats.scan_file(tmp_markdown)
    assert report["external_links"] == 1


def test_scan_file_broken_internal_link(tmp_markdown: Path) -> None:
    report = mdstats.scan_file(tmp_markdown)
    assert len(report["broken"]) == 1
    broken = report["broken"][0]
    assert broken["target"] == "missing.md"


def test_scan_file_valid_internal_link_not_broken(tmp_markdown: Path) -> None:
    report = mdstats.scan_file(tmp_markdown)
    targets = [b["target"] for b in report["broken"]]
    assert "other.md" not in targets


def test_scan_file_largest_section(tmp_markdown: Path) -> None:
    report = mdstats.scan_file(tmp_markdown)
    assert report["largest"]["heading"] == "Section One"


def test_build_report_aggregate(tmp_markdown: Path) -> None:
    report = mdstats.build_report([tmp_markdown])
    agg = report["aggregate"]
    assert agg["files_scanned"] == 1
    assert agg["total_words"] == report["files"][0]["words"]


def test_render_json_output_shape(tmp_markdown: Path) -> None:
    report = mdstats.build_report([tmp_markdown])
    raw = mdstats.render_json(report)
    data = json.loads(raw)
    assert "files" in data
    assert "aggregate" in data
    assert len(data["files"]) == 1
    assert set(data["files"][0].keys()) == {
        "path",
        "headings",
        "words",
        "external_links",
        "broken",
        "largest",
    }


def test_render_plain_contains_path(tmp_markdown: Path) -> None:
    report = mdstats.build_report([tmp_markdown])
    rendered = mdstats.render_plain(report)
    assert tmp_markdown.name in rendered
    assert "Words:" in rendered
    assert "Headings:" in rendered


def test_empty_file() -> None:
    with tempfile.NamedTemporaryFile(
        suffix=".md", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write("")
        path = Path(f.name)
    try:
        report = mdstats.scan_file(path)
        assert report["words"] == 0
        assert report["headings"] == {}
        assert report["external_links"] == 0
        assert report["broken"] == []
        assert report["largest"] == {}
    finally:
        path.unlink(missing_ok=True)


def test_no_headings_section_handling(tmp_path: Path) -> None:
    doc = tmp_path / "noh.md"
    doc.write_text("Just a paragraph of text.\nAnother line here.\n", encoding="utf-8")
    report = mdstats.scan_file(doc)
    assert report["headings"] == {}
    assert report["largest"] == {}


def test_case_insensitive_external_link_excluded(tmp_path: Path) -> None:
    """External URLs with mixed/upper case must NOT be counted as broken
    internal links."""
    doc = tmp_path / "case.md"
    doc.write_text(
        "[Mixed](HTTPS://Example.COM)\n[Upper](HTTP://EXAMPLE.COM)\n",
        encoding="utf-8",
    )
    report = mdstats.scan_file(doc)
    assert report["external_links"] == 2
    assert report["broken"] == []


def test_mailto_not_broken_internal_link(tmp_path: Path) -> None:
    doc = tmp_path / "mail.md"
    doc.write_text("[email](mailto:user@example.com)\n", encoding="utf-8")
    report = mdstats.scan_file(doc)
    assert report["external_links"] == 0
    assert report["broken"] == []


def test_blocked_non_file_uri_schemes_not_broken(tmp_path: Path) -> None:
    doc = tmp_path / "schemes.md"
    doc.write_text(
        "[tel](tel:+1234567890)\n[data](data:text/plain,hello)\n"
        "[js](javascript:alert(1))\n",
        encoding="utf-8",
    )
    report = mdstats.scan_file(doc)
    assert report["broken"] == []


def test_anchor_only_links_ignored(tmp_path: Path) -> None:
    doc = tmp_path / "anchors.md"
    doc.write_text(
        "[top](#top)\n[section](#section-name)\n",
        encoding="utf-8",
    )
    report = mdstats.scan_file(doc)
    assert report["external_links"] == 0
    assert report["broken"] == []


def test_main_help_exit_code() -> None:
    code = mdstats.main(["--help"])
    assert code == 0


def test_main_no_args_empty_stdin() -> None:
    code = mdstats.main([], stdin="")
    assert code == 1


def test_main_stdin_mode(tmp_path: Path) -> None:
    doc = tmp_path / "stdin.md"
    doc.write_text("# Hi\nWords here.\n", encoding="utf-8")
    code = mdstats.main([], stdin=doc.read_text(encoding="utf-8"))
    assert code == 0


def test_main_json_format(tmp_markdown: Path) -> None:
    code = mdstats.main(["--format", "json", str(tmp_markdown)])
    assert code == 0


def test_main_check_passes_when_no_broken(tmp_path: Path) -> None:
    doc = tmp_path / "clean.md"
    doc.write_text("# Clean\nNo broken links here.\n[valid](exists.md)\n", encoding="utf-8")
    (tmp_path / "exists.md").write_text("# Exists\n", encoding="utf-8")
    code = mdstats.main(["--check", str(doc)])
    assert code == 0


def test_main_check_fails_when_broken(tmp_path: Path) -> None:
    doc = tmp_path / "bad.md"
    doc.write_text("[gone](missing.md)\n", encoding="utf-8")
    code = mdstats.main(["--check", str(doc)])
    assert code == 1
