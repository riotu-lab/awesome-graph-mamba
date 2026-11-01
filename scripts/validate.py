#!/usr/bin/env python3
"""Validate the paper database and generated outputs.

Checks
  * JSON-schema conformance of data/papers.yaml (mandatory fields, enums)
  * duplicate keys (YAML level, database level, BibTeX level)
  * every database key exists in references.bib and is cited in main.tex
  * category values exist in data/taxonomy.yaml
  * curated D1--D4 and design-pattern labels match the manuscript tables
  * every work classified in a manuscript table is in the database
  * consistency of auxiliary files (benchmarks, results, challenges)
  * the generated website (docs/) is up to date

Exit status 1 if any error is found. ``--strict`` also fails on warnings.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DuplicateKeyError, ROOT  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--verbose", "-v", action="store_true", help="print informational findings too")
    args = ap.parse_args()
    try:
        from build import collect_outputs, stale_outputs
        outputs, ctx = collect_outputs()
    except DuplicateKeyError as exc:
        print(f"ERROR duplicate-yaml-key: {exc}")
        return 1
    findings = ctx["findings"]
    stale = stale_outputs(outputs)
    n_err = sum(f.severity == "error" for f in findings) + len(stale)
    n_warn = sum(f.severity == "warning" for f in findings)
    for f in findings:
        if f.severity == "info" and not args.verbose:
            continue
        print(f"{f.severity.upper():7s} {f.code:18s} {f.key:28s} {f.message}")
    for p in stale:
        print(f"ERROR   stale-output       {str(p.relative_to(ROOT)):28s} differs from a fresh build (run scripts/build.py)")
    n_info = sum(f.severity == "info" for f in findings)
    print(f"\n{len(ctx['resolved'])} papers checked: {n_err} error(s), {n_warn} warning(s), {n_info} info.")
    if n_err or (args.strict and n_warn):
        print("VALIDATION FAILED")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
