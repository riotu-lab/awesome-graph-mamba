"""Resolve the curated database (data/papers.yaml) against the bibliography and manuscript.

Each resolved record is the fully denormalised view of one reviewed work
(bibliographic metadata, links, classification, evidence) used by the website.
"""
from __future__ import annotations

from common import NR, bib_links, bib_venue, format_authors, latex_to_text, scholar_search

# Display order of categories
SETTING_ORDER = ["static_general", "dynamic_spatiotemporal", "heterogeneous_higher_order"]
ROLE_ORDER = ["taxonomy", "application", "discussed"]


def lookup(taxonomy: dict) -> dict:
    """Convenient id -> label lookups built from taxonomy.yaml."""
    lk = {
        "setting": {s["id"]: s["label"] for s in taxonomy["graph_settings"]},
        "pattern": {p["id"]: p["label"] for p in taxonomy["design_patterns"]},
        "domain": {d["id"]: d["label"] for d in taxonomy["application_domains"]},
        "subdomain": {},
        "subdomain_parent": {},
        "level": {},
        "type": {},
        "role": {r["id"]: r["label"] for r in taxonomy["roles"]},
    }
    for d in taxonomy["application_domains"]:
        for s in d["subdomains"]:
            lk["subdomain"][s["id"]] = s["label"]
            lk["subdomain_parent"][s["id"]] = d["id"]
    for dim in taxonomy["dimensions"]:
        for lv in dim.get("levels", []):
            lk["level"][lv["id"]] = lv["label"]
        for ty in dim.get("types", []):
            lk["type"][ty["id"]] = ty["label"]
    return lk


def paper_benchmarks(key: str, benchmarks: dict) -> list[dict]:
    return [b for b in benchmarks["benchmarks"] if key in b["models"]]


def paper_results(key: str, results: list[dict]) -> list[str]:
    """IDs of result tables in which the paper appears as a row."""
    out = []
    for t in results:
        if any(key in str(r.get("key", "")).split(",") for r in t["rows"]):
            out.append(t["id"])
    return out


def paper_challenges(key: str, challenges: list[dict]) -> list[str]:
    return [c["id"] for c in challenges if any(e["key"] == key for e in c["early_work"])]


def resolve(data: dict, bib: dict, extraction: dict) -> list[dict]:
    labels = extraction.get("section_labels", {})
    cite_secs = extraction.get("cited_keys", {})
    resolved = []
    for p in data["papers"]:
        e = bib.get(p["key"], {})
        title = latex_to_text(e.get("title")) or NR
        links = bib_links(e) if e else {}
        # data/links.yaml fills gaps only: the bibliography's own links always take precedence.
        extra = data.get("links", {}).get(p["key"], {})
        for kind, value in extra.items():
            if not any(links.get(x) for x in ("doi", "arxiv", "url")):
                links[kind] = {"doi": "https://doi.org/", "arxiv": "https://arxiv.org/abs/", "url": ""}[kind] + value
        primary = links.get("doi") or links.get("arxiv") or links.get("url")
        rec = {
            "key": p["key"],
            "model": p["model"],
            "aliases": p.get("aliases", []),
            "title": title,
            "authors": format_authors(e.get("author")),
            "year": e.get("year", NR),
            "venue": bib_venue(e) if e else NR,
            "entry_type": e.get("ENTRYTYPE", NR),
            "doi": links.get("doi", NR),
            "arxiv": links.get("arxiv", NR),
            "url": links.get("url", NR),
            "primary_link": primary or NR,
            "search_link": scholar_search(title) if title != NR else NR,
            "code": p.get("code", NR),
            "roles": p["roles"],
            "precursor": bool(p.get("precursor", False)),
            "multimodal": bool(p.get("multimodal", False)),
            "taxonomy": p.get("taxonomy"),
            "application": p.get("application"),
            "methodology": p.get("methodology", NR),
            "contributions": p.get("contributions", []),
            "complexity": p.get("complexity", NR),
            "efficiency": p.get("efficiency"),
            "expressivity": p.get("expressivity"),
            "benchmarks": [b["id"] for b in paper_benchmarks(p["key"], data["benchmarks"])],
            "datasets": [d for b in paper_benchmarks(p["key"], data["benchmarks"]) for d in b["datasets"]],
            "metrics": sorted({m for b in paper_benchmarks(p["key"], data["benchmarks"]) for m in b["metrics"]}),
            "result_tables": paper_results(p["key"], data["results"]),
            "challenges": paper_challenges(p["key"], data["challenges"]),
            "advantages": p.get("advantages", []),
            "limitations": p.get("limitations", []),
            "notes": p.get("notes", []),
            "manuscript_labels": p["sections"],
            "manuscript_sections": [
                f"{labels[l]['number']} {labels[l]['title']}" for l in p["sections"] if l in labels
            ],
            "cited_in_sections": cite_secs.get(p["key"], []),
            "verification": p["verification"],
            "in_bib": bool(e),
        }
        resolved.append(rec)
    return resolved
