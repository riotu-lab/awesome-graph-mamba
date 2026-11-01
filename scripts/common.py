"""Shared utilities for the Graph Mamba survey repository pipeline.

Everything that touches files lives here so that the generators can be
pure functions (data -> {path: content}), which in turn lets
``validate.py`` check that committed outputs are up to date.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TEX = ROOT / "source" / "main.tex"
SOURCE_BIB = ROOT / "source" / "references.bib"
DATA = ROOT / "data"
GENERATED = DATA / "generated"
# Committed snapshots used when the private manuscript sources are absent (e.g. in CI).
SNAPSHOT_EXTRACTION = GENERATED / "tex_extraction.json"
SNAPSHOT_BIB = GENERATED / "bibliography.json"
BIB_FIELDS = ("ENTRYTYPE", "ID", "title", "author", "year", "journal", "booktitle", "publisher", "howpublished",
              "school", "institution", "doi", "eprint", "archiveprefix", "note", "url")
DOCS = ROOT / "docs"

NR = "NR"


# ---------------------------------------------------------------------------
# YAML loading with duplicate-key detection
# ---------------------------------------------------------------------------
class DuplicateKeyError(ValueError):
    pass


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise DuplicateKeyError(
                f"Duplicate key '{key}' at line {key_node.start_mark.line + 1}"
            )
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def load_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_UniqueKeyLoader)


def load_data() -> dict:
    """Load every curated data file into one dictionary."""
    return {
        "taxonomy": load_yaml(DATA / "taxonomy.yaml"),
        "papers": load_yaml(DATA / "papers.yaml")["papers"],
        "benchmarks": load_yaml(DATA / "benchmarks.yaml"),
        "results": load_yaml(DATA / "results.yaml")["tables"],
        "challenges": load_yaml(DATA / "challenges.yaml")["challenges"],
        "links": (load_yaml(DATA / "links.yaml") or {}).get("links", {}) if (DATA / "links.yaml").exists() else {},
        "dataset_links": (load_yaml(DATA / "links.yaml") or {}).get("datasets", {}) if (DATA / "links.yaml").exists() else {},
        "figures": load_yaml(DATA / "figures.yaml")["figures"] if (DATA / "figures.yaml").exists() else [],
    }


# ---------------------------------------------------------------------------
# BibTeX
# ---------------------------------------------------------------------------
def sources_available() -> bool:
    """True when the manuscript sources (kept out of the public repository) are present locally."""
    return SOURCE_TEX.exists() and SOURCE_BIB.exists()


def bib_snapshot(bib: dict[str, dict], data: dict) -> dict[str, dict]:
    """Subset of the bibliography needed to build the repository: only the works referenced in data/,
    and only the fields the generators read."""
    keys = {p["key"] for p in data["papers"]}
    keys |= {k for t in data["results"] for r in t["rows"] for k in str(r.get("key", "")).split(",") if k}
    keys |= {e["key"] for c in data["challenges"] for e in c["early_work"]}
    return {k: {f: bib[k][f] for f in BIB_FIELDS if f in bib[k]} for k in sorted(keys) if k in bib}


def load_bib(path: Path | None = None) -> dict[str, dict]:
    """Parse references.bib, or fall back to the committed snapshot when the source is absent."""
    path = path or SOURCE_BIB
    if not path.exists():
        return json.loads(SNAPSHOT_BIB.read_text(encoding="utf-8"))
    import logging

    import bibtexparser
    from bibtexparser.bparser import BibTexParser

    logging.getLogger("bibtexparser").setLevel(logging.ERROR)
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parser.homogenize_fields = False
    with open(path, encoding="utf-8") as fh:
        db = bibtexparser.load(fh, parser=parser)
    entries: dict[str, dict] = {}
    for e in db.entries:
        entries[e["ID"]] = e
    return entries


def bib_duplicate_ids(path: Path | None = None) -> list[str]:
    path = path or SOURCE_BIB
    if not path.exists():
        return []
    ids = re.findall(r"^\s*@\w+\s*\{\s*([^,\s]+)\s*,", path.read_text(encoding="utf-8"), re.M)
    seen, dups = set(), []
    for i in ids:
        if i in seen:
            dups.append(i)
        seen.add(i)
    return dups


_ACCENTS = {
    "'": {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú", "c": "ć", "n": "ń", "s": "ś", "z": "ź", "y": "ý",
          "A": "Á", "E": "É", "I": "Í", "O": "Ó", "U": "Ú", "C": "Ć", "S": "Ś", "Z": "Ź"},
    "`": {"a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù", "A": "À", "E": "È"},
    '"': {"a": "ä", "e": "ë", "i": "ï", "o": "ö", "u": "ü", "A": "Ä", "O": "Ö", "U": "Ü"},
    "^": {"a": "â", "e": "ê", "i": "î", "o": "ô", "u": "û"},
    "~": {"a": "ã", "n": "ñ", "o": "õ", "N": "Ñ"},
    "c": {"c": "ç", "C": "Ç", "s": "ş", "S": "Ş"},
    "v": {"c": "č", "s": "š", "z": "ž", "r": "ř", "e": "ě", "C": "Č", "S": "Š", "Z": "Ž"},
}


def latex_to_text(s: str | None) -> str:
    """Convert the small subset of LaTeX found in BibTeX fields to plain text."""
    if not s:
        return ""
    s = re.sub(r"\\([`'\"^~])\s*\{?\\?([A-Za-z])\}?", lambda m: _ACCENTS.get(m.group(1), {}).get(m.group(2), m.group(2)), s)
    s = re.sub(r"\\([cv])\s*\{([A-Za-z])\}", lambda m: _ACCENTS.get(m.group(1), {}).get(m.group(2), m.group(2)), s)
    s = s.replace("\\&", "&").replace("\\%", "%").replace("\\_", "_").replace("\\textendash", "–")
    s = s.replace("---", "—").replace("--", "–")
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)  # drop remaining commands
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def format_authors(raw: str | None, max_authors: int | None = None) -> str:
    if not raw:
        return NR
    parts = [p.strip() for p in re.split(r"\s+and\s+", raw.replace("\n", " ")) if p.strip()]
    names = []
    for p in parts:
        p = latex_to_text(p)
        if p.lower() == "others":
            names.append("et al.")
            continue
        if "," in p:
            last, first = [x.strip() for x in p.split(",", 1)]
            names.append(f"{first} {last}".strip())
        else:
            names.append(p)
    if max_authors and len(names) > max_authors:
        names = names[:max_authors] + ["et al."]
    return ", ".join(names)


ARXIV_RE = re.compile(r"arXiv[:\s]*([0-9]{4}\.[0-9]{4,5})(v\d+)?", re.I)


def bib_links(entry: dict) -> dict:
    """Links derivable from the BibTeX entry only (no external lookup)."""
    links: dict[str, str] = {}
    doi = entry.get("doi", "").strip()
    if doi:
        doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
        links["doi"] = f"https://doi.org/{doi}"
    blob = " ".join(entry.get(f, "") for f in ("journal", "eprint", "note", "url", "howpublished", "archiveprefix"))
    m = ARXIV_RE.search(blob)
    if not m and entry.get("eprint") and re.fullmatch(r"[0-9]{4}\.[0-9]{4,5}", entry["eprint"].strip()):
        links["arxiv"] = f"https://arxiv.org/abs/{entry['eprint'].strip()}"
    elif m:
        links["arxiv"] = f"https://arxiv.org/abs/{m.group(1)}"
    url = entry.get("url", "").strip()
    if url and "arxiv.org" not in url and "doi.org" not in url:
        links["url"] = url
    return links


def scholar_search(title: str) -> str:
    return "https://scholar.google.com/scholar?q=" + urllib.parse.quote_plus(f'"{title}"')


def bib_venue(entry: dict) -> str:
    for f in ("journal", "booktitle", "publisher", "howpublished", "school", "institution"):
        if entry.get(f):
            return latex_to_text(entry[f])
    return NR


# ---------------------------------------------------------------------------
# LaTeX manuscript parsing
# ---------------------------------------------------------------------------
def strip_comments(tex: str) -> str:
    """Remove LaTeX comments (keeping escaped percent signs)."""
    return "\n".join(re.sub(r"(?<!\\)%.*$", "", line) for line in tex.splitlines())


CITE_RE = re.compile(r"\\cite[tp]?\*?(?:\[[^\]]*\])?\{([^}]*)\}")


def cite_keys(text: str) -> list[str]:
    keys: list[str] = []
    for group in CITE_RE.findall(text):
        for k in group.split(","):
            k = k.strip()
            if k and "#" not in k:  # skip macro parameters such as \cite{#3}
                keys.append(k)
    return keys


def section_numbers(tex: str) -> dict[str, dict]:
    """Map section/subsection labels to their printed number and title."""
    tex = strip_comments(tex)
    lines = tex.splitlines()
    sec = sub = 0
    appendix = False
    current = None
    since = 99
    out: dict[str, dict] = {}
    for line in lines:
        if "\\appendix" in line:
            appendix, sec, sub = True, 0, 0
        m = re.search(r"\\(section|subsection|subsubsection)(\*?)\{(.*)\}", line)
        if m:
            kind, star, title = m.groups()
            if not star:
                if kind == "section":
                    sec, sub = sec + 1, 0
                elif kind == "subsection":
                    sub += 1
            prefix = chr(ord("A") + sec - 1) if appendix else str(sec)
            num = prefix if kind == "section" else f"{prefix}.{sub}"
            current = {"number": num, "title": latex_to_text(title), "kind": kind}
            since = 0
            continue
        since += 1
        lm = re.search(r"\\label\{([^}]+)\}", line)
        if lm and current and since <= 2:
            out[lm.group(1)] = current
    return out


def cite_sections(tex: str) -> dict[str, list[str]]:
    """For each cite key, the list of section numbers in which it is cited."""
    tex = strip_comments(tex)
    sec = sub = 0
    appendix = False
    cur = "0"
    out: dict[str, list[str]] = {}
    for line in tex.splitlines():
        if "\\appendix" in line:
            appendix, sec, sub = True, 0, 0
        m = re.search(r"\\(section|subsection)(\*?)\{", line)
        if m and not m.group(2):
            if m.group(1) == "section":
                sec, sub = sec + 1, 0
            else:
                sub += 1
            p = chr(ord("A") + sec - 1) if appendix else str(sec)
            cur = p if sub == 0 else f"{p}.{sub}"
        for k in cite_keys(line):
            out.setdefault(k, [])
            if cur not in out[k]:
                out[k].append(cur)
    return out


def extract_environment_by_label(tex: str, label: str) -> str | None:
    """Return the body of the table/longtable environment containing ``label``."""
    tex = strip_comments(tex)
    idx = tex.find("\\label{" + label + "}")
    if idx < 0:
        return None
    starts = [m.start() for m in re.finditer(r"\\begin\{(table\*?|longtable|sidewaystable)\}", tex[:idx])]
    if not starts:
        return None
    start = starts[-1]
    env = re.match(r"\\begin\{([^}]+)\}", tex[start:]).group(1)
    end = tex.find("\\end{" + env + "}", idx)
    return tex[start:end]


# ---------------------------------------------------------------------------
# Text conversion helpers for outputs
# ---------------------------------------------------------------------------
def md_text(s: Any) -> str:
    """Manuscript-style string -> Markdown (en/em dashes, pipe-safe)."""
    if s is None or s == "":
        return NR
    parts = re.split(r"(\$[^$]+\$)", str(s))
    out = []
    for p in parts:
        if p.startswith("$") and p.endswith("$") and len(p) > 1:
            out.append(p)
        else:
            p = p.replace("---", "—").replace("--", "–")
            p = p.replace("Delta_t", "Δ_t").replace("Delta", "Δ")
            out.append(p.replace("|", "\\|"))
    return "".join(out).replace("\n", " ")


_TEX_ESC = {"&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_"}
_TEX_REPL = {
    "±": r"$\pm$", "—": "---", "–": "--", "†": r"$^{\dagger}$", "◆": r"$^{\blacklozenge}$",
    "Δ": r"$\Delta$", "≥": r"$\geq$", "✓": r"\cmark", "⚠": r"$^{\ast}$", "~": r"\textasciitilde{}",
    "★": r"$\star$", "↑": r"$\uparrow$", "↓": r"$\downarrow$", "·": r"$\cdot$", "×": r"$\times$",
    "→": r"$\rightarrow$", "é": r"\'e", "ö": r"\"o", "ü": r"\"u", "á": r"\'a", "ó": r"\'o", "í": r"\'i",
}


def _tex_plain(s: str) -> str:
    s = "".join(_TEX_ESC.get(ch, ch) for ch in s)
    for k, v in _TEX_REPL.items():
        s = s.replace(k, v)
    s = re.sub(r"\bB_t\b|\bB\\_t\b", r"$B_t$", s)
    s = re.sub(r"\bC\\_t\b", r"$C_t$", s)
    s = s.replace("Delta\\_t", r"$\Delta_t$")
    return s


def tex_text(s: Any) -> str:
    """Plain string -> LaTeX-safe string. Inline math ($...$) is kept verbatim."""
    if s is None or s == "":
        return NR
    parts = re.split(r"(\$[^$]+\$)", str(s))
    return "".join(p if p.startswith("$") and p.endswith("$") and len(p) > 1 else _tex_plain(p) for p in parts)


def csv_text(s: Any) -> str:
    if s is None or s == "":
        return NR
    return str(s).replace("---", "—").replace("--", "–")


def write_outputs(outputs: dict[Path, str]) -> list[Path]:
    """Write files whose content changed; return the list of written paths."""
    written = []
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
            written.append(path)
    return written


def dump_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
