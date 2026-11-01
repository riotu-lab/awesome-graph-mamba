#!/usr/bin/env python3
"""Parse the survey manuscript and bibliography.

Outputs ``data/generated/tex_extraction.json`` containing

* every citation key and the manuscript sections citing it,
* section label -> number mapping (for traceability),
* the rows of ``tab:unified-taxonomy`` (D1--D4 classification),
* the rows of ``tab:cross-domain-applications`` (design patterns),
* the panel entries of ``fig:design-patterns`` (dominant/secondary
  pattern, multimodal and precursor markers),
* the split between reviewed works and background references.

With ``--merge`` any work found in the classification tables but absent
from ``data/papers.yaml`` is appended as a stub with
``verification.status: needs_verification``. Existing records are never
modified, so manually verified metadata is preserved across runs.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    DATA, GENERATED, SNAPSHOT_EXTRACTION, SOURCE_BIB, SOURCE_TEX, cite_keys, cite_sections, dump_json,
    load_bib, load_yaml, section_numbers, sources_available, strip_comments, write_outputs,
)

CMARK = "\\cmark"


def _norm(s: str) -> str:
    s = re.sub(r"\\[a-zA-Z]+", " ", s)
    s = re.sub(r"[{}$^]", " ", s)
    return re.sub(r"[^a-z]+", "", s.lower())


def _clean_cell(cell: str) -> str:
    cell = re.sub(r"\\cite[tp]?\{[^}]*\}", "", cell)
    cell = re.sub(r"\$\^\{\\dagger\}\$", "", cell)
    cell = cell.replace("~", " ").replace("\\&", "&")
    cell = re.sub(r"\\textbf\{([^}]*)\}", r"\1", cell)
    cell = re.sub(r"\s+", " ", cell)
    return cell.strip()


def _rows(body: str, start_marker: str) -> list[str]:
    pos = body.find(start_marker)
    body = body[pos + len(start_marker):] if pos >= 0 else body
    body = body.split("\\end{tabular}")[0]
    return [r for r in re.split(r"\\\\(?:\[[^\]]*\])?", body)]


def _header_text(row: str) -> str | None:
    m = re.search(r"\\multicolumn\{\d+\}\{l\}\{(.*)\}\s*$", row.strip(), re.S)
    if not m:
        return None
    inner = m.group(1)
    inner = re.sub(r"\\text(bf|it)\{", "", inner).replace("}", "")
    return inner.strip()


def _match_label(text: str, options: list[dict]) -> str | None:
    t = _norm(text)
    for o in options:
        if _norm(o["label"]) == t:
            return o["id"]
    return None


def env_body(tex: str, label: str, envs: str = r"table\*?|longtable|figure\*?") -> str | None:
    tex = strip_comments(tex)
    idx = tex.find("\\label{" + label + "}")
    if idx < 0:
        return None
    starts = list(re.finditer(r"\\begin\{(" + envs + r")\}", tex[:idx]))
    if not starts:
        return None
    s = starts[-1]
    end = tex.find("\\end{" + s.group(1) + "}", idx)
    return tex[s.start():end]


def parse_unified_taxonomy(tex: str, taxonomy: dict) -> list[dict]:
    body = env_body(tex, "tab:unified-taxonomy")
    if body is None:
        return []
    levels = ["input", "dynamics", "operator"]
    types = ["standalone", "sequential", "parallel", "embedded"]
    setting = None
    out = []
    for row in _rows(body, "\\midrule"):
        row = re.sub(r"\\(midrule|toprule|bottomrule|hline)", "", row).strip()
        if not row:
            continue
        head = _header_text(row)
        if head is not None:
            setting = _match_label(head, taxonomy["graph_settings"])
            continue
        cells = re.split(r"(?<!\\)&", row)
        if len(cells) != 10:
            continue
        keys = cite_keys(cells[0])
        if not keys:
            continue
        marks = [CMARK in c for c in cells[3:]]
        out.append({
            "key": keys[0],
            "model": _clean_cell(cells[0]),
            "setting": setting,
            "d1": _clean_cell(cells[1]),
            "d2": _clean_cell(cells[2]),
            "d3": [lv for lv, m in zip(levels, marks[:3]) if m],
            "d4": [ty for ty, m in zip(types, marks[3:]) if m],
        })
    return out


def parse_cross_domain(tex: str, taxonomy: dict) -> list[dict]:
    body = env_body(tex, "tab:cross-domain-applications")
    if body is None:
        return []
    body = body.split("\\end{longtable}")[0]
    patterns = ["DV", "RT", "GS", "LG"]
    domains = taxonomy["application_domains"]
    domain = sub = None
    out = []
    for row in _rows(body, "\\endlastfoot"):
        row = re.sub(r"\\(midrule|toprule|bottomrule|hline)", "", row)
        row = re.sub(r"\\rowcolor\{[^}]*\}", "", row).strip()
        if not row:
            continue
        head = _header_text(row)
        if head is not None:
            d = _match_label(head, domains)
            if d:
                domain, sub = d, None
                continue
            for dom in domains:
                s = _match_label(head, dom["subdomains"])
                if s:
                    domain, sub = dom["id"], s
                    break
            continue
        cells = re.split(r"(?<!\\)&", row)
        if len(cells) != 8:
            continue
        keys = cite_keys(cells[0])
        if not keys:
            continue
        out.append({
            "key": keys[0],
            "model": _clean_cell(cells[0]),
            "precursor": "\\dagger" in cells[0],
            "domain": domain,
            "subdomain": sub,
            "task": _clean_cell(cells[1]),
            "graph_construction": _clean_cell(cells[2]),
            "division_of_labor": _clean_cell(cells[3]),
            "patterns": [p for p, c in zip(patterns, cells[4:]) if CMARK in c],
        })
    return out


def parse_design_pattern_figure(tex: str) -> list[dict]:
    body = env_body(tex, "fig:design-patterns")
    if body is None:
        return []
    out = []
    panel = None
    for line in body.splitlines():
        pm = re.search(r"\\phd\{[^}]*\}\{([^}]*)\}", line)
        if pm:
            panel = pm.group(1)
        for m in re.finditer(r"\\gw\{(DV|RT|GS|LG)\}\{(.*?)\}\{([^}]+)\}", line):
            dom, name, key = m.groups()
            sec = re.search(r"\\mathrm\{(DV|RT|GS|LG)\}", name)
            clean = re.sub(r"\$.*?\$", "", name).replace("--", "–").strip()
            out.append({
                "key": key,
                "model": clean,
                "panel": panel,
                "dominant": dom,
                "secondary": sec.group(1) if sec else None,
                "multimodal": "blacklozenge" in name,
                "precursor": "dagger" in name,
            })
    return out


def extract(tex: str, bib: dict, taxonomy: dict) -> dict:
    sections = cite_sections(tex)
    labels = section_numbers(tex)
    unified = parse_unified_taxonomy(tex, taxonomy)
    apps = parse_cross_domain(tex, taxonomy)
    fig = parse_design_pattern_figure(tex)
    classified = sorted({r["key"] for r in unified} | {r["key"] for r in apps})
    all_keys = sorted(sections)
    return {
        "source": {"tex": SOURCE_TEX.name, "bib": SOURCE_BIB.name},
        "n_cited_keys": len(all_keys),
        "n_bib_entries": len(bib),
        "cited_keys": {k: sections[k] for k in all_keys},
        "cited_but_missing_in_bib": sorted(k for k in all_keys if k not in bib),
        "bib_entries_not_cited": sorted(k for k in bib if k not in sections),
        "section_labels": labels,
        "classified_keys": classified,
        "background_keys": sorted(k for k in all_keys if k not in classified),
        "unified_taxonomy": unified,
        "cross_domain_applications": apps,
        "design_pattern_figure": fig,
    }


def _stub_yaml(key: str, tax: dict | None, app: dict | None, fig: dict | None) -> str:
    def q(s):
        return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'

    model = (tax or app or {}).get("model", key)
    roles = (["taxonomy"] if tax else []) + (["application"] if app else [])
    lines = [f"\n- key: {key}", f"  model: {q(model)}", f"  roles: [{', '.join(roles)}]",
             "  sections: []  # TODO: add manuscript labels"]
    if tax:
        lines += ["  taxonomy:", f"    setting: {tax['setting']}", f"    d1: {q(tax['d1'])}", f"    d2: {q(tax['d2'])}",
                  f"    d3: [{', '.join(tax['d3'])}]", f"    d4: [{', '.join(tax['d4'])}]"]
    if app:
        lines += ["  application:", f"    domain: {app['domain']}", f"    subdomain: {app['subdomain']}",
                  f"    task: {q(app['task'])}", f"    graph_construction: {q(app['graph_construction'])}",
                  f"    division_of_labor: {q(app['division_of_labor'])}",
                  f"    patterns: [{', '.join(app['patterns'])}]",
                  f"    dominant_pattern: {(fig or {}).get('dominant') or (app['patterns'] or ['NR'])[0]}"]
        if fig and fig.get("secondary"):
            lines.append(f"    secondary_pattern: {fig['secondary']}")
    lines += ['  methodology: "NR"  # TODO: summarise from the manuscript',
              "  verification:", "    status: needs_verification",
              '    flags: ["Auto-generated stub from manuscript tables; complete and verify."]']
    return "\n".join(lines) + "\n"


def merge_stubs(extraction: dict, papers_path: Path = DATA / "papers.yaml") -> list[str]:
    existing = {p["key"] for p in load_yaml(papers_path)["papers"]}
    tax = {r["key"]: r for r in extraction["unified_taxonomy"]}
    app = {r["key"]: r for r in extraction["cross_domain_applications"]}
    fig = {r["key"]: r for r in extraction["design_pattern_figure"]}
    new = [k for k in extraction["classified_keys"] if k not in existing]
    if new:
        with open(papers_path, "a", encoding="utf-8") as fh:
            fh.write("\n# --- stubs appended by extract_papers.py --merge (verify before use) ---")
            for k in new:
                fh.write(_stub_yaml(k, tax.get(k), app.get(k), fig.get(k)))
    return new


def run(merge: bool = False, write: bool = True) -> dict:
    """Parse the manuscript; without the (private) sources, reuse the committed extraction snapshot."""
    if sources_available():
        tex = SOURCE_TEX.read_text(encoding="utf-8")
        bib = load_bib()
        taxonomy = load_yaml(DATA / "taxonomy.yaml")
        extraction = extract(tex, bib, taxonomy)
    else:
        extraction = json.loads(SNAPSHOT_EXTRACTION.read_text(encoding="utf-8"))
        write = False
    if write:
        write_outputs({GENERATED / "tex_extraction.json": dump_json(extraction)})
    if merge:
        added = merge_stubs(extraction)
        extraction["merged_stubs"] = added
    return extraction


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--merge", action="store_true", help="append stubs for unclassified-in-database works")
    args = ap.parse_args()
    ex = run(merge=args.merge)
    print(f"cited keys: {ex['n_cited_keys']} | bib entries: {ex['n_bib_entries']}")
    print(f"taxonomy rows: {len(ex['unified_taxonomy'])} | application rows: {len(ex['cross_domain_applications'])} "
          f"| figure entries: {len(ex['design_pattern_figure'])}")
    print(f"classified works: {len(ex['classified_keys'])} | background references: {len(ex['background_keys'])}")
    if ex["cited_but_missing_in_bib"]:
        print("MISSING in bib:", ", ".join(ex["cited_but_missing_in_bib"]))
    if args.merge:
        print("stubs appended:", ", ".join(ex["merged_stubs"]) or "none")


if __name__ == "__main__":
    main()
