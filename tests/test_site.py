"""Regression tests for the GitHub Pages site (docs/index.html) and for building without
the private manuscript sources.

Static tests inspect the generated page and its embedded payload. Browser tests drive
the real page in headless Chrome/Chromium (skipped when no browser is installed): a
probe script is appended to a copy of the page, performs the interactions, and writes
its observations as JSON into the DOM, which ``--dump-dom`` returns.
"""
import html as htmllib
from html import escape as html_escape
import json
import re
import shutil
import subprocess

import pytest

import common
from common import DOCS, ROOT, load_yaml

INDEX = DOCS / "index.html"


def payload():
    html = INDEX.read_text(encoding="utf-8")
    return json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))


# ---------------------------------------------------------------------------
# Building without the manuscript sources (as in CI)
# ---------------------------------------------------------------------------
def test_build_without_sources_matches_full_build(monkeypatch, tmp_path):
    from build import collect_outputs
    full, _ = collect_outputs()
    monkeypatch.setattr(common, "SOURCE_TEX", tmp_path / "missing.tex")
    monkeypatch.setattr(common, "SOURCE_BIB", tmp_path / "missing.bib")
    assert not common.sources_available()
    snap, ctx = collect_outputs()
    assert snap.keys() == full.keys()
    assert [p for p in full if full[p] != snap[p]] == []
    assert not [f for f in ctx["findings"] if f.severity == "error"]


def test_bibliography_snapshot_is_minimal():
    snap = json.loads((ROOT / "data" / "generated" / "bibliography.json").read_text(encoding="utf-8"))
    data = common.load_data()
    assert {p["key"] for p in data["papers"]} <= set(snap)
    assert all(set(e) <= set(common.BIB_FIELDS) for e in snap.values())


def test_manuscript_sources_are_not_published():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "source/main.tex" in ignored and "source/references.bib" in ignored


# ---------------------------------------------------------------------------
# Static checks
# ---------------------------------------------------------------------------
def test_navigation_views_present():
    html = INDEX.read_text(encoding="utf-8")
    for view, label in [("home", "Home"), ("tables", "Tables")]:
        assert f'id="view-{view}"' in html
        assert f'<a href="#{view}" data-view="{view}">{label}</a>' in html
    assert 'id="view-papers"' not in html and 'data-view="papers"' not in html


def test_embedded_tables_match_built_tables():
    from build import collect_outputs
    from generate_site import HIDDEN_TABLES
    _, ctx = collect_outputs()
    built = {k: v for k, v in ctx["tables"].items() if k not in HIDDEN_TABLES}
    tables = payload()["tables"]
    assert [t["id"] for t in tables] == list(built)
    for t in tables:
        assert sum(isinstance(r, list) for r in t["rows"]) == sum(not isinstance(r, tuple) for r in built[t["id"]].rows), t["id"]
        width = len(t["headers"])
        assert all(len(r) == width for r in t["rows"] if isinstance(r, list)), t["id"]


def test_table_cells_keep_survey_markers_and_best_values():
    tabs = {t["id"]: t for t in payload()["tables"]}
    models = [r[0]["t"] for r in tabs["paper_index"]["rows"] if isinstance(r, list)]
    assert any(m.endswith("†") for m in models)
    perf = [r for r in tabs["perf_brain"]["rows"] if isinstance(r, list)]
    assert any(r[0]["t"].endswith("★") for r in perf)
    assert sum(c.get("best", False) for r in perf for c in r) >= 1


def test_definitions_come_from_taxonomy_yaml():
    tx = load_yaml(ROOT / "data" / "taxonomy.yaml")
    p = payload()
    assert p["dimensions"] == tx["dimensions"]
    assert p["patterns"] == tx["design_patterns"]
    assert p["abbreviations"] == tx["abbreviations"]


def test_citation_comes_from_citation_cff():
    cff = load_yaml(ROOT / "CITATION.cff")["preferred-citation"]
    bib = payload()["citation"]
    assert cff["title"] in bib and cff["journal"] in bib and str(cff["year"]) in bib
    assert all(a["family-names"] in bib for a in cff["authors"])
    assert "doi" not in bib.lower() or cff.get("doi")


def test_paper_index_hides_bibtex_keys_on_site():
    t = next(x for x in payload()["tables"] if x["id"] == "paper_index")
    assert "BibTeX key" not in t["headers"]
    assert all(len(r) == len(t["headers"]) for r in t["rows"] if isinstance(r, list))



def test_links_file_fills_gaps_only():
    links = load_yaml(ROOT / "data" / "links.yaml")["links"]
    papers = {x["key"]: x for x in payload()["papers"]}
    assert set(links) <= set(papers)
    for key, entry in links.items():
        (kind, value), = entry.items()
        assert kind in ("doi", "arxiv", "url")
        assert value in (papers[key]["doi"] + papers[key]["arxiv"] + papers[key]["url"]) or papers[key]["doi"] != "NR", key
    bib = json.loads((ROOT / "data" / "generated" / "bibliography.json").read_text(encoding="utf-8"))
    assert not any(bib.get(k, {}).get("doi") for k in links), "links.yaml must not override the bibliography"


def test_abstract_and_research_questions_from_taxonomy_yaml():
    tx = load_yaml(ROOT / "data" / "taxonomy.yaml")
    p = payload()
    assert p["survey"]["abstract"] == tx["survey"]["abstract"]
    assert [q["id"] for q in p["researchQuestions"]] == [q["id"] for q in tx["research_questions"]]
    assert all(all(q["sections"]) for q in p["researchQuestions"])


def test_table_links_are_external_or_in_site():
    for t in payload()["tables"]:
        for r in t["rows"]:
            if not isinstance(r, list):
                continue
            for c in r:
                hrefs = [c.get("href")] + [x.get("href") for x in c.get("parts", [])]
                assert all(h.startswith(("http://", "https://")) for h in hrefs if h), (t["id"], c)


def test_every_benchmark_dataset_has_a_source_link():
    data = common.load_data()
    t7 = next(t for t in payload()["tables"] if t["id"] == "benchmark_summary")
    rows = [r for r in t7["rows"] if isinstance(r, list)]
    for row, b in zip(rows, data["benchmarks"]["benchmarks"]):
        assert [x["t"] for x in row[0]["parts"]] == b["datasets"]
        assert all(x.get("href") for x in row[0]["parts"]), b["id"]
        assert all(x.get("href") for x in row[4]["parts"]), b["id"]


def test_site_tables_are_numbered_without_gaps():
    nums = [int(re.match(r"^T(\d+) · ", t["title"]).group(1)) for t in payload()["tables"] if re.match(r"^T\d+ · ", t["title"])]
    assert nums == list(range(1, len(nums) + 1))


def test_survey_figures_on_home():
    html = INDEX.read_text(encoding="utf-8")
    figs = load_yaml(ROOT / "data" / "figures.yaml")["figures"]
    for f in figs:
        assert f'id="fig-{f["id"]}"' in html and f["caption"].replace("'", "&#x27;") in html, f["id"]
    assert "__FIGURES_TOP__" not in html and "__FIGURE_LANDSCAPE__" not in html


def test_landscape_lists_every_application_with_a_link():
    import site_figures
    from build import collect_outputs
    _, ctx = collect_outputs()
    land = site_figures.fig_landscape(ctx["resolved"])
    apps = [r for r in ctx["resolved"] if r["application"]]
    assert land.count("<li>") == len(apps)
    assert land.count('target="_blank"') == sum(r["primary_link"] != "NR" for r in apps)
    for r in apps:
        assert html_escape(r["model"].replace("--", "–")) in land, r["key"]


def test_figure_links_point_to_papers():
    html = INDEX.read_text(encoding="utf-8")
    block = html[html.index('id="fig-serialization"'):html.index('id="fig-design-patterns"')]
    hrefs = re.findall(r'<a href="([^"]+)"', block)
    assert len(hrefs) == 9 and all(h.startswith("https://") for h in hrefs)


def test_comparison_page_redirects_to_tables_view():
    html = (DOCS / "comparison.html").read_text(encoding="utf-8")
    assert 'http-equiv="refresh"' in html and 'href="./#tables"' in html


# ---------------------------------------------------------------------------
# Browser checks
# ---------------------------------------------------------------------------
CHROME = next((shutil.which(b) for b in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
               if shutil.which(b)), None)
needs_browser = pytest.mark.skipif(CHROME is None, reason="no headless Chrome/Chromium available")

PROBE = r"""
<script>
(async function(){
  const R = {}, $ = id => document.getElementById(id);
  const tick = (ms) => new Promise(r => setTimeout(r, ms || 0));
  const go = async h => { location.hash = h; await tick(20); };
  const D = JSON.parse($("data").textContent), P = D.papers;
  const visible = el => !!el && !el.closest("[hidden]");
  const overflow = () => document.documentElement.scrollWidth - window.innerWidth;
  const rowsOf = t => t.rows.filter(Array.isArray);
  try {
    // --- home ---
    R.overflow = {home: overflow()};
    R.kpis = [...document.querySelectorAll("#kpis b")].map(b => +b.textContent);
    R.heat = {};
    document.querySelectorAll("#figHeat .c").forEach(c => R.heat[c.dataset.lv + "|" + c.dataset.ty] = +c.textContent);
    R.yearTotal = [...document.querySelectorAll("#figYears .vbar .t")].reduce((s, t) => s + +t.textContent, 0);
    R.appTotal = [...document.querySelectorAll("#figApps .v")].reduce((s, t) => s + +t.textContent, 0);
    R.setTotal = [...document.querySelectorAll("#figSet .v")].reduce((s, t) => s + +t.textContent, 0);
    R.homeVisible = visible($("homeTitle"));
    R.treeLevels = {};
    document.querySelectorAll("#tree .leaf b").forEach(b => { const l = b.parentElement; R.treeLevels[l.firstChild.textContent.trim()] = +b.textContent; });
    R.treeHeads = [...document.querySelectorAll("#tree .bhead b")].map(b => +b.textContent);
    R.donutRole = [...document.querySelectorAll("#figRole .dlegend b")].map(b => parseInt(b.firstChild.textContent));
    R.donutVenue = [...document.querySelectorAll("#figVenue .dlegend b")].map(b => parseInt(b.firstChild.textContent));
    R.donutArcs = document.querySelectorAll("#figRole svg circle[data-tip]").length;
    R.challenges = document.querySelectorAll("#chal li").length;
    R.challengeLabels = /\b(tab|fig|sec|eq):/.test($("chal").textContent);
    R.bib = $("bib").textContent; R.bibExpected = D.citation;
    R.abstract = $("abstract").textContent;
    R.rqs = [...document.querySelectorAll("#rqs li b")].map(b => b.textContent);
    R.groupLabels = Object.fromEntries([...document.querySelectorAll("#tGroups [data-g]")].map(b => [b.dataset.g, b.firstChild.textContent]));

    // --- tables gallery: every table gets a visual type ---
    await go("tables");
    R.overflow.tables = overflow();
    R.navCurrent = document.querySelector('.nav a[aria-current="page"]').dataset.view;
    R.cards = document.querySelectorAll("#tCards .tcard").length;
    R.appendixApart = !!$("appSep") && [...$("appSep").nextElementSibling.querySelectorAll(".tcard")].map(b => b.dataset.t).sort().join() === D.results.map(r => r.id).sort().join();
    R.kinds = Object.fromEntries([...document.querySelectorAll("#tCards .tcard")].map(b => [b.dataset.t, b.querySelector(".kind").textContent]));
    document.querySelector('#tGroups [data-g="app:performance-tables"]').click();
    R.resultCards = [...document.querySelectorAll("#tCards .tcard")].map(b => b.dataset.t);
    document.querySelector('#tGroups [data-g=""]').click();

    // --- dot matrix (T2): dots = checkmarks, totals, expand a row, search ---
    document.querySelector('#tCards [data-t="unified_taxonomy"]').click(); await tick(20);
    R.hashTable = location.hash;
    R.overflow.matrix = overflow();
    const t2 = D.tables.find(x => x.id === "unified_taxonomy");
    R.dots = document.querySelectorAll("#tBody .dm tbody .d").length;
    R.checks = rowsOf(t2).flatMap(r => r).filter(c => c.t === "✓").length;
    R.totals = [...document.querySelectorAll("#tBody .dm tfoot td.dc b")].map(b => +b.textContent);
    R.totalsExpected = t2.headers.map((h, i) => i).filter(i => rowsOf(t2).some(r => r[i].t === "✓")).map(i => rowsOf(t2).filter(r => r[i].t === "✓").length);
    const btn = document.querySelector("#tBody .rowbtn"); btn.focus(); btn.click();
    R.expanded = document.querySelector('#tBody .rowbtn[data-row="0"]').getAttribute("aria-expanded");
    R.expandedText = document.querySelector("#tBody tr.more").textContent.includes(rowsOf(t2)[0][2].t);
    R.expandFocus = document.activeElement.dataset.row;
    const tq = $("tq"); tq.value = "bidirectional"; tq.dispatchEvent(new Event("input", {bubbles: true}));
    R.matrixSearch = document.querySelectorAll("#tBody .dm tbody tr:not(.grp):not(.more)").length;
    R.matrixSearchExpected = rowsOf(t2).filter(r => r.some(c => c.t.toLowerCase().includes("bidirectional"))).length;
    tq.value = ""; tq.dispatchEvent(new Event("input", {bubbles: true}));

    // --- table view of the same table: sort + downloads ---
    document.querySelector('.seg [data-v="table"]').click();
    R.tableRows = document.querySelectorAll("#tBody .ctab tbody tr:not(.grp)").length;
    R.tableExpected = rowsOf(t2).length;
    document.querySelector('#tBody [data-sort="1"]').click();
    document.querySelector('#tBody [data-sort="1"]').click();
    R.sortAttr = document.querySelector('#tBody th[aria-sort]').getAttribute("aria-sort");
    R.sortedYears = [...document.querySelectorAll("#tBody .ctab tbody tr")].map(r => +r.children[1].textContent);
    R.downloadButtons = document.querySelectorAll("[data-dl], .dls").length;
    R.captionHasLabels = /\b(tab|fig|sec|eq):/.test($("tDetail").textContent);

    // --- dominant vs secondary pattern (T4) ---
    await go("tables/cross_domain_applications");
    const t4 = D.tables.find(x => x.id === "cross_domain_applications");
    R.subDots = document.querySelectorAll("#tBody .dm .d.sub").length;
    R.subExpected = rowsOf(t4).filter(r => /\(/.test(r[r.length - 1].t)).length;

    // --- heatmap (T6): values and totals ---
    await go("tables/coupling_integration");
    R.overflow.heatmap = overflow();
    const t6 = D.tables.find(x => x.id === "coupling_integration");
    R.heatCells = [...document.querySelectorAll("#tBody .hm tbody tr:not(.grp) td")].map(td => td.firstChild ? td.firstChild.textContent : "");
    R.heatExpected = rowsOf(t6).flatMap(r => r.slice(1).map(c => c.t.replace(/\s*\(\+\d+\)$/, "")));
    R.heatSumRows = [...document.querySelectorAll("#tBody .hm tr.sum td")].every(td => td.classList.contains("tot"));
    await go("tables/pattern_distribution");
    R.abbrKeys = [...document.querySelectorAll("#tBody .abbr dt")].map(d => d.textContent);
    R.headerNames = [...document.querySelectorAll("#tBody .hm thead th small")].map(s => s.textContent);

    // --- T7: dataset and model links, readable result-table links ---
    await go("tables/benchmark_summary");
    document.querySelector('.seg [data-v="table"]').click();
    const t7 = D.tables.find(x => x.id === "benchmark_summary");
    R.t7DatasetLinks = [...document.querySelectorAll("#tBody .ctab tbody tr")].map(tr => tr.children[0].querySelectorAll("a").length);
    R.t7DatasetExpected = rowsOf(t7).map(r => r[0].parts.length);
    R.t7ResultLinks = [...document.querySelectorAll('#tBody .ctab a[href^="#tables/"]')].map(a => a.textContent);
    R.t7RawIds = /perf_[a-z]+/.test(document.querySelector("#tBody .ctab tbody").textContent);

    // --- cost equation (T3): equation first, then one card per design-question term ---
    await go("tables/structural_tradeoffs");
    R.eqTerms = [...document.querySelectorAll("#tBody .eqline .term b")].map(b => b.textContent);
    R.eqCards = [...document.querySelectorAll("#tBody .eqcard header b")].map(b => b.textContent);
    R.eqFirst = !!document.querySelector("#tBody > .eq:first-child");

    // --- cards (T1) ---
    await go("tables/taxonomy_dimensions");
    R.cardCount = document.querySelectorAll("#tBody .rcard").length;
    R.cardExpected = rowsOf(D.tables.find(x => x.id === "taxonomy_dimensions")).length;
    R.freeText = /Free text \(per model\)/.test($("tBody").textContent);

    // --- results chart + scoreboard ---
    await go("tables/perf_brain");
    const res = D.results.find(r => r.id === "perf_brain");
    R.chartBars = document.querySelectorAll("#tBody .rbars .bar").length;
    R.chartExpected = res.rows.filter(r => r.values[0] != null).length;
    R.chartGm = document.querySelectorAll("#tBody .rbars .bar.gm").length;
    R.gmExpected = res.rows.filter(r => r.gm && r.values[0] != null).length;
    R.chartBest = document.querySelector("#tBody .rbars .v.best").textContent;
    const vals = res.rows.map(r => parseFloat(r.values[0])).filter(v => !isNaN(v));
    R.bestExpected = res.better[0] === "lower" ? Math.min(...vals) : Math.max(...vals);
    R.score = [...document.querySelectorAll("#tBody .score b")].map(b => b.textContent);
    R.scoreExpected = res.rows.filter(r => r.gm).map(g => {
      const ks = res.columns.map((c, k) => k).filter(k => res.rows.some(x => x.values[k] != null));
      const best = k => { const v = res.rows.map(x => parseFloat(x.values[k])).filter(x => !isNaN(x)); return res.better[k] === "lower" ? Math.min(...v) : Math.max(...v); };
      return `${ks.filter(k => g.values[k] != null && parseFloat(g.values[k]) === best(k)).length} of ${ks.length}`;
    });
    document.querySelector('#tBody [data-col="1"]').click();
    R.chartCol = document.querySelector('#tBody [data-col][aria-pressed="true"]').dataset.col;
    R.overflow.chart = overflow();
    $("tBack").click(); await tick(20);
    R.backHash = location.hash; R.backFocus = document.activeElement.dataset.t;

    // --- old Papers links land on the tables ---
    await go("papers"); R.legacyPapers = location.hash === "#papers" && visible($("tablesTitle"));
    await go(P[3].key); R.legacyKey = visible($("tablesTitle"));
    await go("home");

    // --- GitHub only in the header; accessible names ---
    R.repoLinksOutsideHeader = [...document.querySelectorAll('a[href*="github.com"]')].filter(a => !a.closest(".site-header")).length;
    R.repoLinksInHeader = document.querySelectorAll('.site-header a[href*="github.com"]').length;
    R.unnamedButtons = [...document.querySelectorAll("button")].filter(b => !(b.getAttribute("aria-label") || b.textContent.trim())).length;
    R.unlabelledInputs = [...document.querySelectorAll("input,select")].filter(c => !(c.labels && c.labels.length) && !c.getAttribute("aria-label")).length;
  } catch (e) { R.error = String(e && e.stack || e); }
  const pre = document.createElement("pre"); pre.id = "probe-result"; pre.textContent = JSON.stringify(R);
  document.body.appendChild(pre);
})();
</script>
"""


def run_probe(tmp_path, width):
    page = tmp_path / "index.html"
    page.write_text(INDEX.read_text(encoding="utf-8").replace("</body>", PROBE + "</body>"), encoding="utf-8")
    out = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
                          f"--window-size={width},900", "--virtual-time-budget=8000", "--dump-dom", page.as_uri()],
                         capture_output=True, text=True, timeout=120)
    m = re.search(r'<pre id="probe-result">(.*?)</pre>', out.stdout, re.S)
    assert m, out.stderr[-2000:]
    r = json.loads(htmllib.unescape(m.group(1)))
    assert "error" not in r, r["error"]
    return r


@pytest.fixture(scope="module", params=[1366, 390], ids=["desktop", "mobile"])
def probe(request, tmp_path_factory):
    if CHROME is None:
        pytest.skip("no headless Chrome/Chromium available")
    return run_probe(tmp_path_factory.mktemp(f"site{request.param}"), request.param)


@needs_browser
def test_no_horizontal_page_scroll(probe):
    assert all(v <= 0 for v in probe["overflow"].values()), probe["overflow"]


@needs_browser
def test_home_figures_match_data(probe):
    p = payload()
    P = p["papers"]
    assert probe["homeVisible"]
    assert probe["kpis"] == [len(P), p["counts"]["taxonomy"], p["counts"]["application"], len(p["tables"])]
    arch = [x for x in P if x["taxonomy"]]
    for cell, n in probe["heat"].items():
        lv, ty = cell.split("|")
        assert n == sum(lv in x["taxonomy"]["d3"] and ty in x["taxonomy"]["d4"] for x in arch), cell
    assert len(probe["heat"]) == 12
    assert probe["yearTotal"] == len(P)
    assert probe["appTotal"] == p["counts"]["application"]
    assert probe["setTotal"] == p["counts"]["taxonomy"]


@needs_browser
def test_home_taxonomy_tree_donuts_challenges_citation(probe):
    p = payload()
    P = p["papers"]
    arch = [x for x in P if x["taxonomy"]]
    app = [x for x in P if x["application"]]
    assert probe["treeHeads"] == [len(arch), len(app), len(app)]
    for lv, label in p["labels"]["level"].items():
        assert probe["treeLevels"][label] == sum(lv in x["taxonomy"]["d3"] for x in arch), label
    for ty, label in p["labels"]["type"].items():
        assert probe["treeLevels"][label] == sum(ty in x["taxonomy"]["d4"] for x in arch), label
    for sd, label in p["labels"]["subdomain"].items():
        n = sum(x["application"]["subdomain"] == sd for x in app)
        if n:
            assert probe["treeLevels"][label] == n, label
    assert probe["donutRole"] == [p["counts"][r] for r in ("taxonomy", "application", "discussed")]
    assert probe["donutArcs"] == sum(1 for r in ("taxonomy", "application", "discussed") if p["counts"][r])
    assert sum(probe["donutVenue"]) == len(P)
    assert probe["challenges"] == len(p["challenges"]) and not probe["challengeLabels"]
    assert probe["bib"] == probe["bibExpected"]
    p_ = payload()
    assert probe["abstract"] == p_["survey"]["abstract"]
    assert probe["rqs"] == [q["id"] for q in p_["researchQuestions"]]
    for label, sec in p_["sections"].items():
        assert sec["title"] in probe["groupLabels"][label]


@needs_browser
def test_every_table_has_a_fitting_visual(probe):
    p = payload()
    assert probe["navCurrent"] == "tables"
    assert probe["cards"] == len(p["tables"])
    assert probe["appendixApart"]
    assert sorted(probe["resultCards"]) == sorted(r["id"] for r in p["results"])
    k = probe["kinds"]
    assert {k[x] for x in ("unified_taxonomy", "cross_domain_applications")} == {"Dot matrix"}
    assert "evidence_coverage" not in k
    assert {k[x] for x in ("pattern_distribution", "coupling_integration")} == {"Heatmap"}
    assert {k[x] for x in ("taxonomy_dimensions", "future_directions")} == {"Cards"}
    assert k["structural_tradeoffs"] == "Cost equation"
    assert {k[r["id"]] for r in p["results"]} == {"Bar chart"}


@needs_browser
def test_dot_matrix(probe):
    assert probe["hashTable"] == "#tables/unified_taxonomy"
    assert probe["dots"] == probe["checks"] > 0
    assert probe["totals"] == probe["totalsExpected"]
    assert probe["expanded"] == "true" and probe["expandedText"] and probe["expandFocus"] == "0"
    assert probe["matrixSearch"] == probe["matrixSearchExpected"] > 0
    assert probe["subDots"] == probe["subExpected"] > 0


@needs_browser
def test_table_view_sort_and_no_downloads(probe):
    assert probe["tableRows"] == probe["tableExpected"]
    assert probe["sortAttr"] == "descending"
    assert probe["sortedYears"] == sorted(probe["sortedYears"], reverse=True)
    assert probe["downloadButtons"] == 0
    assert not probe["captionHasLabels"]


@needs_browser
def test_benchmark_table_links(probe):
    assert probe["t7DatasetLinks"] == probe["t7DatasetExpected"]
    assert len(probe["t7ResultLinks"]) == 5 and not probe["t7RawIds"]


@needs_browser
def test_cost_equation_view(probe):
    eq = load_yaml(ROOT / "data" / "taxonomy.yaml")["cost_decomposition"].replace("_", "").replace(" ", "")
    assert "=".join(["".join(probe["eqTerms"][:1]), "+".join(probe["eqTerms"][1:])]) == eq
    assert probe["eqFirst"] and probe["eqCards"] == ["Ttoken", "Tserialize", "TSSM", "Tfusion"]


@needs_browser
def test_heatmap_and_cards(probe):
    assert probe["heatCells"] == probe["heatExpected"]
    assert probe["heatSumRows"]
    assert probe["abbrKeys"][:4] == ["DV", "RT", "GS", "LG"] and "+n" in probe["abbrKeys"]
    assert len(probe["headerNames"]) == 4
    assert probe["cardCount"] == probe["cardExpected"]
    assert not probe["freeText"]


@needs_browser
def test_results_chart_and_scoreboard(probe):
    assert probe["chartBars"] == probe["chartExpected"]
    assert probe["chartGm"] == probe["gmExpected"] >= 1
    assert float(probe["chartBest"].split("±")[0]) == probe["bestExpected"]
    assert probe["score"] == probe["scoreExpected"]
    assert probe["chartCol"] == "1"
    assert probe["backHash"] == "#tables" and probe["backFocus"] == "perf_brain"


@needs_browser
def test_old_papers_links_land_on_tables(probe):
    assert probe["legacyPapers"] and probe["legacyKey"]


@needs_browser
def test_repository_link_only_in_header(probe):
    assert probe["repoLinksInHeader"] == 1
    assert probe["repoLinksOutsideHeader"] == 0


@needs_browser
def test_controls_have_accessible_names(probe):
    assert probe["unnamedButtons"] == 0
    assert probe["unlabelledInputs"] == 0
