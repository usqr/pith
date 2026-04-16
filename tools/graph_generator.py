#!/usr/bin/env python3
"""
Pith Wiki Graph Generator
Scans ./wiki/ for .md files, extracts [[wikilinks]], and renders an
interactive force-directed graph as a standalone wiki-graph.html.
"""

import os
import re
import json
import webbrowser
import sys
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
# Resolve relative to the user's working directory, not the script location.
# This ensures the tool works correctly when installed inside pith/tools/.
WIKI_DIR = Path.cwd() / "wiki"
OUTPUT_FILE = Path.cwd() / "wiki-graph.html"
WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')


# ── 1. Parse wiki ─────────────────────────────────────────────────────────────
def parse_wiki(wiki_dir: Path) -> tuple[list[dict], list[dict]]:
    """Return (nodes, edges) from all .md files under wiki_dir."""
    if not wiki_dir.exists():
        print(f"[error] wiki directory not found: {wiki_dir}", file=sys.stderr)
        sys.exit(1)

    node_set: dict[str, dict] = {}   # id -> {id, label, path, group}
    edges: list[dict] = []

    md_files = sorted(wiki_dir.rglob("*.md"))
    if not md_files:
        print("[warn] No .md files found in wiki/")

    for md_path in md_files:
        rel = md_path.relative_to(wiki_dir)
        node_id = str(rel.with_suffix(""))          # e.g. "decisions/auth-choice"
        label = md_path.stem                         # e.g. "auth-choice"
        group = rel.parts[0] if len(rel.parts) > 1 else "root"

        if node_id not in node_set:
            node_set[node_id] = {"id": node_id, "label": label,
                                 "path": str(rel), "group": group}

        content = md_path.read_text(encoding="utf-8", errors="ignore")
        for match in WIKILINK_RE.finditer(content):
            raw = match.group(1).strip()
            # Normalise: lowercase, spaces → hyphens, no .md suffix
            target_label = raw.lower().replace(" ", "-").replace(".md", "")
            # Try to find a matching node by label (fuzzy: just stem match)
            target_id = _resolve_target(target_label, node_set)
            if target_id:
                edges.append({"source": node_id, "target": target_id})
            else:
                # Ghost node — referenced but no file yet
                ghost_id = f"ghost/{target_label}"
                if ghost_id not in node_set:
                    node_set[ghost_id] = {
                        "id": ghost_id,
                        "label": raw,
                        "path": None,
                        "group": "ghost",
                    }
                edges.append({"source": node_id, "target": ghost_id})

    # Deduplicate edges
    seen_edges: set[tuple] = set()
    unique_edges = []
    for e in edges:
        key = (e["source"], e["target"])
        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append(e)

    nodes = list(node_set.values())
    print(f"[pith graph] {len(nodes)} nodes, {len(unique_edges)} edges")
    return nodes, unique_edges


def _resolve_target(target_label: str, node_set: dict) -> str | None:
    """Match a wikilink target to an existing node id by stem."""
    for node_id, node in node_set.items():
        if node["label"].lower().replace(" ", "-") == target_label:
            return node_id
    # Partial path match (e.g. "decisions/auth-choice" ends with label)
    for node_id in node_set:
        if node_id.lower().endswith(target_label):
            return node_id
    return None


# ── 2. Generate HTML ──────────────────────────────────────────────────────────
HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Pith Wiki Graph</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: #09090b;
    color: #e4e4e7;
    font-family: 'SF Mono', 'Fira Code', ui-monospace, monospace;
    overflow: hidden;
    height: 100vh;
  }

  /* ── Theme tokens ────────────────────────────────────────────────────────── */
  :root {
    --bg:           #09090b;
    --bg-glass:     rgba(9,9,11,0.65);
    --border:       rgba(255,255,255,0.08);
    --border-btn:   rgba(255,255,255,0.12);
    --border-hover: rgba(255,255,255,0.22);
    --text:         #e4e4e7;
    --text-muted:   #a1a1aa;
    --text-dim:     #52525b;
    --pill-bg:      rgba(9,9,11,0.82);
    --link-base:    #27272a;
  }
  .light {
    --bg:           #fafafa;
    --bg-glass:     rgba(250,250,250,0.72);
    --border:       rgba(0,0,0,0.08);
    --border-btn:   rgba(0,0,0,0.14);
    --border-hover: rgba(0,0,0,0.28);
    --text:         #09090b;
    --text-muted:   #52525b;
    --text-dim:     #a1a1aa;
    --pill-bg:      rgba(250,250,250,0.88);
    --link-base:    #d4d4d8;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'SF Mono', 'Fira Code', ui-monospace, monospace;
    overflow: hidden;
    height: 100vh;
    transition: background 0.25s;
  }

  /* ── Glassmorphism header ─────────────────────────────────────────────────── */
  #header {
    position: fixed;
    top: 16px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 16px;
    background: var(--bg-glass);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.18);
    white-space: nowrap;
  }

  #header .logo {
    font-size: 12px;
    font-weight: 700;
    color: #a78bfa;
    letter-spacing: 0.1em;
  }

  #header .divider {
    width: 1px;
    height: 16px;
    background: var(--border);
  }

  #header .stats {
    font-size: 11px;
    color: var(--text-dim);
  }

  /* shadcn Button variant="outline" size="sm" */
  .btn {
    background: transparent;
    border: 1px solid var(--border-btn);
    color: var(--text-muted);
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-family: inherit;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s, color 0.15s;
  }
  .btn:hover {
    background: rgba(128,128,128,0.08);
    border-color: var(--border-hover);
    color: var(--text);
  }
  .btn:active { background: rgba(128,128,128,0.14); }

  /* theme toggle icon */
  #theme-btn { font-size: 13px; padding: 3px 8px; }

  /* ── Legend ──────────────────────────────────────────────────────────────── */
  #legend {
    position: fixed;
    bottom: 20px;
    left: 20px;
    z-index: 20;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px 14px;
    background: var(--bg-glass);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .legend-item {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 10px;
    color: var(--text-dim);
  }
  .legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  /* ── SVG canvas ──────────────────────────────────────────────────────────── */
  svg {
    width: 100vw;
    height: 100vh;
    display: block;
  }

  /* ── Links ───────────────────────────────────────────────────────────────── */
  .link {
    stroke-width: 1.5px;
    transition: stroke-opacity 0.2s, stroke-width 0.2s;
  }
  .link.faded   { stroke-opacity: 0.05; }
  .link.active  { stroke-width: 2px; stroke-opacity: 0.9 !important; }

  /* ── Node circles ────────────────────────────────────────────────────────── */
  .node { cursor: grab; }
  .node:active { cursor: grabbing; }

  .node circle {
    stroke-width: 1.5px;
    transition: opacity 0.2s, filter 0.2s;
  }
  .node circle.ghost {
    stroke-dasharray: 4 3;
    fill: transparent;
    opacity: 0.3;
  }
  .node.faded circle  { opacity: 0.07; }
  .node.faded .pill-bg { opacity: 0.07; }
  .node.faded text    { opacity: 0.07; }

  /* ── Label pill ──────────────────────────────────────────────────────────── */
  .pill-bg {
    transition: opacity 0.2s;
  }

  .node text {
    font-size: 10.5px;
    pointer-events: none;
    dominant-baseline: central;
    transition: opacity 0.2s, fill 0.2s;
  }
  .node.focused text { font-weight: 600; }

  /* ── Tooltip ─────────────────────────────────────────────────────────────── */
  #tooltip {
    position: fixed;
    background: var(--bg-glass);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 9px 13px;
    font-size: 11px;
    color: var(--text);
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s;
    max-width: 280px;
    line-height: 1.7;
    z-index: 30;
    backdrop-filter: blur(10px);
  }
  #tooltip.visible { opacity: 1; }
  #tooltip .tip-label { font-weight: 600; margin-bottom: 2px; }
  #tooltip .tip-meta  { color: var(--text-dim); font-size: 10px; }
  #tooltip .tip-path  { color: var(--text-dim); font-size: 10px; margin-top: 3px; }
  #tooltip .tip-links { color: var(--text-dim); font-size: 10px; margin-top: 4px; }
</style>
</head>
<body>

<div id="header">
  <span class="logo">◆ PITH WIKI</span>
  <div class="divider"></div>
  <span class="stats" id="stats">loading…</span>
  <button class="btn" onclick="resetZoom()">Reset view</button>
  <button class="btn" id="theme-btn" onclick="toggleTheme()" title="Toggle light/dark">☀︎</button>
</div>

<div id="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#34d399"></div>Decisions</div>
  <div class="legend-item"><div class="legend-dot" style="background:#818cf8"></div>Concepts</div>
  <div class="legend-item"><div class="legend-dot" style="background:#fb923c"></div>Entities</div>
  <div class="legend-item"><div class="legend-dot" style="background:#f472b6"></div>Syntheses</div>
  <div class="legend-item"><div class="legend-dot" style="background:#a78bfa"></div>Root</div>
  <div class="legend-item"><div class="legend-dot" style="background:#3f3f46;border:1px dashed #52525b"></div>Ghost</div>
</div>

<div id="tooltip"></div>
<svg id="graph"></svg>

<script>
// ── Injected data ─────────────────────────────────────────────────────────────
const RAW_NODES = __NODES__;
const RAW_EDGES = __EDGES__;

// ── Tailwind-inspired palette ─────────────────────────────────────────────────
const GROUP_COLORS = {
  decisions:  "#34d399",   // emerald-400
  concepts:   "#818cf8",   // indigo-400
  entities:   "#fb923c",   // orange-400  (tools/services/people)
  syntheses:  "#f472b6",   // pink-400
  root:       "#a78bfa",   // violet-400
  ghost:      "#3f3f46",   // zinc-700
};
const DEFAULT_COLOR = "#818cf8";

const GROUP_GLOW = {
  decisions: "drop-shadow(0 0 6px rgba(52,211,153,0.55))",
  concepts:  "drop-shadow(0 0 6px rgba(129,140,248,0.55))",
  entities:  "drop-shadow(0 0 6px rgba(251,146,60,0.55))",
  syntheses: "drop-shadow(0 0 6px rgba(244,114,182,0.55))",
  root:      "drop-shadow(0 0 6px rgba(167,139,250,0.55))",
};

function nodeColor(d) { return GROUP_COLORS[d.group] || DEFAULT_COLOR; }
function nodeGlow(d)  { return GROUP_GLOW[d.group]  || "none"; }
function nodeRadius(d){ return d.group === "ghost" ? 5 : 10; }

// ── Build adjacency index ─────────────────────────────────────────────────────
const nodeById = {};
RAW_NODES.forEach(n => { nodeById[n.id] = n; });

const edges = RAW_EDGES.filter(e =>
  nodeById[e.source] !== undefined && nodeById[e.target] !== undefined
);

// neighbour sets (populated after simulation resolves ids)
const neighbours = {};
RAW_NODES.forEach(n => { neighbours[n.id] = new Set(); });

document.getElementById("stats").textContent =
  `${RAW_NODES.length} pages · ${edges.length} links`;

// ── SVG / zoom ────────────────────────────────────────────────────────────────
const svg = d3.select("#graph");
const W = window.innerWidth, H = window.innerHeight;
const g = svg.append("g");

const zoom = d3.zoom()
  .scaleExtent([0.08, 10])
  .on("zoom", e => g.attr("transform", e.transform));

svg.call(zoom);

function resetZoom() {
  svg.transition().duration(500)
     .call(zoom.transform, d3.zoomIdentity.translate(W/2, H/2).scale(0.9));
}

// ── Simulation ────────────────────────────────────────────────────────────────
const simulation = d3.forceSimulation(RAW_NODES)
  .force("link",    d3.forceLink(edges).id(d => d.id).distance(100).strength(0.35))
  .force("charge",  d3.forceManyBody().strength(-320))
  .force("center",  d3.forceCenter(0, 0))
  .force("collide", d3.forceCollide(32));

// ── Links ─────────────────────────────────────────────────────────────────────
const link = g.append("g").attr("class", "links")
  .selectAll("line")
  .data(edges)
  .join("line")
  .attr("class", "link")
  .attr("stroke", d => {
    const s = d.source.id || d.source;
    const t = d.target.id || d.target;
    const sn = nodeById[s], tn = nodeById[t];
    // blend both endpoint colours at low opacity
    return sn ? nodeColor(sn) : "#27272a";
  })
  .attr("stroke-opacity", 0.25);

// ── Node groups ───────────────────────────────────────────────────────────────
const nodeG = g.append("g").attr("class", "nodes")
  .selectAll("g")
  .data(RAW_NODES)
  .join("g")
  .attr("class", "node")
  .call(d3.drag()
    .on("start", dragStart)
    .on("drag",  dragged)
    .on("end",   dragEnd));

// Circle
nodeG.append("circle")
  .attr("r",      nodeRadius)
  .attr("fill",   d => d.group === "ghost" ? "transparent" : nodeColor(d))
  .attr("fill-opacity", d => d.group === "ghost" ? 0 : 0.18)
  .attr("stroke", nodeColor)
  .attr("filter", d => nodeGlow(d))
  .classed("ghost", d => d.group === "ghost");

// Pill background rect (sized after layout so we do it in tick)
nodeG.append("rect")
  .attr("class", "pill-bg")
  .attr("rx", 3).attr("ry", 3)
  .attr("fill", "rgba(9,9,11,0.82)")
  .attr("opacity", 0);   // revealed after first tick

// Label text
nodeG.append("text")
  .text(d => d.label)
  .attr("x", 15)
  .attr("y", 0)
  .attr("fill", "#a1a1aa");

// ── Build neighbour index after edge data is bound ────────────────────────────
edges.forEach(e => {
  const s = e.source.id || e.source;
  const t = e.target.id || e.target;
  if (neighbours[s]) neighbours[s].add(t);
  if (neighbours[t]) neighbours[t].add(s);
});

// ── Focus hover ───────────────────────────────────────────────────────────────
const tooltip = document.getElementById("tooltip");

nodeG
  .on("mouseover", (event, d) => {
    const nb = neighbours[d.id] || new Set();

    // Dim all, then un-dim focal node + 1st-degree
    nodeG.classed("faded",  n => n.id !== d.id && !nb.has(n.id))
         .classed("focused", n => n.id === d.id);

    link.classed("faded",  e => {
          const s = e.source.id || e.source;
          const t = e.target.id || e.target;
          return s !== d.id && t !== d.id;
        })
        .classed("active", e => {
          const s = e.source.id || e.source;
          const t = e.target.id || e.target;
          return s === d.id || t === d.id;
        });

    // Tooltip
    const outDeg = edges.filter(e => (e.source.id||e.source) === d.id).length;
    const inDeg  = edges.filter(e => (e.target.id||e.target) === d.id).length;
    tooltip.innerHTML =
      `<div class="tip-label" style="color:${nodeColor(d)}">${d.label}</div>` +
      `<div class="tip-meta">${d.group}</div>` +
      (d.path ? `<div class="tip-path">${d.path}</div>` : "") +
      `<div class="tip-links">↗ ${outDeg} out &nbsp;·&nbsp; ↙ ${inDeg} in</div>`;
    tooltip.classList.add("visible");
  })
  .on("mousemove", event => {
    tooltip.style.left = (event.clientX + 18) + "px";
    tooltip.style.top  = (event.clientY - 12) + "px";
  })
  .on("mouseout", () => {
    nodeG.classed("faded", false).classed("focused", false);
    link.classed("faded", false).classed("active", false);
    tooltip.classList.remove("visible");
  });

// ── Tick ──────────────────────────────────────────────────────────────────────
const PILL_PAD_X = 5, PILL_PAD_Y = 3;

simulation.on("tick", () => {
  link
    .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x).attr("y2", d => d.target.y);

  nodeG.attr("transform", d => `translate(${d.x},${d.y})`);

  // Size pill rects to match text bounding box
  nodeG.each(function() {
    const grp  = d3.select(this);
    const txt  = grp.select("text").node();
    const rect = grp.select("rect.pill-bg");
    if (!txt) return;
    try {
      const bb = txt.getBBox();
      rect
        .attr("x",      bb.x - PILL_PAD_X)
        .attr("y",      bb.y - PILL_PAD_Y)
        .attr("width",  bb.width  + PILL_PAD_X * 2)
        .attr("height", bb.height + PILL_PAD_Y * 2)
        .attr("opacity", 1);
    } catch(e) {}
  });
});

// ── Drag ──────────────────────────────────────────────────────────────────────
function dragStart(event, d) {
  if (!event.active) simulation.alphaTarget(0.3).restart();
  d.fx = d.x; d.fy = d.y;
}
function dragged(event, d) { d.fx = event.x; d.fy = event.y; }
function dragEnd(event, d) {
  if (!event.active) simulation.alphaTarget(0);
  d.fx = null; d.fy = null;
}

// ── Theme toggle ──────────────────────────────────────────────────────────────
let isDark = true;

function applyTheme() {
  document.body.classList.toggle("light", !isDark);
  document.getElementById("theme-btn").textContent = isDark ? "☀︎" : "☾";

  // Recolour pill backgrounds (CSS var doesn't reach SVG fill attr directly)
  const pillColor = isDark ? "rgba(9,9,11,0.82)" : "rgba(250,250,250,0.88)";
  nodeG.selectAll("rect.pill-bg").attr("fill", pillColor);

  // Recolour text
  const textColor = isDark ? "#a1a1aa" : "#52525b";
  nodeG.selectAll("text").attr("fill", textColor);

  // Recolour link base (non-focused)
  link.filter(function() {
    return !d3.select(this).classed("active");
  }).attr("stroke", isDark ? undefined : d => {
    const s = d.source.id || d.source;
    const sn = nodeById[s];
    return sn ? nodeColor(sn) : "#d4d4d8";
  });
}

function toggleTheme() {
  isDark = !isDark;
  applyTheme();
}

// ── Initial view ──────────────────────────────────────────────────────────────
svg.call(zoom.transform, d3.zoomIdentity.translate(W/2, H/2).scale(0.9));

window.addEventListener("resize", () =>
  simulation.force("center", d3.forceCenter(0,0)).alpha(0.1).restart()
);
</script>
</body>
</html>
"""


def generate_html(nodes: list[dict], edges: list[dict]) -> str:
    html = HTML_TEMPLATE
    html = html.replace("__NODES__", json.dumps(nodes, indent=2))
    html = html.replace("__EDGES__", json.dumps(edges, indent=2))
    return html


# ── 3. Main ───────────────────────────────────────────────────────────────────
def main():
    nodes, edges = parse_wiki(WIKI_DIR)
    html = generate_html(nodes, edges)

    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"[pith graph] written → {OUTPUT_FILE}")

    url = OUTPUT_FILE.resolve().as_uri()
    webbrowser.open(url)
    print(f"[pith graph] opening {url}")


if __name__ == "__main__":
    main()
