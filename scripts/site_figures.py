#!/usr/bin/env python3
"""Survey figures for the GitHub Pages site, re-implemented as inline SVG / HTML.

The manuscript draws these figures in TikZ. The site cannot run LaTeX, so the
figures are ported here with the same coordinates (TikZ ``x=0.01cm``: one SVG
unit = 0.01 cm, y pointing down). Every work cited in a figure becomes a link
to its paper, and the applications landscape is generated from the database so
it always matches the tables. Colours use the site's CSS variables, so the
figures follow the light/dark theme.
"""
from __future__ import annotations

import html
import math

PT = 3.528  # one TeX point expressed in figure units (0.01 cm)
NODE = {"blue": "#4c7bd9", "green": "#2f9e6a", "red": "#e0554f", "orange": "#ee8a2f", "purple": "#8b5fd0",
        "yellow": "#e2b52b", "gray": "#8d93a8", "light": "#b9c8f0"}
C = {k: f"var(--c{k})" for k in range(1, 7)}
INK, MUTED, EDGE, RULE = "var(--ink)", "var(--muted)", "var(--edge)", "var(--line)"
PAT_COLOR = {"DV": "var(--c1)", "RT": "var(--c2)", "GS": "var(--c3)", "LG": "var(--c4)"}
PAT_TEXT = {"DV": "#ffffff", "RT": "#1b1a33", "GS": "#1b1a33", "LG": "#1b1a33"}  # legible on each tag colour


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def tint(color: str, pct: int) -> str:
    return f"color-mix(in srgb,{color} {pct}%,var(--surface))"


# ---------------------------------------------------------------------------
# SVG primitives (TikZ-like)
# ---------------------------------------------------------------------------
def rect(x1, y1, x2, y2, fill="none", stroke="none", sw=0.0, rx=0, dash=None) -> str:
    st = f"fill:{fill};stroke:{stroke};stroke-width:{sw:.1f}" + (f";stroke-dasharray:{dash}" if dash else "")
    return f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{x2 - x1:.1f}" height="{y2 - y1:.1f}" rx="{rx}" style="{st}"/>'


def path(points, stroke=EDGE, sw=0.9 * PT, dash=None, arrow=None, close=False) -> str:
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points) + (" Z" if close else "")
    st = f"fill:none;stroke:{stroke};stroke-width:{sw:.1f};stroke-linecap:round;stroke-linejoin:round" + \
        (f";stroke-dasharray:{dash}" if dash else "")
    return f'<path d="{d}" style="{st}"' + (f' marker-end="url(#{arrow})"' if arrow else "") + "/>"


def edges(pairs, **kw) -> str:
    return "".join(path([a, b], **kw) for a, b in pairs)


def circle(x, y, r, fill, stroke="var(--surface)", sw=1.2 * PT) -> str:
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" style="fill:{fill};stroke:{stroke};stroke-width:{sw:.1f}"/>'


def text(x, y, s, pt=10.0, anchor="middle", weight=400, fill=INK, italic=False, raw=False, lh=1.28) -> str:
    """Multi-line text centred vertically on y (TikZ node semantics); ``anchor`` is start/middle/end."""
    lines = s.split("\n")
    size = pt * PT
    y0 = y - (len(lines) - 1) * size * lh / 2
    st = f"font-size:{size:.1f}px;font-weight:{weight};fill:{fill}" + (";font-style:italic" if italic else "")
    spans = "".join(f'<tspan x="{x:.1f}" y="{y0 + i * size * lh:.1f}">{ln if raw else esc(ln)}</tspan>'
                    for i, ln in enumerate(lines))
    return f'<text text-anchor="{anchor}" dominant-baseline="central" style="{st}">{spans}</text>'


def node(x, y, color, r=15.0, label="", pt=6.5) -> str:
    out = circle(x, y, r, color)
    if label:
        out += text(x, y, label, pt, weight=700, fill="#ffffff")
    return out


def link(href: str | None, inner: str) -> str:
    return f'<a href="{esc(href)}" target="_blank" rel="noopener">{inner}</a>' if href else inner


def svg(w, h, body, label, fid) -> str:
    defs = (f'<defs><marker id="ah-{fid}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="5" markerHeight="5" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" style="fill:{INK}"/></marker></defs>')
    return (f'<svg class="sfig-svg" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}" '
            f'xmlns="http://www.w3.org/2000/svg">{defs}{body}</svg>')


def shadow_rect(x1, y1, x2, y2, rx, dx=4, dy=5, pct=22) -> str:
    return rect(x1 + dx, y1 + dy, x2 + dx, y2 + dy, fill=f"color-mix(in srgb,var(--c6) {pct}%,transparent)", rx=rx)


# ---------------------------------------------------------------------------
# Figure: graph settings (fig:graph-types)
# ---------------------------------------------------------------------------
G7 = {"A": (0, 0), "B": (142, -41), "C": (274, 19), "D": (173, 59), "E": (76, 88), "F": (77, 178), "G": (230, 157)}
G7_EDGES = [("A", "B"), ("A", "E"), ("B", "C"), ("C", "D"), ("D", "E"), ("C", "G"), ("E", "F"), ("F", "G")]


def gseven(sx, sy, s, colors, alt_dashed=False) -> str:
    p = {k: (sx + s * x, sy + s * y) for k, (x, y) in G7.items()}
    out = edges([(p[a], p[b]) for a, b in G7_EDGES])
    out += edges([(p["B"], p["D"]), (p["C"], p["D"])], dash="9 7" if alt_dashed else None)
    for k, col in zip("ABCDEFG", colors):
        out += node(*p[k], NODE[col], r=15)
    return out


def panelbox(x1, y1, x2, y2, color) -> str:
    return rect(x1, y1, x2, y2, fill="var(--surface)", stroke=f"color-mix(in srgb,{color} 70%,transparent)",
                sw=1.3 * PT, rx=15)


def pill(x1, x2, y1, y2, color, label) -> str:
    return (rect(x1 + 4, y1 + 5, x2 + 4, y2 + 5, fill="color-mix(in srgb,var(--c6) 30%,transparent)")
            + rect(x1, y1, x2, y2, fill=color) + text(x1 + 22, (y1 + y2) / 2, label, 13.2, "start", 700, "#ffffff"))


def legcard(x1, y1, x2, y2) -> str:
    return shadow_rect(x1, y1, x2, y2, 8) + rect(x1, y1, x2, y2, fill="var(--surface)", stroke=RULE, sw=0.8 * PT, rx=8)


def fig_graph_types() -> str:
    b = []
    a = b.append
    # 1. static
    a(panelbox(12, 25, 735, 385, C[1])); a(pill(30, 435, 13, 73, C[1], "1. Static Graph"))
    a(gseven(50, 155, 0.8, ["blue"] * 7))
    a(text(320, 180, "The structure and\nfeatures of the graph\nremain unchanged\nover time.", 10.4, "start"))
    a(node(330, 335, NODE["blue"], 14)); a(text(355, 335, "Node", 9.2, "start"))
    a(path([(460, 335), (498, 335)])); a(text(515, 335, "Edge", 9.2, "start"))
    # 2. dynamic
    a(panelbox(757, 25, 2322, 385, C[2])); a(pill(1097, 1673, 13, 73, C[2], "2. Dynamic Graph"))
    a(path([(1113, 95), (1113, 295)], stroke=MUTED, sw=0.9 * PT, dash="10 8"))
    a(path([(1585, 95), (1585, 295)], stroke=MUTED, sw=0.9 * PT, dash="10 8"))
    a(gseven(834, 130, 0.8, ["blue"] * 7))
    dyn = ["blue", "blue", "blue", "blue", "blue", "green", "blue"]
    a(gseven(1218, 130, 0.8, dyn, True)); a(gseven(1690, 130, 0.8, dyn, True))
    for x, lab in [(953, "Time t"), (1352, "Time t+1"), (1808, "Time t′")]:
        a(text(x, 310, lab, 10.6))
    a(legcard(1970, 90, 2312, 330)); a(text(2141, 115, "Legend", 12, weight=700))
    a(node(2007, 157, NODE["blue"], 13)); a(text(2057, 157, "Existing node", 9.2, "start"))
    a(node(2007, 202, NODE["green"], 13)); a(text(2057, 202, "New node", 9.2, "start"))
    a(path([(1985, 247), (2022, 247)])); a(text(2057, 247, "Existing edge", 9.2, "start"))
    a(path([(1985, 292), (2022, 292)], dash="9 7")); a(text(2057, 292, "Removed edge", 9.2, "start"))
    a(text(1530, 355, "Nodes and/or edges may appear, disappear, or change over time.", 12.6, weight=700, fill=C[2]))
    # 3. homogeneous
    a(panelbox(12, 405, 735, 765, C[3])); a(pill(30, 673, 393, 453, C[3], "3. Homogeneous Graph"))
    a(gseven(55, 545, 0.8, ["blue"] * 7))
    a(text(330, 565, "All nodes and edges\nare of the same type\nand described by the\nsame attributes.", 10.2, "start"))
    a(node(345, 695, NODE["blue"], 14)); a(text(372, 695, "Node (single type)", 9.2, "start"))
    a(path([(326, 735), (364, 735)])); a(text(372, 735, "Edge (single type)", 9.2, "start"))
    # 4. heterogeneous
    a(panelbox(757, 405, 2322, 765, C[4])); a(pill(1060, 1740, 393, 453, C[4], "4. Heterogeneous Graph"))
    a(shadow_rect(1800, 418, 2168, 463, 6, 4, 5)); a(rect(1800, 418, 2168, 463, fill=tint(C[4], 18), stroke=C[4], sw=PT, rx=6))
    a(text(1984, 440, "Real-world example", 9.8, weight=700, fill=C[4]))
    a(gseven(800, 545, 0.8, ["blue", "green", "gray", "blue", "blue", "gray", "green"]))
    a(text(1045, 530, "Multiple types of nodes\nand/or edges with different\nattributes and relations.", 10.2, "start"))
    for y, col, lab in [(628, "blue", "Type A node"), (670, "green", "Type B node"), (712, "gray", "Type C node")]:
        a(node(1060, y, NODE[col], 13)); a(text(1082, y, lab, 9.2, "start"))
    for y, col, lab in [(628, EDGE, "Relation type 1"), (670, C[1], "Relation type 2"), (712, C[3], "Relation type 3")]:
        a(path([(1290, y), (1325, y)], stroke=col)); a(text(1340, y, lab, 9.2, "start"))
    a(path([(1595, 470), (1595, 755)], stroke=MUTED, sw=0.9 * PT, dash="10 8"))

    def T(x, y):  # scope shift={(20,-28.5)}, yscale=0.83
        return (x + 20, -28.5 + 0.83 * y)
    a(path([T(1686, 663), T(1843, 640)], sw=PT)); a(path([T(1897, 640), T(2126, 645)], stroke=C[1], sw=PT))
    a(path([T(1687, 710), T(2140, 776)], stroke=C[3], sw=PT)); a(path([T(1672, 716), T(1700, 815)], sw=PT, dash="9 7"))
    a(path([T(2140, 796), T(1940, 866)], sw=PT))
    for xa, ya, xb, yb in [(1843, 603, 1897, 677), (2136, 606, 2205, 663), (1672, 833, 1740, 890), (1876, 829, 1930, 900)]:
        (p1, p2) = T(xa, ya), T(xb, yb)
        a(rect(p1[0], p1[1], p2[0], p2[1], fill=tint(C[6], 18), stroke=MUTED, sw=PT))
    a(node(*T(1664, 689), NODE["purple"], 17)); a(node(*T(2164, 779), NODE["purple"], 17))
    for x, y, lab in [(1777, 621, "Work in"), (2036, 623, "Located in"), (1988, 744, "Send email"),
                      (1632, 788, "Live in"), (2040, 876, "Connected to")]:
        a(text(*T(x, y), lab, 8.4, fill=MUTED))
    for x, y, lab in [(1624, 721, "User"), (1904, 705, "Company"), (2172, 703, "Home"), (2168, 825, "User"),
                      (1707, 922, "Home"), (1933, 922, "Company")]:
        a(text(*T(x, y), lab, 8.8))
    # 5. spatio-temporal (scope shift y -213)
    def S(y):
        return y - 213
    a(panelbox(12, S(998), 2322, S(1375), C[5])); a(pill(30, 711, S(992), S(1052), C[5], "5. Spatio-Temporal Graph"))
    for y in (1110, 1198, 1295):
        a(rect(72, S(y - 10), 405, S(y + 10), fill="color-mix(in srgb,var(--c6) 20%,transparent)"))
    for x in (145, 348):
        a(rect(x - 11, S(1098), x + 11, S(1300), fill="color-mix(in srgb,var(--c6) 20%,transparent)"))
    for x, y, lab in [(120, 1093, "1"), (334, 1093, "4"), (222, 1201, "3"), (118, 1294, "2"), (335, 1294, "5")]:
        a(node(x, S(y), NODE["blue"], 17, lab, 7))
    a(text(463, S(1163), "Nodes are associated\nwith spatial locations,\nand the graph evolves\nover time.", 10.2, "start"))
    a(node(464, S(1289), NODE["blue"], 14)); a(text(500, S(1292), "Spatial node (location)", 8.4, "start"))
    a(path([(449, S(1339)), (492, S(1339))])); a(text(500, S(1342), "Spatial relation", 8.4, "start"))
    for xz, lab, dA, dB, cB in [(845, "Time t", False, False, "blue"), (1239, "Time t+1", False, True, "blue"),
                                (1633, "Time t′", True, True, "light")]:
        a(rect(xz + 5, S(1059), xz + 281, S(1298), fill="color-mix(in srgb,var(--c6) 22%,transparent)"))
        a(rect(xz, S(1054), xz + 276, S(1293), fill="var(--surface)", stroke=MUTED, sw=PT))
        a(path([(xz + 48, S(1104)), (xz + 134, S(1175))], dash="9 7" if dA else None))
        a(path([(xz + 205, S(1104)), (xz + 134, S(1175))])); a(path([(xz + 66, S(1244)), (xz + 134, S(1175))]))
        a(path([(xz + 224, S(1244)), (xz + 134, S(1175))], dash="9 7" if dB else None))
        for dx, dy, lb, col in [(48, 1104, "1", "blue"), (205, 1104, "2", cB), (134, 1175, "3", "blue"),
                                (66, 1244, "4", "blue"), (224, 1244, "5", "blue")]:
            a(node(xz + dx, S(dy), NODE[col], 17, lb, 7))
        a(text(xz + 143, S(1335), lab, 10.6))
    for y in (1153, 1203, 1253):
        a(circle(1566, S(y), 3.5, INK, stroke="none", sw=0))
    a(legcard(1929, S(1067), 2310, S(1333))); a(text(2097, S(1101), "Legend", 12, weight=700))
    a(node(1958, S(1149), NODE["blue"], 13)); a(text(2013, S(1159), "Node (location)", 9.2, "start"))
    a(node(1958, S(1195), NODE["light"], 13)); a(text(2013, S(1204), "New/changed node", 9.2, "start"))
    a(path([(1940, S(1246)), (1978, S(1246))])); a(text(2013, S(1250), "Existing relation", 9.2, "start"))
    a(path([(1940, S(1290)), (1978, S(1290))], dash="9 7")); a(text(2013, S(1297), "Removed relation", 9.2, "start"))
    # banner
    a(rect(16, 1185, 2326, 1255, fill="color-mix(in srgb,var(--c6) 25%,transparent)", rx=10))
    a(rect(12, 1180, 2322, 1250, fill=tint(C[6], 12), stroke="color-mix(in srgb,var(--c6) 50%,transparent)", sw=PT, rx=10))
    a(text(1167, 1215, '<tspan style="font-weight:700">Not mutually exclusive:</tspan>  Heterogeneous + Dynamic + '
                       'Spatial  =  <tspan style="font-weight:700;fill:var(--c1)">Real-world Graphs</tspan>', 12, raw=True))
    return svg(2340, 1265, "".join(b), "Graph settings: static, dynamic, homogeneous, heterogeneous, and "
               "spatio-temporal graphs; real-world graphs combine them.", "gt")


# ---------------------------------------------------------------------------
# Figure: token construction, serialization and scanning (fig:serialization)
# ---------------------------------------------------------------------------
GB = {1: (291, 234, "blue"), 2: (210, 300, "green"), 3: (291, 320, "red"), 4: (371, 300, "orange"),
      5: (198, 413, "purple"), 6: (259, 421, "yellow"), 7: (318, 423, "red"), 8: (388, 416, "gray")}
GB_EDGES = [(1, 2), (1, 3), (1, 4), (2, 3), (3, 4), (2, 5), (3, 6), (3, 7), (4, 8)]


def gbase(dx=0, dy=0) -> str:
    p = {k: (x + dx, y + dy) for k, (x, y, _) in GB.items()}
    out = edges([(p[a], p[b]) for a, b in GB_EDGES])
    for k, (x, y, col) in GB.items():
        out += node(x + dx, y + dy, NODE[col], 17, str(k), 7)
    return out


def fig_serialization(links: dict) -> str:
    """links: BibTeX key -> (model name, paper URL or None)."""
    b = []
    a = b.append
    ar = "ah-se"

    def model(x, y, key, pt=12):
        name, href = links[key]
        a(link(href, text(x, y, name, pt, weight=700, fill="var(--primary)")))

    def badge(cx, cy, w, label):
        a(rect(cx - w / 2, cy - 15, cx + w / 2, cy + 15, fill="var(--c6)", rx=6))
        a(text(cx, cy, label, 7.8, weight=700, fill="#ffffff"))

    def seqbox(x1, y1, x2, y2, rx=7):
        a(rect(x1, y1, x2, y2, fill="var(--surface)", stroke=RULE, sw=0.9 * PT, rx=rx))

    def arrow(p, q):
        a(path([p, q], stroke=INK, sw=0.9 * PT, arrow=ar))

    for (x1, x2, k) in [(10, 530, 1), (549, 1048, 2), (1065, 1539, 3), (1556, 2055, 4), (2073, 2570, 5)]:
        a(rect(x1, 5, x2, 958, fill="var(--surface)", stroke=f"color-mix(in srgb,{C[k]} 70%,transparent)", sw=0.9 * PT, rx=9))
    for (x1, x2, k, t1, t2, sub) in [(30, 515, 1, "(a) Structure-aware", "node ordering", "(e.g., degree / centrality)"),
                                     (558, 1028, 2, "(b) Neighborhood", "token construction", "(k-hop subgraphs → tokens)"),
                                     (1075, 1527, 3, "(c) Type-/metapath-aware", "token construction", "(heterogeneous graph)"),
                                     (1578, 2045, 4, "(d) Temporal", "serialization", "(graph snapshots over time)"),
                                     (2088, 2555, 5, "(e) Rank-aware", "higher-order tokenization", "(simplicial complexes)")]:
        a(rect(x1 + 5, 13, x2 + 5, 177, fill=f"color-mix(in srgb,{C[k]} 22%,transparent)"))
        a(rect(x1, 8, x2, 172, fill=tint(C[k], 14)))
        a(text((x1 + x2) / 2, 42, t1, 10.3, weight=700, fill=C[k]))
        a(text((x1 + x2) / 2, 90, t2, 10.3, weight=700, fill=C[k]))
        a(text((x1 + x2) / 2, 137, sub, 10, fill=INK))

    # (a) structural ordering
    a(gbase())
    a(rect(15, 507, 145, 608, fill=tint(C[1], 14)))
    a(rect(15, 507, 520, 608, stroke=f"color-mix(in srgb,{C[1]} 40%,transparent)", sw=0.6 * PT))
    a(path([(15, 558), (520, 558)], stroke=f"color-mix(in srgb,{C[1]} 40%,transparent)", sw=0.6 * PT))
    for i in range(0, 8):
        a(path([(145 + i * 46.875, 507), (145 + i * 46.875, 608)], stroke=f"color-mix(in srgb,{C[1]} 40%,transparent)", sw=0.6 * PT))
    a(text(80, 531, "Node", 11, weight=700)); a(text(82, 577, "Degree", 11, weight=700))
    for k, (nv, dg) in enumerate([(3, 5), (1, 3), (2, 3), (4, 3), (5, 1), (6, 1), (7, 1), (8, 1)]):
        a(text(145 + k * 46.875 + 23.4, 532, str(nv), 11)); a(text(145 + k * 46.875 + 23.4, 583, str(dg), 11))
    a(text(272, 627, "ties (equal degree) broken at random", 8.4, italic=True, fill=MUTED))
    arrow((274, 645), (274, 705))
    seqbox(45, 718, 509, 798)
    a(text(277, 760, 'V<tspan baseline-shift="sub" font-size="70%">3</tspan> → V<tspan baseline-shift="sub" font-size="70%">1</tspan>'
                     ' → V<tspan baseline-shift="sub" font-size="70%">2</tspan> → V<tspan baseline-shift="sub" font-size="70%">4</tspan> → …',
           11, raw=True))
    badge(273, 826, 110, "D2"); model(273, 895, "wang2024graph")

    # (b) neighborhood tokenization
    a(gbase(473, -2))
    a(f'<ellipse cx="{290 + 473}" cy="{285 - 2}" rx="120" ry="88" style="fill:none;stroke:{C[2]};stroke-width:{0.9 * PT:.1f};stroke-dasharray:10 7"/>')
    for x, lab in [(562, "1"), (702, "2"), (846, "3")]:
        seqbox(x, 487, x + 126, 643, rx=8)
        a(text(x + 61, 503, f'T<tspan baseline-shift="sub" font-size="70%">{lab}</tspan>', 7.6, weight=700, raw=True))
    a(edges([((626, 548), (587, 615)), ((626, 548), (661, 615)), ((765, 548), (726, 615)), ((765, 548), (800, 615)),
             ((911, 545), (873, 611)), ((911, 545), (946, 611))]))
    for x, y, col, lab in [(626, 548, "blue", "1"), (587, 615, "green", "2"), (661, 615, "red", "3"), (765, 548, "orange", "4"),
                           (726, 615, "green", "2"), (800, 615, "yellow", "6"), (911, 545, "red", "3"), (873, 611, "purple", "5"),
                           (946, 611, "yellow", "6")]:
        a(node(x, y, NODE[col], 17, lab, 7))
    a(text(996, 568, "…", 16, weight=700))
    arrow((765, 650), (765, 718))
    seqbox(594, 723, 931, 798)
    a(text(762, 761, '[T<tspan baseline-shift="sub" font-size="70%">1</tspan>, T<tspan baseline-shift="sub" font-size="70%">2</tspan>, '
                     'T<tspan baseline-shift="sub" font-size="70%">3</tspan>, …]', 11, raw=True))
    badge(793, 826, 110, "D1"); model(793, 895, "behrouz2024graph")

    # (c) type-aware / metapath
    a(edges([((1245, 205), (1147, 298)), ((1245, 205), (1245, 310)), ((1245, 205), (1348, 298)), ((1147, 298), (1245, 310)),
             ((1348, 298), (1245, 310)), ((1147, 298), (1147, 411)), ((1245, 310), (1245, 411)), ((1348, 298), (1348, 411))]))
    for x, y, col in [(1245, 205, "blue"), (1245, 310, "blue"), (1147, 298, "orange"), (1348, 298, "orange"),
                      (1147, 411, "blue"), (1245, 411, "orange"), (1348, 411, "blue")]:
        a(node(x, y, NODE[col], 18))
    a(node(1380, 261, NODE["blue"], 17)); a(text(1400, 261, "Type A", 10, "start"))
    a(node(1380, 323, NODE["orange"], 17)); a(text(1400, 321, "Type B", 10, "start"))
    a(node(1136, 540, NODE["blue"], 28, "A", 9)); a(node(1245, 540, NODE["orange"], 28, "B", 9))
    a(node(1367, 540, NODE["blue"], 28, "A", 9))
    arrow((1166, 540), (1215, 540)); arrow((1275, 540), (1337, 540))
    a(text(1273, 601, "Metapath", 10.5))
    arrow((1275, 660), (1275, 715))
    seqbox(1104, 730, 1445, 806)
    a(text(1274, 769, "[ϕ(A–B–A), …]", 11))
    badge(1321, 832, 170, "D1 + D2"); model(1321, 897, "pan2024hetegraph")

    # (d) temporal serialization
    for cx, lab in [(1655, "t−1"), (1810, "t"), (1965, "t+1")]:
        seqbox(cx - 67, 230, cx + 67, 467, rx=8)
        a(text(cx, 198, f'G<tspan baseline-shift="super" font-size="70%">({lab})</tspan>', 7.6, weight=700, raw=True))
        pts = {"1": (1, 265), "2": (-42, 325), "3": (9, 342), "4": (52, 325), "5": (-32, 407), "6": (11, 407), "7": (57, 407)}
        P = {k: (cx + x, y) for k, (x, y) in pts.items()}
        a(edges([(P["1"], P["2"]), (P["1"], P["3"]), (P["1"], P["4"]), (P["2"], P["3"]), (P["3"], P["4"]),
                 (P["2"], P["5"]), (P["3"], P["6"]), (P["4"], P["7"])], sw=0.55 * PT))
        for k, col in zip("1234567", ["blue", "green", "red", "orange", "purple", "yellow", "gray"]):
            a(node(*P[k], NODE[col], 10.5, "3" if k == "3" else "", 4))
    a(text(1808, 505, "Per-node temporal sequence", 10.5)); a(text(1808, 548, "(e.g., for node v₃)", 10.5))
    for x in (1693, 1809, 1925):
        a(node(x, 595, NODE["red"], 22))
    arrow((1716, 595), (1786, 595)); arrow((1832, 595), (1902, 595))
    for x, lab in [(1693, "t−1"), (1820, "t"), (1943, "t+1")]:
        a(text(x, 655, f'u<tspan baseline-shift="super" font-size="70%">{lab}</tspan>', 11, raw=True))
    arrow((1778, 673), (1778, 724))
    seqbox(1611, 735, 1995, 808)
    a(text(1803, 772, '[u<tspan baseline-shift="super" font-size="70%">t−1</tspan> + u<tspan baseline-shift="super" font-size="70%">t</tspan>'
                      ' + u<tspan baseline-shift="super" font-size="70%">t+1</tspan> + …]', 9.6, raw=True))
    badge(1809, 828, 290, "D2 (temporal order)")
    model(1809, 884, "li2024state"); model(1809, 922, "ding2024dygmamba")

    # (e) rank-aware higher-order
    a(gbase(2016, -2))
    a(text(2322, 471, "Higher-order structures:", 10.5))
    for x, l1, l2 in [(2102, "Triangles", "(2-cells)"), (2254, "Edges", "(1-cells)"), (2407, "Nodes", "(0-cells)")]:
        seqbox(x, 502, x + 133, 680, rx=8)
        a(text(x + 66, 523, l1, 7.6, weight=700)); a(text(x + 66, 549, l2, 7.6, weight=700))
    a(path([(2142, 596), (2125, 643), (2172, 643)], sw=0.6 * PT, close=True))
    a(node(2142, 596, NODE["blue"], 10.5)); a(node(2125, 643, NODE["green"], 10.5)); a(node(2172, 643, NODE["red"], 10.5))
    a(path([(2276, 625), (2338, 625)], sw=0.6 * PT))
    a(node(2276, 625, NODE["red"], 10.5)); a(node(2338, 625, NODE["orange"], 10.5)); a(node(2446, 627, NODE["gray"], 10.5, "8", 4))
    arrow((2321, 683), (2321, 724))
    seqbox(2148, 740, 2497, 814)
    a(text(2322, 778, '[τ<tspan baseline-shift="sub" font-size="70%">△</tspan>, τ<tspan baseline-shift="sub" font-size="70%">E</tspan>, '
                      'τ<tspan baseline-shift="sub" font-size="70%">V</tspan>, …]', 11, raw=True))
    badge(2318, 836, 170, "D1 + D2"); model(2318, 897, "montagna2024topological")

    # scanning strip
    a(rect(15, 980, 2568, 1218, fill="var(--surface)", stroke="color-mix(in srgb,var(--c6) 70%,transparent)", sw=0.9 * PT, rx=9))
    a(rect(22, 985, 477, 1212, fill=tint(C[6], 12)))
    a(text(250, 1100, "D2: Scan direction\nand multiplicity", 12.5, weight=700))
    a(path([(1028, 983), (1028, 1215)], stroke=RULE)); a(path([(1793, 983), (1793, 1215)], stroke=RULE))
    for x, lab in [(715, "Unidirectional"), (1386, "Bidirectional"), (2170, "Multi-order / multi-scan")]:
        a(text(x, 1008, lab, 11.5, weight=700))
    a(text(752, 1193, "single ordered scan", 9.5))
    h_name, h_href = links["dong2024hamba"]; g_name, g_href = links["behrouz2024graph"]; s_name, s_href = links["choi2024spot"]
    a(f'<text text-anchor="middle" dominant-baseline="central" style="font-size:{9.5 * PT:.1f}px;fill:{INK}">'
      f'<tspan x="1410" y="1193">e.g., </tspan>{link(h_href, f"<tspan class=lnk>{esc(h_name)}</tspan>")}, '
      f'{link(g_href, f"<tspan class=lnk>{esc(g_name)}</tspan>")}</text>')
    a(f'<text text-anchor="middle" dominant-baseline="central" style="font-size:{9.5 * PT:.1f}px;fill:{INK}">'
      f'<tspan x="2180" y="1193">e.g., </tspan>{link(s_href, f"<tspan class=lnk>{esc(s_name)}</tspan>")}</text>')
    for x in (579, 736, 892):
        a(node(x, 1103, NODE["blue"], 17))
    arrow((596, 1103), (718, 1103)); arrow((753, 1103), (874, 1103)); a(text(955, 1097, "…", 14, weight=700))
    for x in (1165, 1328, 1491, 1654):
        a(node(x, 1103, NODE["blue"], 17))
    for p, q in [((1182, 1103), (1310, 1103)), ((1345, 1103), (1473, 1103)), ((1508, 1103), (1636, 1103)),
                 ((1307, 1133), (1187, 1133)), ((1470, 1133), (1350, 1133)), ((1633, 1133), (1513, 1133))]:
        arrow(p, q)
    for xs, y in [((1932, 2074, 2216, 2357), 1040), ((1928, 2069, 2210, 2351), 1095), ((1927, 2069, 2210, 2351), 1146)]:
        for x in xs:
            a(node(x, y, NODE["blue"], 17))
    for p, q in [((1950, 1040), (2056, 1040)), ((2092, 1040), (2198, 1040)), ((2234, 1040), (2339, 1040)),
                 ((2051, 1095), (1947, 1095)), ((2192, 1095), (2087, 1095)), ((2333, 1095), (2228, 1095)),
                 ((1943, 1141), (2054, 1108)), ((2087, 1146), (2192, 1146)), ((2226, 1141), (2336, 1108))]:
        arrow(p, q)
    for x, y in [(2408, 1036), (2404, 1092), (2404, 1148)]:
        a(text(x, y, "…", 14, weight=700))
    body = "".join(b).replace('id="ah-se"', 'id="ah-se"')
    return svg(2578, 1226, body, "Representative token construction, serialization, and scanning strategies (panels a–e) "
               "and unidirectional, bidirectional, and multi-order scanning.", "se")


# ---------------------------------------------------------------------------
# Figure: unified pipeline (fig:pipeline) -- responsive HTML
# ---------------------------------------------------------------------------
ICONS = {
    "net": '<path d="M5 17 L19 17 L12 5 Z" /><circle cx="5" cy="17" r="2.2"/><circle cx="19" cy="17" r="2.2"/><circle cx="12" cy="5" r="2.2"/>',
    "tok": '<rect x="2.5" y="9" width="5" height="6" rx="1"/><rect x="9.5" y="9" width="5" height="6" rx="1"/><rect x="16.5" y="9" width="5" height="6" rx="1"/>',
    "seq": '<circle cx="4" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="20" cy="12" r="1.6"/><path d="M6 12h4M14 12h4"/>',
    "op": '<circle cx="12" cy="12" r="4.5"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>',
    "fus": '<path d="M3 6l7 6-7 6M10 12h11M17 8l4 4-4 4"/>',
}
STAGES = [
    (1, "net", "Graph construction", "native graph, or graph derived from images, signals, or text", "", "which entities and edges exist"),
    (2, "tok", "Tokenization", "nodes, neighborhoods, walks, metapaths, cells, snapshots", "D1", "what a token contains: local structure, type, rank"),
    (3, "seq", "Ordering and scanning", "order <i>π</i> ∈ Π(<i>G</i>), direction(s)", "D2", "structure-derived order and direction"),
    (4, "op", "State-space computation", "<i>h<sub>t</sub></i> = <i>Ā<sub>t</sub> h</i><sub><i>t</i>−1</sub> + <i>B̄<sub>t</sub> u<sub>t</sub></i>", "D3",
     "graph-conditioned Δ, <i>B</i>, <i>C</i> or transition; separate graph operator"),
    (5, "fus", "Alignment and readout", "restore <b>P</b><sub><i>π</i></sub><sup>⊤</sup>, fuse, pool or head", "D4", "fusion with the local branch; readout"),
]


def fig_pipeline() -> str:
    stages = "".join(
        f'<li class="pstage" style="--sc:var(--c{k})"><div class="pcard"><div class="phead"><span class="pico" aria-hidden="true">'
        f'<svg viewBox="0 0 24 24">{ICONS[icon]}</svg></span><h4>{k}. {esc(title)}</h4>'
        + (f'<span class="pdq">taxonomy {dq}</span>' if dq else "") + f'</div><p>{desc}</p></div>'
        f'<div class="pentry"><b>E{k}</b> {entry}</div></li>'
        for k, icon, title, desc, dq, entry in STAGES)
    return ('<div class="pipe">'
            '<div class="plocal"><span class="ptag">optional</span><span class="pfrom" aria-hidden="true">from 1 ↴</span>'
            '<span><b>Local branch</b>: message passing, graph convolution, or graph attention (produces '
            '<b>H</b><sub>local</sub>)</span><span class="pfrom" aria-hidden="true">↳ into 5</span></div>'
            f'<ol class="pstages">{stages}</ol>'
            '<p class="pnote"><b>E1–E5</b>: where graph structure enters each stage.</p></div>')


# ---------------------------------------------------------------------------
# Figure: applications landscape (fig:design-patterns), generated from the database
# ---------------------------------------------------------------------------
LANDSCAPE = [  # id, panel title, subdomains, ring colour, ring label, start angle, end angle
    ("neural", "Neural and physiological signals", ["neural_signals"], "#1f63a8", "Neural\nsignals", 30, 90),
    ("clinical", "Clinical, biological, molecular", ["clinical_molecular"], "#1b8a86", "Clinical &\nmolecular", -30, 30),
    ("histo", "Histopathology", ["histopathology"], "#3f8a2e", "Histo-\npathology", -90, -30),
    ("medical", "Medical imaging", ["medical_imaging"], "#6b4b9e", "Medical\nimaging", 210, 270),
    ("remote", "Remote sensing and visual data", ["remote_sensing", "articulated_motion"], "#d97a18", "Remote &\nvisual", 150, 210),
    ("other", "Other application areas", ["financial", "industrial", "cybersecurity", "language"], "#4f5d75", "Other\nareas", 90, 150),
]
PATTERN_SHORT = {"DV": "dual-view: graph and SSM process different views",
                 "RT": "relational–temporal: time orders the sequence",
                 "GS": "graph-guided sequence: graph structure orders the sequence",
                 "LG": "local-to-global: local graph, then global SSM"}


def _ring() -> str:
    ro, ri = 310, 175
    pt = lambda r, ang: (r * math.cos(math.radians(ang)), -r * math.sin(math.radians(ang)))
    parts = []
    for gid, title, _, col, lab, a0, a1 in LANDSCAPE:
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pt(ri, a0), pt(ro, a0), pt(ro, a1), pt(ri, a1)
        d = (f"M{x0:.1f},{y0:.1f} L{x1:.1f},{y1:.1f} A{ro},{ro} 0 0 0 {x2:.1f},{y2:.1f} "
             f"L{x3:.1f},{y3:.1f} A{ri},{ri} 0 0 1 {x0:.1f},{y0:.1f} Z")
        parts.append(f'<a href="#land-{gid}" class="ringseg" aria-label="{esc(title)}"><path d="{d}" style="fill:{col}"/></a>')
        mx, my = pt(242, (a0 + a1) / 2)
        lines = lab.split("\n")
        parts.append('<text text-anchor="middle" dominant-baseline="central" class="ringlab">' + "".join(
            f'<tspan x="{mx:.1f}" y="{my + (i - (len(lines) - 1) / 2) * 30:.1f}">{esc(t)}</tspan>' for i, t in enumerate(lines)) + "</text>")
    for ang in (30, 90, 150, 210, 270, 330):
        (xa, ya), (xb, yb) = pt(160, ang), pt(325, ang)
        parts.append(f'<path d="M{xa:.1f},{ya:.1f} L{xb:.1f},{yb:.1f}" style="stroke:var(--surface);stroke-width:12"/>')
    parts.append('<circle cx="0" cy="0" r="160" style="fill:var(--surface)"/>'
                 '<circle cx="0" cy="0" r="145" style="fill:none;stroke:var(--line);stroke-width:3"/>'
                 '<text text-anchor="middle" dominant-baseline="central" class="ringc"><tspan x="0" y="-18">Graph Mamba</tspan>'
                 '<tspan x="0" y="22">applications</tspan></text>')
    return ('<svg class="ring" viewBox="-335 -335 670 670" role="img" aria-label="Ring of six application data settings">'
            + "".join(parts) + "</svg>")


def fig_landscape(resolved: list[dict]) -> str:
    apps = [r for r in resolved if r["application"]]
    order = {"DV": 0, "RT": 1, "GS": 2, "LG": 3}

    def item(r):
        a = r["application"]
        sup = (f'<sup>+{esc(a["secondary_pattern"])}</sup>' if a.get("secondary_pattern") else "") + \
              ('<sup title="multimodal">◆</sup>' if r["multimodal"] else "") + \
              ('<sup title="structured-SSM precursor">†</sup>' if r["precursor"] else "")
        href = r["primary_link"] if r["primary_link"] != "NR" else None
        name = esc(r["model"].replace("--", "–"))
        return (f'<li><span class="ptagc" style="background:{PAT_COLOR[a["dominant_pattern"]]};color:{PAT_TEXT[a["dominant_pattern"]]}">{a["dominant_pattern"]}</span>'
                f'{link(href, name)}{sup}</li>')

    def panel(g):
        gid, title, subs, col, *_ = g
        works = sorted([r for r in apps if r["application"]["subdomain"] in subs],
                       key=lambda r: order[r["application"]["dominant_pattern"]])
        return (f'<section class="lpanel" id="land-{gid}" style="--lc:{col}"><h4>{esc(title)}</h4>'
                f'<ul>{"".join(item(r) for r in works)}</ul></section>')

    by = {g[0]: g for g in LANDSCAPE}
    left = "".join(panel(by[k]) for k in ("other", "remote", "medical"))
    right = "".join(panel(by[k]) for k in ("neural", "clinical", "histo"))
    legend = "".join(f'<span><span class="ptagc" style="background:{PAT_COLOR[k]};color:{PAT_TEXT[k]}">{k}</span>{esc(v)}</span>'
                     for k, v in PATTERN_SHORT.items())
    return (f'<div class="land"><div class="lcol">{left}</div><div class="lring">{_ring()}</div><div class="lcol">{right}</div></div>'
            f'<div class="llegend">{legend}<span class="lmarks"><sup>+X</sup> secondary pattern; ◆ multimodal; † structured-SSM '
            f'precursor without input-dependent selection.</span></div>')


# ---------------------------------------------------------------------------
def figure_html(fig: dict, body: str, wide_scroll: bool = False) -> str:
    inner = f'<div class="sfig-scroll" tabindex="0" role="region" aria-label="{esc(fig["title"])}">{body}</div>' if wide_scroll else body
    return (f'<figure class="sfig" id="fig-{esc(fig["id"])}"><h3>{esc(fig["title"])}</h3>{inner}'
            f'<figcaption>{esc(fig["caption"])}</figcaption></figure>')


def render(figures: list[dict], resolved: list[dict]) -> dict[str, str]:
    """HTML blocks keyed by figure id."""
    by_key = {r["key"]: r for r in resolved}
    links = {k: (r["model"], r["primary_link"] if r["primary_link"] != "NR" else None) for k, r in by_key.items()}
    bodies = {"graph-types": (fig_graph_types(), True), "pipeline": (fig_pipeline(), False),
              "serialization": (fig_serialization(links), True), "design-patterns": (fig_landscape(resolved), False)}
    return {f["id"]: figure_html(f, *bodies[f["id"]]) for f in figures if f["id"] in bodies}
