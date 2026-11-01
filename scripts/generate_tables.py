#!/usr/bin/env python3
"""Build the scientific comparison tables shown on the website from the paper database.

Every table is an in-memory ``Table`` of ``Cell`` objects (Markdown, LaTeX, and
plain-text renderings of each value). Missing values are ``NR``; performance
numbers are only placed side by side when the survey reports them from the same
source paper and protocol; derived tables say so in their notes.
"""
from __future__ import annotations

import re
import sys
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NR, csv_text, md_text, tex_text  # noqa: E402
from database import SETTING_ORDER, lookup  # noqa: E402

CHECK_MD, CHECK_TEX = "✓", r"\cmark"


# ---------------------------------------------------------------------------
# Table model and renderers
# ---------------------------------------------------------------------------
@dataclass
class Cell:
    md: str
    tex: str
    csv: str

    @classmethod
    def text(cls, s: Any) -> "Cell":
        return cls(md_text(s), tex_text(s), csv_text(s))

    @classmethod
    def check(cls, flag: bool) -> "Cell":
        return cls(CHECK_MD if flag else "", CHECK_TEX if flag else "", "1" if flag else "0")

    @classmethod
    def model(cls, name: str, key: str | None, link: str | None = None, marks: str = "") -> "Cell":
        md = md_text(name) + marks
        if link and link != NR:
            md = f"[{md_text(name)}]({link}){marks}"
        tex = tex_text(name) + tex_text(marks) if marks else tex_text(name)
        if key:
            tex += "~\\cite{" + key + "}"
        return cls(md, tex, csv_text(name))


_REF_NAMES = {"tab": "Table~\\ref", "fig": "Fig.~\\ref", "sec": "Section~\\ref", "subsec": "Section~\\ref",
              "eq": "Eq.~\\eqref", "app": "Appendix~\\ref"}


def tex_refs(s: str) -> str:
    """Turn manuscript labels (tab:x, sec:x, ...) in already-escaped LaTeX into cross-references."""
    def rep(m):
        label = (m.group(1) + ":" + m.group(2)).replace("\\_", "_")
        return _REF_NAMES[m.group(1)] + "{" + label + "}"
    return re.sub(r"\b(tab|fig|subsec|sec|eq|app):((?:[A-Za-z0-9-]|\\_)+)", rep, s)


def C(x: Any) -> Cell:
    return x if isinstance(x, Cell) else Cell.text(x)


@dataclass
class Table:
    id: str
    title: str
    caption: str
    headers: list[str]
    colspec: str
    rows: list = field(default_factory=list)  # list[list[Cell]] or ("group", label)
    notes: list[str] = field(default_factory=list)
    long: bool = False
    group_header: str = "Group"
    csv_extra_headers: list[str] | None = None
    md_align: list[str] | None = None
    tex_head: str | None = None  # optional raw LaTeX header (multi-row column groups)

    def add(self, cells: list[Any]) -> None:
        self.rows.append([C(c) for c in cells])

    def group(self, label: str) -> None:
        self.rows.append(("group", label))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def marks(rec: dict) -> str:
    m = ""
    if rec.get("precursor"):
        m += "†"
    if rec.get("multimodal"):
        m += "◆"
    if rec["verification"]["status"] == "needs_verification":
        m += "⚠"
    return m


def model_cell(rec: dict, with_marks: bool = True) -> Cell:
    return Cell.model(rec["model"], rec["key"], rec["primary_link"], marks(rec) if with_marks else "")


def by_key(resolved: list[dict]) -> dict[str, dict]:
    return {r["key"]: r for r in resolved}


LEGEND_MARKS = ("Markers: † structured-SSM precursor without input-dependent selection; ◆ multimodal input; "
                "⚠ record flagged for author verification (see docs/FLAGS.md). NR = not reported in the survey.")


# ---------------------------------------------------------------------------
# Individual tables
# ---------------------------------------------------------------------------
def t_taxonomy_dimensions(data: dict, resolved: list[dict]) -> Table:
    t = Table("taxonomy_dimensions", "T1 · Taxonomy dimensions",
              "Taxonomy dimensions used to classify Graph Mamba architectures (manuscript tab:taxonomy-dimensions).",
              ["Dim.", "Design question", "Architectural aspect", "Main question", "Representative design choices", "Categories"],
              "p{0.8cm}p{1.6cm}p{2.8cm}p{3.2cm}p{5.2cm}p{3.4cm}")
    for d in data["taxonomy"]["dimensions"]:
        cats = [x["label"] for x in d.get("levels", []) + d.get("types", [])]
        t.add([d["id"], d["name"], d["aspect"], d["question"], d["choices"], ", ".join(cats) if cats else "Free text (per model)"])
    t.notes = ["The four dimensions are not mutually exclusive; a model receives one label per dimension, "
               "and multiple D3/D4 labels when it combines strategies."]
    return t


def t_unified_taxonomy(data: dict, resolved: list[dict]) -> Table:
    lk = lookup(data["taxonomy"])
    t = Table("unified_taxonomy", "T2 · Unified D1–D4 taxonomy of Graph Mamba architectures",
              "Unified taxonomy of representative Graph Mamba architectures according to tokenization (D1), "
              "ordering (D2), coupling (D3), and integration (D4) (manuscript tab:unified-taxonomy).",
              ["Model", "Year", "Tokenization (D1)", "Ordering (D2)", "D3: Input", "D3: Dynamics", "D3: Operator",
               "D4: Standalone", "D4: Sequential", "D4: Parallel", "D4: Embedded"],
              "p{2.4cm}c p{3.4cm}p{3.4cm}ccccccc",
              md_align=[":---", ":---:", ":---", ":---"] + [":---:"] * 7)
    t.group_header = "Graph setting"
    rot = lambda x: "\\rotatebox{90}{" + x + "}"
    t.tex_head = ("\\multirow{2}{*}{\\textbf{Model}} & \\multirow{2}{*}{\\textbf{Year}} & "
                  "\\multirow{2}{*}{\\textbf{Tokenization (D1)}} & \\multirow{2}{*}{\\textbf{Ordering (D2)}} & "
                  "\\multicolumn{3}{c}{\\textbf{Coupling (D3)}} & \\multicolumn{4}{c}{\\textbf{Integration (D4)}} \\\\\n"
                  "\\cmidrule(lr){5-7}\\cmidrule(lr){8-11}\n& & & & "
                  + " & ".join(rot(x) for x in ["Input", "Dynamics", "Operator", "Standalone", "Sequential", "Parallel", "Embedded"])
                  + " \\\\")
    for s in SETTING_ORDER:
        recs = [r for r in resolved if r["taxonomy"] and r["taxonomy"]["setting"] == s]
        if not recs:
            continue
        t.group(lk["setting"][s])
        for r in recs:
            tx = r["taxonomy"]
            t.add([model_cell(r), r["year"], tx["d1"], tx["d2"]]
                  + [Cell.check(lv in tx["d3"]) for lv in ("input", "dynamics", "operator")]
                  + [Cell.check(ty in tx["d4"]) for ty in ("standalone", "sequential", "parallel", "embedded")])
    t.notes = ["D3 indicates where graph structure enters the state-space computation (input-, dynamics-, or "
               "operator-level coupling); D4 indicates how the state-space component is combined with "
               "graph-learning mechanisms. Multiple check marks: the architecture combines strategies.", LEGEND_MARKS]
    return t


def t_structural_tradeoffs(data: dict, resolved: list[dict]) -> Table:
    t = Table("structural_tradeoffs", "T3 · Structural and computational trade-offs per dimension",
              "Structural and computational implications of the Graph Mamba taxonomy dimensions "
              "(manuscript tab:structural-tradeoffs), with the cost term of eq:end-to-end-cost each dimension contributes.",
              ["Dim.", "Design choice", "Structural implication", "Main trade-off", "Cost term"],
              "p{0.8cm}p{2.4cm}p{4.4cm}p{6.2cm}p{1.6cm}")
    for d in data["taxonomy"]["dimensions"]:
        t.add([d["id"], f"{d['name']}: {d['aspect']}", d["structural_implication"], d["trade_off"],
               Cell(f"`{d['cost_term']}`", "$" + d["cost_term"].replace("_", "_{\\mathrm{") + "}}$", d["cost_term"])])
    t.notes = [f"Conceptual decomposition: {data['taxonomy']['cost_decomposition']}. T_graph belongs to graph "
               "construction, which the survey treats as context rather than a design question."]
    return t


def t_cross_domain(data: dict, resolved: list[dict]) -> Table:
    t = Table("cross_domain_applications", "T4 · Cross-domain applications and graph–SSM design patterns",
              "Cross-domain Graph Mamba applications and recurring graph--SSM design patterns "
              "(manuscript tab:cross-domain-applications and fig:design-patterns).",
              ["Work", "Year", "Task", "Graph construction", "Graph–SSM division of labor", "DV", "RT", "GS", "LG", "Dominant (secondary)"],
              "p{2.3cm}c p{2.6cm}p{3.2cm}p{5.6cm}ccccc", long=True,
              md_align=[":---", ":---:", ":---", ":---", ":---"] + [":---:"] * 5)
    t.group_header = "Domain"
    t.tex_head = ("\\multirow{2}{*}{\\textbf{Work}} & \\multirow{2}{*}{\\textbf{Year}} & \\multirow{2}{*}{\\textbf{Task}} & "
                  "\\multirow{2}{*}{\\textbf{Graph construction}} & \\multirow{2}{*}{\\textbf{Graph--SSM division of labor}} & "
                  "\\multicolumn{4}{c}{\\textbf{Pattern}} & \\multirow{2}{*}{\\textbf{Dominant}} \\\\\n"
                  "\\cmidrule(lr){6-9}\n& & & & & DV & RT & GS & LG & \\\\")
    for dom in data["taxonomy"]["application_domains"]:
        for sub in dom["subdomains"]:
            recs = [r for r in resolved if r["application"] and r["application"]["subdomain"] == sub["id"]]
            if not recs:
                continue
            t.group(f"{dom['label']} — {sub['label']}")
            for r in recs:
                a = r["application"]
                dom_txt = a["dominant_pattern"] + (f" (+{a['secondary_pattern']})" if a.get("secondary_pattern") else "")
                t.add([model_cell(r), r["year"], a["task"], a["graph_construction"], a["division_of_labor"]]
                      + [Cell.check(p in a["patterns"]) for p in ("DV", "RT", "GS", "LG")] + [dom_txt])
    t.notes = ["Patterns: DV = dual-view; RT = relational--temporal; GS = graph-guided sequence; LG = local-to-global. "
               "Multiple check marks indicate combined patterns; the dominant/secondary assignment follows fig:design-patterns.",
               LEGEND_MARKS]
    return t


def t_pattern_distribution(data: dict, resolved: list[dict]) -> Table:
    t = Table("pattern_distribution", "T5 · Distribution of dominant design patterns across application settings (derived)",
              "Number of reviewed applications per data setting and dominant design pattern. Derived automatically "
              "from the dominant-pattern labels of fig:design-patterns; secondary patterns in parentheses.",
              ["Data setting", "DV", "RT", "GS", "LG", "Total", "Precursors (†)", "Multimodal (◆)"],
              "p{5cm}ccccccc", md_align=[":---"] + [":---:"] * 7)
    apps = [r for r in resolved if r["application"]]
    tot_dom, tot_sec = Counter(), Counter()
    for dom in data["taxonomy"]["application_domains"]:
        for sub in dom["subdomains"]:
            recs = [r for r in apps if r["application"]["subdomain"] == sub["id"]]
            if not recs:
                continue
            dc = Counter(r["application"]["dominant_pattern"] for r in recs)
            sc = Counter(r["application"].get("secondary_pattern") for r in recs if r["application"].get("secondary_pattern"))
            tot_dom.update(dc)
            tot_sec.update(sc)
            cells = [f"{dc.get(p, 0)}" + (f" (+{sc[p]})" if sc.get(p) else "") for p in ("DV", "RT", "GS", "LG")]
            t.add([sub["label"]] + cells + [len(recs), sum(r["precursor"] for r in recs), sum(r["multimodal"] for r in recs)])
    t.add([Cell("**Total**", "\\textbf{Total}", "Total")]
          + [f"{tot_dom.get(p, 0)}" + (f" (+{tot_sec[p]})" if tot_sec.get(p) else "") for p in ("DV", "RT", "GS", "LG")]
          + [len(apps), sum(r["precursor"] for r in apps), sum(r["multimodal"] for r in apps)])
    t.notes = ["Derived statistic (not a manuscript table). Counts dominant patterns only; '+n' gives secondary-pattern assignments."]
    return t


def t_coupling_integration(data: dict, resolved: list[dict]) -> Table:
    lk = lookup(data["taxonomy"])
    levels = ["input", "dynamics", "operator"]
    types = ["standalone", "sequential", "parallel", "embedded"]
    t = Table("coupling_integration", "T6 · Coupling depth × integration type (derived)",
              "Number of architectures in tab:unified-taxonomy per graph setting, coupling level (D3) and integration "
              "type (D4). Derived automatically; an architecture with several labels is counted once per label.",
              ["Graph setting", "Models", "Input", "Dynamics", "Operator", "Standalone", "Sequential", "Parallel", "Embedded"],
              "p{4.6cm}cccccccc", md_align=[":---"] + [":---:"] * 8)
    tax = [r for r in resolved if r["taxonomy"]]
    for s in SETTING_ORDER:
        recs = [r for r in tax if r["taxonomy"]["setting"] == s]
        t.add([lk["setting"][s], len(recs)]
              + [sum(lv in r["taxonomy"]["d3"] for r in recs) for lv in levels]
              + [sum(ty in r["taxonomy"]["d4"] for r in recs) for ty in types])
    t.add([Cell("**All settings**", "\\textbf{All settings}", "All settings"), len(tax)]
          + [sum(lv in r["taxonomy"]["d3"] for r in tax) for lv in levels]
          + [sum(ty in r["taxonomy"]["d4"] for r in tax) for ty in types])
    # cross matrix as additional rows
    t.group("Cross-tabulation D3 level × D4 type (all settings)")
    for lv in levels:
        na = Cell("–", "--", "")
        t.add([lk["level"][lv], sum(lv in r["taxonomy"]["d3"] for r in tax), na, na, na]
              + [sum(lv in r["taxonomy"]["d3"] and ty in r["taxonomy"]["d4"] for r in tax) for ty in types])
    t.notes = ["Derived statistic (not a manuscript table). " + _coupling_summary(tax, lk, levels, types)]
    return t


def _coupling_summary(tax: list[dict], lk: dict, levels: list[str], types: list[str]) -> str:
    """State the D3/D4 counts (most common first), computed from the database. The survey's qualitative
    observation is repeated only while the counts still support it."""
    d3 = {lv: sum(lv in r["taxonomy"]["d3"] for r in tax) for lv in levels}
    d4 = {ty: sum(ty in r["taxonomy"]["d4"] for r in tax) for ty in types}

    def ranked(counts: dict, names: dict) -> str:
        parts = [f"{names[k].lower()} ({n})" for k, n in sorted(counts.items(), key=lambda kv: -kv[1])]
        return ", ".join(parts[:-1]) + ", and " + parts[-1]

    text = (f"Across the {len(tax)} classified architectures, coupling is {ranked(d3, lk['level'])}; "
            f"integration is {ranked(d4, lk['type'])}.")
    if (min(d3["input"], d3["dynamics"]) > d3["operator"]
            and min(d4["standalone"], d4["parallel"]) > max(d4["sequential"], d4["embedded"])):
        text += (" Input- and dynamics-level coupling and standalone and parallel integration are therefore the "
                 "dominant choices, as observed in the survey.")
    return text


def t_benchmarks(data: dict, resolved: list[dict]) -> Table:
    bk = by_key(resolved)
    t = Table("benchmark_summary", "T7 · Benchmarks used in the comparative analysis",
              "Representative benchmarks used to evaluate Graph Mamba models (manuscript tab:benchmark-summary).",
              ["Benchmark(s)", "Domain / task", "Graph setting", "Main metrics", "Representative models", "Numeric results"],
              "p{2.6cm}p{2.6cm}p{2.8cm}p{1.8cm}p{4.2cm}p{1.8cm}")
    for b in data["benchmarks"]["benchmarks"]:
        models_md = ", ".join(_md_link(bk[k]) for k in b["models"] if k in bk)
        models_tex = ", ".join(f"{tex_text(bk[k]['model'])}~\\cite{{{k}}}" for k in b["models"] if k in bk)
        models_csv = "; ".join(bk[k]["model"] for k in b["models"] if k in bk)
        res = b.get("results_table")
        res_cell = Cell(f"[{res}]({res}.md)", f"Table~\\ref{{tab:repo-{res}}}", res) if res else Cell.text(NR)
        t.add([", ".join(b["datasets"]), b["domain_task"], b["graph_setting"], ", ".join(b["metrics"]),
               Cell(models_md, models_tex, models_csv), res_cell])
    leg = "; ".join(f"{k} = {v}" for k, v in data["benchmarks"]["metric_legend"].items())
    t.notes = [f"Metrics: {leg}.", "Identical metrics do not imply directly comparable experimental conditions across rows."]
    return t


def t_efficiency(data: dict, resolved: list[dict]) -> Table:
    t = Table("efficiency_summary", "T8 · Reported complexity, efficiency, and scalability evidence",
              "Reported complexity (sec. 4.3) and efficiency/scalability evidence (manuscript tab:efficiency-summary). "
              "Scan complexity and end-to-end scalability are reported separately.",
              ["Model", "Reported complexity", "Reported scaling", "Additional cost sources", "Reported evidence"],
              "p{2.2cm}p{4.0cm}p{2.6cm}p{3.2cm}p{4.6cm}")
    for r in resolved:
        if not (r["efficiency"] or r["complexity"] != NR):
            continue
        e = r["efficiency"] or {}
        t.add([model_cell(r), r["complexity"], e.get("scaling", NR), e.get("additional_costs", NR), e.get("evidence", NR)])
    t.notes = ["Evidence is configuration-specific and taken from the original publications; it does not establish "
               "complete-pipeline scalability for other settings. NR = not reported in the survey."]
    return t


def t_expressivity(data: dict, resolved: list[dict]) -> Table:
    t = Table("expressivity", "T9 · Theoretical expressive-power results",
              "Theoretical expressive-power results reported for SSM-based graph models, with message-passing GNNs "
              "and graph Transformers as references (manuscript tab:expressivity). PE/SE: positional/structural encodings.",
              ["Model", "Permutation property", "Reported result", "Caveat"],
              "p{2.8cm}p{2.8cm}p{6.0cm}p{5.0cm}")
    t.group("Reference model families")
    for ref in data["taxonomy"]["expressivity_references"]:
        t.add([Cell(md_text(ref["model"]), tex_text(ref["model"]) + "~\\cite{" + ",".join(ref["keys"]) + "}", ref["model"]),
               ref["permutation_property"], ref["result"], ref["caveat"]])
    t.group("SSM-based graph models")
    for r in resolved:
        if r["expressivity"]:
            x = r["expressivity"]
            t.add([model_cell(r), x["permutation_property"], x["result"], x["caveat"]])
    t.notes = ["For serialization-based models, separating WL-indistinguishable graphs may stem from symmetry breaking "
               "by the imposed ordering; expressive power should be characterized under an explicit invariance requirement."]
    return t


def t_future(data: dict, resolved: list[dict]) -> Table:
    bk = by_key(resolved)
    t = Table("future_directions", "T10 · Open challenges and research directions",
              "Open challenges and future research directions for Graph Mamba (manuscript tab:future-directions).",
              ["Challenge", "Design question", "Promising directions", "Early work / examples"],
              "p{3.0cm}p{2.2cm}p{7.2cm}p{4.6cm}")
    for c in data["challenges"]:
        md_parts, tex_parts, csv_parts = [], [], []
        for e in c["early_work"]:
            scope = f" ({e['scope']})" if e.get("scope") else ""
            if e["key"] in bk:
                md_parts.append(_md_link(bk[e["key"]], e["label"]) + md_text(scope))
            else:
                md_parts.append(md_text(e["label"]) + md_text(scope))
            tex_parts.append(f"{tex_text(e['label'])}~\\cite{{{e['key']}}}{tex_text(scope)}")
            csv_parts.append(e["label"] + scope)
        t.add([c["challenge"], ", ".join(c["design_questions"]), c["directions"],
               Cell(", ".join(md_parts), ", ".join(tex_parts), "; ".join(csv_parts))])
    return t


def _md_link(rec: dict, label: str | None = None) -> str:
    """Markdown link from a model name to its paper (plain name when no link is known)."""
    name = md_text(label or rec["model"])
    return f"[{name}]({rec['primary_link']})" if rec["primary_link"] != NR else name


def _num(v: str | None) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).split("±")[0].strip())
    except ValueError:
        return None


def t_performance(data: dict, resolved: list[dict], spec: dict) -> Table:
    cols = spec["columns"]
    headers = ["Model"] + [f"{c['dataset']} · {c['metric']}" if c["dataset"] != "—" else c["metric"] for c in cols]
    src = by_key(resolved).get(spec["source"])
    src_name = src["model"] if src else spec["source"]
    t = Table(spec["id"], f"Published results · {spec['caption']}",
              f"{spec['caption']}. Results as reported in the {src_name} paper and transcribed in manuscript {spec['label']}; "
              "not reproduced.",
              headers, "l" + "c" * len(cols), md_align=[":---"] + [":---:"] * len(cols))
    # best per column (within this table only)
    best = []
    for j, b in enumerate(spec["better"]):
        vals = [_num(r["values"][j]) for r in spec["rows"]]
        vals = [v for v in vals if v is not None]
        best.append((min(vals) if b == "lower" else max(vals)) if vals else None)
    for r in spec["rows"]:
        key = r.get("key")
        name = r["model"] + (" ★" if r.get("gm") else "")
        mc = Cell(md_text(name), tex_text(r["model"]) + ("~\\cite{" + key + "}" if key else "") + (r" $\star$" if r.get("gm") else ""), r["model"])
        cells = [mc]
        for j, v in enumerate(r["values"]):
            if v is None:
                cells.append(Cell(NR, NR, NR))
                continue
            is_best = best[j] is not None and _num(v) == best[j]
            md_v, tex_v = md_text(v), tex_text(v)
            cells.append(Cell(f"**{md_v}**" if is_best else md_v, f"\\textbf{{{tex_v}}}" if is_best else tex_v, csv_text(v)))
        t.add(cells)
    arrows = ", ".join(f"{h}: {'↑' if b == 'higher' else '↓'}" for h, b in zip(headers[1:], spec["better"]))
    t.notes = [f"Evidence level: {spec['evidence']} published results (same source paper, datasets, and protocol). "
               "Do not compare these numbers with other tables in this repository.",
               f"Direction: {arrows}. Bold = best value per column within this table; ★ = Graph Mamba / SSM-based model.",
               f"Survey interpretation: {spec['interpretation']}"]
    return t


def t_evidence_coverage(data: dict, resolved: list[dict]) -> Table:
    t = Table("evidence_coverage", "T11 · Evidence coverage and reporting gaps (derived)",
              "Kinds of evidence the survey reports for each architecture-level work (taxonomy and discussed models). "
              "Derived automatically; it exposes the reporting gaps discussed in sec:reproducibility.",
              ["Model", "Setting", "Complexity", "Efficiency evidence", "Expressivity result", "Benchmarks named",
               "Numeric results", "Limitations stated", "Challenge link"],
              "p{2.4cm}p{2.6cm}ccccccc", md_align=[":---", ":---"] + [":---:"] * 7)
    lk = lookup(data["taxonomy"])
    for r in resolved:
        if not (r["taxonomy"] or "discussed" in r["roles"]):
            continue
        setting = lk["setting"][r["taxonomy"]["setting"]].replace(" Graph Models", "") if r["taxonomy"] else "Discussed (Sec. 7)"
        t.add([model_cell(r), setting, Cell.check(r["complexity"] != NR), Cell.check(bool(r["efficiency"])),
               Cell.check(bool(r["expressivity"])), Cell.check(bool(r["benchmarks"])), Cell.check(bool(r["result_tables"])),
               Cell.check(bool(r["limitations"])), Cell.check(bool(r["challenges"]))])
    tax = [r for r in resolved if r["taxonomy"]]
    t.notes = [f"Of {len(tax)} classified architectures, {sum(r['complexity'] != NR for r in tax)} have a complexity statement, "
               f"{sum(bool(r['efficiency']) for r in tax)} efficiency evidence, {sum(bool(r['expressivity']) for r in tax)} an "
               f"expressivity result, and {sum(bool(r['result_tables']) for r in tax)} numeric results reported in the survey. "
               "Empty cell = not reported in the survey (NR)."]
    return t


def t_paper_index(data: dict, resolved: list[dict]) -> Table:
    lk = lookup(data["taxonomy"])
    t = Table("paper_index", "T12 · Index of reviewed works",
              "All works in the paper database with bibliographic metadata resolved from the survey bibliography.",
              ["Model", "BibTeX key", "Year", "Venue", "Role", "Category", "Link"],
              "p{2.4cm}p{3.0cm}c p{4.4cm}p{1.6cm}p{3.6cm}p{1.2cm}", long=True)
    for r in sorted(resolved, key=lambda x: (str(x["year"]), x["model"].lower())):
        if r["taxonomy"]:
            cat = lk["setting"][r["taxonomy"]["setting"]]
        elif r["application"]:
            cat = lk["subdomain"][r["application"]["subdomain"]]
        else:
            cat = "Discussed in Sec. 7"
        link = r["primary_link"]
        link_cell = Cell(f"[link]({link})" if link != NR else f"NR ([search]({r['search_link']}))",
                         f"\\url{{{link}}}" if link != NR else NR, link)
        t.add([model_cell(r), Cell(f"`{r['key']}`", "\\texttt{" + tex_text(r["key"]) + "}", r["key"]), r["year"],
               r["venue"], ", ".join(r["roles"]), cat, link_cell])
    t.notes = ["Link = DOI, arXiv, or publisher URL from the survey bibliography, or from data/links.yaml when the "
               "bibliography has none (each matched to the work by its exact title); NR when no link was found."]
    return t


TABLE_BUILDERS = [
    t_taxonomy_dimensions, t_unified_taxonomy, t_structural_tradeoffs, t_cross_domain, t_pattern_distribution,
    t_coupling_integration, t_benchmarks, t_efficiency, t_expressivity, t_future, t_evidence_coverage, t_paper_index,
]


def build_tables(data: dict, resolved: list[dict]) -> "OrderedDict[str, Table]":
    tables: "OrderedDict[str, Table]" = OrderedDict()
    for fn in TABLE_BUILDERS:
        tb = fn(data, resolved)
        tables[tb.id] = tb
    for spec in data["results"]:
        tb = t_performance(data, resolved, spec)
        tables[tb.id] = tb
    return tables
