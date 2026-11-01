#!/usr/bin/env python3
"""Rebuild the website (docs/index.html) from the survey data.

Pipeline
  1. parse source/main.tex and source/references.bib  (extract_papers)
     The manuscript sources are private (git-ignored). Without them the build
     uses the committed snapshots data/generated/tex_extraction.json and
     data/generated/bibliography.json, so CI keeps working.
  2. resolve data/papers.yaml against the bibliography (database)
  3. run consistency checks against the manuscript      (quality)
  4. build the comparison tables in memory              (generate_tables)
  5. generate the website docs/index.html               (generate_site, site_figures)

Usage
  python scripts/build.py            # rebuild
  python scripts/build.py --merge    # also append stubs for newly classified works
  python scripts/build.py --check    # do not write; exit 1 if outputs are stale
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (GENERATED, ROOT, SNAPSHOT_BIB, bib_duplicate_ids, bib_snapshot, dump_json,  # noqa: E402
                    load_bib, load_data, write_outputs)
import extract_papers  # noqa: E402
from database import resolve  # noqa: E402
from generate_tables import build_tables  # noqa: E402
from generate_site import site_outputs  # noqa: E402
from quality import all_findings  # noqa: E402


def collect_outputs(merge: bool = False):
    """Return (outputs, context) without writing anything except merges."""
    extraction = extract_papers.run(merge=merge, write=False)
    extraction.pop("merged_stubs", None)
    data = load_data()
    bib = load_bib()
    resolved = resolve(data, bib, extraction)
    findings = all_findings(data, bib, extraction, resolved, bib_duplicate_ids())
    outputs = {GENERATED / "tex_extraction.json": dump_json(extraction), SNAPSHOT_BIB: dump_json(bib_snapshot(bib, data))}
    tables = build_tables(data, resolved)
    outputs.update(site_outputs(data, resolved, tables, extraction))
    ctx = {"data": data, "bib": bib, "extraction": extraction, "resolved": resolved, "findings": findings, "tables": tables}
    return outputs, ctx


def stale_outputs(outputs) -> list[Path]:
    return [p for p, c in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != c]


def build(merge: bool = False, check: bool = False, only: list[str] | None = None, quiet: bool = False) -> int:
    outputs, ctx = collect_outputs(merge=merge)
    if only:
        keep = {"site": ("docs/index.html", "docs/comparison.html")}
        prefixes = []
        for o in only:
            v = keep[o]
            prefixes += [v] if isinstance(v, str) else list(v)
        outputs = {p: c for p, c in outputs.items() if str(p.relative_to(ROOT)).startswith(tuple(prefixes))}
    if check:
        stale = stale_outputs(outputs)
        for p in stale:
            print(f"STALE: {p.relative_to(ROOT)}")
        print("outputs up to date" if not stale else f"{len(stale)} stale output(s); run python scripts/build.py")
        return 1 if stale else 0
    written = write_outputs(outputs)
    if not quiet:
        sev = {s: sum(f.severity == s for f in ctx["findings"]) for s in ("error", "warning", "info")}
        print(f"papers: {len(ctx['resolved'])} | tables: {len(ctx['tables'])} | files generated: {len(outputs)} "
              f"| files changed: {len(written)}")
        print(f"findings: {sev['error']} errors, {sev['warning']} warnings, {sev['info']} info "
              "(python scripts/validate.py -v lists them)")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--merge", action="store_true", help="append stubs for works classified in the manuscript but missing from papers.yaml")
    ap.add_argument("--check", action="store_true", help="exit 1 if generated outputs are not up to date")
    a = ap.parse_args()
    sys.exit(build(merge=a.merge, check=a.check))


if __name__ == "__main__":
    main()
