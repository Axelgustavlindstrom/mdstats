# mdstats — Markdown Repository Statistics and Link Auditor

`mdstats` reads one or more Markdown files and reports per-file and aggregate
statistics: headings (count and distribution by level), word count, external
link count, broken internal link check, and the largest section by word count.
It is a zero-runtime-dependency Python CLI suitable for CI gates, doc audits,
and repository health dashboards.

## Features

- **Per-file and aggregate statistics** over any number of Markdown files.
- **Heading distribution by level** — H1 through H6 counts in every report.
- **Word count** for every file and in aggregate.
- **External link count** — tracks `http://` / `https://` links only.
- **Broken internal link detection** — checks relative file links against the
  filesystem and reports the file, line, and target for each missing path.
- **Largest section** — identifies the heading whose body has the most words.
- **Two output formats** — human-readable `plain` (default) and machine-readable
  `json`.
- **CI-friendly `--check` mode** — exits `0` when no broken internal links are
  found, `1` when any are found.

## Installation

```bash
python -m pip install mdstats
```

For development:

```bash
git clone <repo>
cd mdstats
python -m pip install -e ".[dev]"
```

## Usage

Pass one or more Markdown files:

```bash
mdstats README.md docs/*.md
```

Read from stdin:

```bash
cat README.md | mdstats
```

JSON output:

```bash
mdstats --format json README.md
```

CI gate — fail when broken internal links are found:

```bash
mdstats --check docs/
echo $?
# 0 -> no broken links
# 1 -> broken links detected
```

### Options

| Flag | Description |
|------|-------------|
| `files` | One or more Markdown files to scan. If omitted, reads stdin. |
| `-f`, `--format` | Output format: `plain` (default) or `json`. |
| `--check` | Exit 0 when no broken links, 1 when any are found. |
| `-h`, `--help` | Show help message. |

## Example output (plain)

```
## README.md
Headings: 12
  H1: 2, H2: 5, H3: 3, H4: 1, H5: 0, H6: 1
Words: 4523
External links: 8
Broken internal links: 0
Largest section: "Getting Started" (342 words)

## docs/guide.md
Headings: 8
  H1: 1, H2: 4, H3: 2, H4: 0, H5: 0, H6: 1
Words: 2100
External links: 3
Broken internal links: 2
  line 47: ../missing.md
  line 82: old-guide.md
Largest section: "Configuration" (198 words)

## Aggregate
Files scanned: 2
Total headings: 20
Total words: 6623
Total external links: 11
Total broken internal links: 2
```

## Project structure

```
mdstats/
├── pyproject.toml      # Package metadata and deps
├── mdstats.py          # CLI implementation (flat single module)
├── README.md           # This file
├── .gitignore
└── tests/
    └── test_mdstats.py # pytest suite
```

## Repository

GitHub: https://github.com/Axelgustavlindstrom/mdstats

## Tags

`markdown`, `statistics`, `link-auditor`, `cli`, `docs`, `ci`, `python`
