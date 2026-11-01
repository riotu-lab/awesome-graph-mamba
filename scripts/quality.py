"""Consistency and data-quality checks.

Findings have a severity:

* ``error``   – the database is invalid or contradicts the manuscript
                tables (build/CI fails),
* ``warning`` – needs attention but does not invalidate the data,
* ``info``    – informational (e.g., missing DOI in the bibliography).

Used by ``build.py`` and ``validate.py`` (to fail CI).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from common import DATA, NR, latex_to_text


@dataclass
class Finding:
    severity: str
    code: str
    key: str
    message: str


def schema_findings(papers: list[dict]) -> list[Finding]:
    import jsonschema

    schema = json.loads((DATA / "schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    out = []
    for p in papers:
        for err in sorted(validator.iter_errors(p), key=lambda e: list(e.path)):
            loc = "/".join(str(x) for x in err.path) or "(record)"
            out.append(Finding("error", "schema", p.get("key", "?"), f"{loc}: {err.message}"))
    return out


def taxonomy_value_findings(papers: list[dict], taxonomy: dict) -> list[Finding]:
    out = []
    settings = {s["id"] for s in taxonomy["graph_settings"]}
    patterns = {p["id"] for p in taxonomy["design_patterns"]}
    domains = {d["id"]: {s["id"] for s in d["subdomains"]} for d in taxonomy["application_domains"]}
    levels = {lv["id"] for d in taxonomy["dimensions"] for lv in d.get("levels", [])}
    types = {ty["id"] for d in taxonomy["dimensions"] for ty in d.get("types", [])}
    roles = {r["id"] for r in taxonomy["roles"]}
    for p in papers:
        k = p.get("key", "?")
        for r in p.get("roles", []):
            if r not in roles:
                out.append(Finding("error", "invalid-role", k, f"unknown role '{r}'"))
        t = p.get("taxonomy")
        if t:
            if t.get("setting") not in settings:
                out.append(Finding("error", "invalid-category", k, f"unknown graph setting '{t.get('setting')}'"))
            for lv in t.get("d3", []):
                if lv not in levels:
                    out.append(Finding("error", "invalid-category", k, f"unknown D3 level '{lv}'"))
            for ty in t.get("d4", []):
                if ty not in types:
                    out.append(Finding("error", "invalid-category", k, f"unknown D4 type '{ty}'"))
        a = p.get("application")
        if a:
            if a.get("domain") not in domains:
                out.append(Finding("error", "invalid-category", k, f"unknown domain '{a.get('domain')}'"))
            elif a.get("subdomain") not in domains[a["domain"]]:
                out.append(Finding("error", "invalid-category", k, f"subdomain '{a.get('subdomain')}' not in domain '{a['domain']}'"))
            for pt in a.get("patterns", []):
                if pt not in patterns:
                    out.append(Finding("error", "invalid-category", k, f"unknown pattern '{pt}'"))
            if a.get("dominant_pattern") not in a.get("patterns", []):
                out.append(Finding("error", "pattern-inconsistent", k, "dominant_pattern is not among the checked patterns"))
            sp = a.get("secondary_pattern")
            if sp and sp not in a.get("patterns", []):
                out.append(Finding("error", "pattern-inconsistent", k, "secondary_pattern is not among the checked patterns"))
        if "taxonomy" in p.get("roles", []) and not t:
            out.append(Finding("error", "missing-field", k, "role 'taxonomy' requires a taxonomy block"))
        if "application" in p.get("roles", []) and not a:
            out.append(Finding("error", "missing-field", k, "role 'application' requires an application block"))
    return out


def duplicate_findings(papers: list[dict]) -> list[Finding]:
    out, seen_k, seen_m = [], {}, {}
    for p in papers:
        k = p.get("key")
        if k in seen_k:
            out.append(Finding("error", "duplicate-key", k, "BibTeX key appears more than once in papers.yaml"))
        seen_k[k] = True
        m = (p.get("model") or "").strip().lower()
        if m in seen_m:
            out.append(Finding("error", "duplicate-model", k, f"model name '{p.get('model')}' also used by {seen_m[m]}"))
        seen_m[m] = k
    return out


def reference_findings(data: dict, bib: dict, extraction: dict, bib_dups: list[str]) -> list[Finding]:
    out = []
    cited = extraction["cited_keys"]
    for p in data["papers"]:
        k = p["key"]
        if k not in bib:
            out.append(Finding("error", "missing-bib", k, "key not found in the bibliography"))
        if k not in cited:
            out.append(Finding("error", "not-cited", k, "key is not cited in the manuscript"))
        for lbl in p.get("sections", []):
            if lbl not in extraction["section_labels"] and not lbl.startswith(("tab:", "fig:", "eq:")):
                out.append(Finding("error", "bad-label", k, f"manuscript label '{lbl}' does not exist"))
    for k in extraction["cited_but_missing_in_bib"]:
        out.append(Finding("error", "missing-bib", k, "cited in the manuscript but missing from the bibliography"))
    for d in bib_dups:
        out.append(Finding("error", "duplicate-bib", d, "duplicate BibTeX key in the bibliography"))
    # keys referenced in auxiliary data files
    known = set(bib)
    for b in data["benchmarks"]["benchmarks"]:
        for k in b["models"]:
            if k not in {p["key"] for p in data["papers"]}:
                out.append(Finding("error", "unknown-key", k, f"benchmark '{b['id']}' references a work not in papers.yaml"))
    for t in data["results"]:
        for r in t["rows"]:
            for k in str(r.get("key", "")).split(","):
                if k and k not in known:
                    out.append(Finding("error", "missing-bib", k, f"result table '{t['id']}' row key not in the bibliography"))
        n = len(t["columns"])
        if len(t["better"]) != n:
            out.append(Finding("error", "result-shape", t["id"], "length of 'better' differs from number of columns"))
        for r in t["rows"]:
            if len(r["values"]) != n:
                out.append(Finding("error", "result-shape", t["id"], f"row '{r['model']}' has {len(r['values'])} values, expected {n}"))
    for c in data["challenges"]:
        for e in c["early_work"]:
            if e["key"] not in known:
                out.append(Finding("error", "missing-bib", e["key"], f"challenge '{c['id']}' early work not in the bibliography"))
    # classified in manuscript but missing from database
    db = {p["key"] for p in data["papers"]}
    for k in extraction["classified_keys"]:
        if k not in db:
            out.append(Finding("error", "unlisted-work", k, "classified in a manuscript table but missing from papers.yaml "
                                                       "(run scripts/extract_papers.py --merge)"))
    n_unc = len(extraction["bib_entries_not_cited"])
    if n_unc:
        out.append(Finding("info", "uncited-bib", "*", f"{n_unc} bibliography entries are not cited in the manuscript: "
                                                       + ", ".join(extraction["bib_entries_not_cited"])))
    return out


def manuscript_consistency_findings(data: dict, extraction: dict) -> list[Finding]:
    """Compare curated classifications with what is parsed from the manuscript tables."""
    out = []
    tax = {r["key"]: r for r in extraction["unified_taxonomy"]}
    app = {r["key"]: r for r in extraction["cross_domain_applications"]}
    fig = {r["key"]: r for r in extraction["design_pattern_figure"]}
    for p in data["papers"]:
        k = p["key"]
        verified_override = p["verification"].get("status") == "verified" and p["verification"].get("override_reason")
        sev = "warning" if verified_override else "error"
        t = p.get("taxonomy")
        if t and k in tax:
            m = tax[k]
            for f in ("setting", "d3", "d4"):
                if (sorted(t[f]) if isinstance(t[f], list) else t[f]) != (sorted(m[f]) if isinstance(m[f], list) else m[f]):
                    out.append(Finding(sev, "tex-mismatch", k, f"taxonomy.{f} = {t[f]} but tab:unified-taxonomy gives {m[f]}"))
            for f in ("d1", "d2"):
                if re.sub(r"\W", "", t[f].lower()) != re.sub(r"\W", "", latex_to_text(m[f]).lower()):
                    out.append(Finding("warning", "tex-text-mismatch", k, f"taxonomy.{f} text differs from manuscript: '{m[f]}'"))
        elif t and k not in tax:
            out.append(Finding("error", "tex-missing", k, "has a taxonomy block but is not a row of tab:unified-taxonomy"))
        elif not t and k in tax:
            out.append(Finding("error", "tex-missing", k, "row of tab:unified-taxonomy but no taxonomy block"))
        a = p.get("application")
        if a and k in app:
            m = app[k]
            if sorted(a["patterns"]) != sorted(m["patterns"]):
                out.append(Finding(sev, "tex-mismatch", k, f"patterns {a['patterns']} but manuscript table gives {m['patterns']}"))
            if a["domain"] != m["domain"]:
                out.append(Finding(sev, "tex-mismatch", k, f"domain {a['domain']} but manuscript table gives {m['domain']}"))
            if m["subdomain"] and a["subdomain"] != m["subdomain"]:
                out.append(Finding(sev, "tex-mismatch", k, f"subdomain {a['subdomain']} but manuscript table gives {m['subdomain']}"))
            if bool(p.get("precursor")) != m["precursor"]:
                out.append(Finding(sev, "tex-mismatch", k, "precursor flag differs from the dagger in the manuscript table"))
        elif a and k not in app:
            out.append(Finding("error", "tex-missing", k, "has an application block but is not a row of tab:cross-domain-applications"))
        elif not a and k in app:
            out.append(Finding("error", "tex-missing", k, "row of tab:cross-domain-applications but no application block"))
        if a and k in fig:
            f = fig[k]
            if a["dominant_pattern"] != f["dominant"]:
                out.append(Finding(sev, "tex-mismatch", k, f"dominant pattern {a['dominant_pattern']} but fig:design-patterns gives {f['dominant']}"))
            if a.get("secondary_pattern") != f["secondary"]:
                out.append(Finding(sev, "tex-mismatch", k, f"secondary pattern {a.get('secondary_pattern')} but fig:design-patterns gives {f['secondary']}"))
            if bool(p.get("multimodal")) != f["multimodal"]:
                out.append(Finding(sev, "tex-mismatch", k, "multimodal flag differs from fig:design-patterns"))
    return out


def completeness_findings(resolved: list[dict]) -> list[Finding]:
    out = []
    for r in resolved:
        k = r["key"]
        for fl in r["verification"].get("flags", []):
            out.append(Finding("warning", "author-flag", k, fl))
        if r["methodology"] in ("", NR) or r["methodology"].startswith("NR"):
            out.append(Finding("warning", "incomplete", k, "methodology not described in the survey"))
        if r["primary_link"] == NR:
            out.append(Finding("info", "no-link", k, "no DOI/arXiv/URL in the bibliography"))
        if "et al." in r["authors"]:
            out.append(Finding("info", "truncated-authors", k, "author list truncated ('and others') in the bibliography"))
        m = re.search(r"(19|20)\d{2}", k)
        if m and str(r["year"]) != m.group(0):
            out.append(Finding("info", "key-year", k, f"BibTeX key suggests {m.group(0)} but year field is {r['year']}"))
    return out


def all_findings(data, bib, extraction, resolved, bib_dups) -> list[Finding]:
    f = []
    f += schema_findings(data["papers"])
    f += duplicate_findings(data["papers"])
    f += taxonomy_value_findings(data["papers"], data["taxonomy"])
    f += reference_findings(data, bib, extraction, bib_dups)
    f += manuscript_consistency_findings(data, extraction)
    f += completeness_findings(resolved)
    return f
