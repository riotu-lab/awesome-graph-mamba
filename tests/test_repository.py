"""Integration tests on the real manuscript, database, and generated outputs."""
import copy

import pytest

from build import collect_outputs, stale_outputs
from common import DuplicateKeyError, load_yaml
from quality import manuscript_consistency_findings, schema_findings, taxonomy_value_findings


@pytest.fixture(scope="module")
def built():
    return collect_outputs()


def test_counts_match_manuscript(built):
    _, ctx = built
    ex = ctx["extraction"]
    assert len(ex["unified_taxonomy"]) == 21
    assert len(ex["cross_domain_applications"]) == 30
    assert len(ex["design_pattern_figure"]) == 30
    assert not ex["cited_but_missing_in_bib"]


def test_every_classified_work_in_database(built):
    _, ctx = built
    db = {p["key"] for p in ctx["data"]["papers"]}
    assert set(ctx["extraction"]["classified_keys"]) <= db


def test_no_errors(built):
    _, ctx = built
    errors = [f for f in ctx["findings"] if f.severity == "error"]
    assert not errors, errors


def test_outputs_are_up_to_date(built):
    outputs, _ = built
    assert not stale_outputs(outputs), "run python scripts/build.py"


def test_missing_values_rendered_nr(built):
    _, ctx = built
    rows = [r for r in ctx["tables"]["perf_hsi"].rows if not isinstance(r, tuple)]
    ab_lstm = next(r for r in rows if r[0].csv == "AB-LSTM")
    assert ab_lstm[-1].csv == "NR"


def test_only_website_outputs_are_generated(built):
    outputs, _ = built
    rel = {p.relative_to(p.parents[1]).as_posix() if p.parent.name == "docs" else p.relative_to(p.parents[2]).as_posix()
           for p in outputs}
    assert rel == {"docs/index.html", "docs/comparison.html", "data/generated/tex_extraction.json",
                   "data/generated/bibliography.json"}


def test_performance_tables_single_source(built):
    _, ctx = built
    for t in ctx["data"]["results"]:
        assert t["source"] in {r.get("key") for r in t["rows"]}, f"{t['id']}: source paper must be a row"


def test_invalid_category_is_detected(built):
    _, ctx = built
    papers = copy.deepcopy(ctx["data"]["papers"])
    papers[0]["taxonomy"]["d3"] = ["quantum"]
    assert schema_findings(papers)
    assert taxonomy_value_findings(papers, ctx["data"]["taxonomy"])


def test_manuscript_mismatch_is_detected(built):
    _, ctx = built
    data = copy.deepcopy(ctx["data"])
    rec = next(p for p in data["papers"] if p["key"] == "huang2024can")
    rec["taxonomy"]["d4"] = ["parallel"]
    codes = [f.code for f in manuscript_consistency_findings(data, ctx["extraction"]) if f.key == "huang2024can"]
    assert "tex-mismatch" in codes


def test_verified_override_downgrades_to_warning(built):
    _, ctx = built
    data = copy.deepcopy(ctx["data"])
    rec = next(p for p in data["papers"] if p["key"] == "huang2024can")
    rec["taxonomy"]["d4"] = ["parallel"]
    rec["verification"] = {"status": "verified", "override_reason": "test"}
    f = [x for x in manuscript_consistency_findings(data, ctx["extraction"]) if x.key == "huang2024can"]
    assert f and all(x.severity == "warning" for x in f)


def test_duplicate_yaml_keys_rejected(tmp_path):
    p = tmp_path / "dup.yaml"
    p.write_text("a: 1\na: 2\n")
    with pytest.raises(DuplicateKeyError):
        load_yaml(p)


def test_merge_never_modifies_existing_records(tmp_path, built):
    from extract_papers import merge_stubs
    _, ctx = built
    src = (tmp_path / "papers.yaml")
    original = "papers:\n- key: huang2024can\n  model: GSSC-CUSTOM\n"
    src.write_text(original)
    added = merge_stubs(ctx["extraction"], src)
    text = src.read_text()
    assert text.startswith(original)
    assert "huang2024can" not in added and len(added) == 50
    assert "status: needs_verification" in text
    stubs = load_yaml(src)["papers"]
    assert stubs[0]["model"] == "GSSC-CUSTOM" and len(stubs) == 51


def test_site_embeds_every_work(built):
    import json
    import re
    outputs, ctx = built
    html = next(c for p, c in outputs.items() if p.name == "index.html")
    blob = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1)
    payload = json.loads(blob)
    assert {p["key"] for p in payload["papers"]} == {r["key"] for r in ctx["resolved"]}
    assert "__DATA__" not in html
