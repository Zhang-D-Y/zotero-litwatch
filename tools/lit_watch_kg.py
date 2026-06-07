#!/usr/bin/env python3
"""Generate a local literature knowledge graph for MicroSurgeon LitWatch.

Inputs are screened JSONL metadata records. Outputs are self-contained and do
not require Zotero or network access.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import textwrap
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT_PROJECT_ID = "my_project_microsurgeon"


CONCEPTS = {
    "method": {
        "LLM agent": ["llm agent", "agent", "multi-agent", "autonomous", "chat", "copilot"],
        "RAG": ["rag", "retrieval", "retrieval-augmented"],
        "memory": ["memory", "skill library", "experience", "hard bank"],
        "distillation": ["distillation", "distilled", "fine-tuning", "finetuning", "supervised"],
        "formal equivalence": ["formal equivalence", "equivalence checking", "lec", "formaleval"],
        "timing ECO": ["timing eco", "engineering change order", "eco timing", "timing closure"],
        "RTL repair": ["rtl repair", "verilog repair", "bug fix", "bug fixing", "repair"],
        "multi-agent": ["multi-agent", "multi agent", "agents", "role"],
        "symbolic reasoning": ["symbolic", "neural-symbolic", "program synthesis", "synthesis"],
        "EDA tool feedback": ["eda feedback", "tool feedback", "compiler", "simulator", "yosys", "iverilog"],
        "fine-tuning": ["fine-tuning", "finetuning", "fine tuned", "fine-tuned"],
        "assertion generation": ["assertion", "sva", "nl2sva", "systemverilog assertion"],
        "PPA optimization": ["ppa", "power", "performance", "area", "optimization"],
    },
    "task": {
        "Verilog debugging": ["verilog debugging", "debugging", "debug", "bug localization"],
        "RTL semantic repair": ["semantic", "functional bug", "functional correction", "rtl repair", "verilog hdl"],
        "timing closure": ["timing closure", "wns", "tns", "sta", "static timing"],
        "PPA optimization": ["ppa", "power", "performance", "area"],
        "bug localization": ["bug localization", "fault localization", "localization"],
        "RTL code generation": ["code generation", "rtl generation", "verilog generation", "hdl generation"],
        "assertion generation": ["assertion generation", "sva", "nl2sva"],
        "hardware security repair": ["hardware security", "trojan", "vulnerability", "security bug"],
        "verification automation": ["verification", "formal verification", "uvm", "test generation"],
        "benchmark evaluation": ["benchmark", "dataset", "evaluation", "eval"],
    },
    "evidence_gate": {
        "compile pass": ["compile", "compiler", "syntax", "lint"],
        "synthesis pass": ["synthesis", "yosys", "synthesizable"],
        "simulation pass": ["simulation", "testbench", "test bench", "functional correctness", "golden"],
        "formal equivalence": ["formal equivalence", "equivalence checking", "lec"],
        "WNS/TNS": ["wns", "tns", "timing"],
        "correctness gate": ["correctness", "validated", "verification", "pass rate"],
        "human approval": ["human", "expert", "manual"],
        "claim-evidence": ["evidence", "empirical", "case study", "evaluation"],
    },
    "benchmark": {
        "OpenROAD": ["openroad", "opensta"],
        "Yosys": ["yosys"],
        "ISCA/ISCAS": ["isca", "iscas"],
        "Verilog benchmarks": ["verilog benchmark", "verilogeval", "hdlbits", "rtllm", "rtl-repair", "fixbench"],
        "EDA datasets": ["dataset", "eda dataset", "github", "openllm-rtl", "rtlcoder", "opentitan", "cva6"],
    },
}

GAPS = {
    "gap_adversarial_repair_learning": {
        "label": "Gap: adversarial repair learning",
        "keywords": ["adversarial", "red team", "blue team", "bug injection", "mutation"],
        "description": "Most work evaluates fixed repair tasks; few show a blue repair agent improving under adaptive red-team bug pressure.",
    },
    "gap_formal_correctness_gate": {
        "label": "Gap: LEC/formal repair gate",
        "keywords": ["formal", "equivalence", "lec", "correctness"],
        "description": "Most LLM-for-RTL work validates with compile/simulation rather than formal equivalence as a repair gate.",
    },
    "gap_memory_distillation": {
        "label": "Gap: repair memory/distillation",
        "keywords": ["memory", "retrieval", "distillation", "rag", "skill"],
        "description": "RAG appears in some workflows, but durable repair memory and distilled repair skill ablations remain thin.",
    },
    "gap_semantic_rtl_repair": {
        "label": "Gap: semantic RTL repair benchmark",
        "keywords": ["semantic", "functional", "repair", "debug"],
        "description": "Existing benchmarks skew toward generation, syntax, or fixed tests; semantic bug repair with robust gates remains underdeveloped.",
    },
    "gap_timing_boundary": {
        "label": "Gap: deterministic-tool boundary",
        "keywords": ["timing", "eco", "openroad", "opensta", "wns", "tns"],
        "description": "Timing ECO is a deterministic optimization stronghold; papers rarely separate where LLM adds no value from where semantics matter.",
    },
}


def clean(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def norm_id(prefix: str, label: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", label.lower()).strip("_")
    return f"{prefix}_{value[:80]}" if value else prefix


def text_blob(record: Dict[str, Any]) -> str:
    fields = [
        record.get("title", ""),
        record.get("abstract", ""),
        record.get("venue", ""),
        " ".join(record.get("tags") or []),
        record.get("target_subcollection", ""),
        record.get("query", ""),
    ]
    return " ".join(clean(x).lower() for x in fields if x)


def contains_term(blob: str, term: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(term.lower()).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
    return re.search(pattern, blob) is not None


def matches(blob: str, terms: Iterable[str]) -> bool:
    return any(contains_term(blob, term) for term in terms)


def load_records(path: Path, min_score: int) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if int(record.get("score") or 0) >= min_score:
                records.append(record)
    records.sort(key=lambda r: (int(r.get("score") or 0), int(r.get("citation_count") or 0), r.get("year") or 0), reverse=True)
    return records


def add_node(nodes: Dict[str, Dict[str, Any]], node_id: str, label: str, node_type: str, **attrs: Any) -> None:
    if node_id not in nodes:
        nodes[node_id] = {"id": node_id, "label": label, "type": node_type, **attrs}
    else:
        nodes[node_id].update({k: v for k, v in attrs.items() if v not in (None, "", [])})


def add_edge(edges: List[Dict[str, Any]], seen: set[Tuple[str, str, str]], source: str, target: str, edge_type: str, **attrs: Any) -> None:
    key = (source, target, edge_type)
    if key in seen:
        return
    seen.add(key)
    edges.append({"source": source, "target": target, "type": edge_type, **attrs})


def category_label(record: Dict[str, Any]) -> str:
    sub = clean(record.get("target_subcollection", ""))
    mapping = {
        "01_llm_agent_for_eda": "LLM/agent for EDA",
        "02_rtl_repair_debug": "RTL repair/debug",
        "03_formal_correctness_gate": "Formal correctness gate",
        "04_timing_eco_deterministic": "Timing ECO / deterministic tools",
        "05_memory_retrieval_distillation": "Memory/RAG/distillation",
        "06_benchmarks_evaluation": "Benchmark/evaluation",
        "07_red_blue_adversarial_eda": "Red-blue/adversarial EDA",
        "08_rtl_representation_learning": "RTL representation learning",
        "09_background_llm_code_repair": "LLM code repair background",
    }
    return mapping.get(sub, sub or "Uncategorized")


def project_relation(record: Dict[str, Any]) -> str:
    blob = text_blob(record)
    if matches(blob, ["repair", "debug", "bug localization", "bug fixing"]):
        return "Directly informs MicroSurgeon blue-team repair and evaluation."
    if matches(blob, ["formal equivalence", "equivalence checking", "assertion", "formal verification"]):
        return "Supports correctness gates beyond simulation."
    if matches(blob, ["timing", "eco", "openroad", "opensta", "wns", "tns"]):
        return "Defines deterministic-tool boundary where LLM increment may be weak."
    if matches(blob, ["rag", "retrieval", "memory", "distillation", "fine-tuning"]):
        return "Motivates memory/retrieval/distillation ablations."
    if matches(blob, ["benchmark", "dataset", "evaluation"]):
        return "Helps position the semantic RTL repair benchmark."
    return "Background for AI-for-EDA framing."


def citable_claim(record: Dict[str, Any]) -> str:
    blob = text_blob(record)
    if matches(blob, ["rtlfixer", "syntax"]):
        return "LLM repair can be effective for RTL syntax or compile-error loops."
    if matches(blob, ["bug localization", "debugging", "debug"]):
        return "LLMs are being evaluated for Verilog/RTL debugging and fault localization."
    if matches(blob, ["formal", "assertion", "sva"]):
        return "Formal or assertion-based checks are emerging as evaluation aids, but not yet universal repair gates."
    if matches(blob, ["timing", "eco", "openroad", "opensta"]):
        return "Timing closure/ECO is mainly a tool-driven optimization problem."
    if matches(blob, ["benchmark", "dataset", "verilogeval", "hdlbits"]):
        return "Current AI-for-RTL benchmarks often emphasize generation or fixed testbench correctness."
    if matches(blob, ["rag", "retrieval", "memory", "distillation"]):
        return "Retrieval and adaptation are plausible mechanisms for improving LLM hardware workflows."
    return "LLM-for-EDA is expanding beyond generation toward verification, debugging, and optimization."


def overclaim_guard(record: Dict[str, Any]) -> str:
    blob = text_blob(record)
    if matches(blob, ["code generation", "rtl generation", "verilog generation"]):
        return "Do not claim it solves repair; use it as generation/benchmark background."
    if matches(blob, ["syntax", "compile"]) and not matches(blob, ["functional", "semantic", "formal"]):
        return "Do not generalize syntax repair to semantic correctness."
    if matches(blob, ["simulation", "testbench"]) and not matches(blob, ["formal equivalence", "lec"]):
        return "Do not overstate correctness beyond tested scenarios."
    if matches(blob, ["timing", "eco"]):
        return "Do not argue LLM beats deterministic STA/ECO without direct evidence."
    if matches(blob, ["adversarial", "bug injection"]):
        return "Do not imply the paper proves blue-agent learning unless explicitly evaluated."
    return "Use as supporting context; verify exact claims in full text before citing."


def reading_priority(record: Dict[str, Any]) -> str:
    title = clean(record.get("title", "")).lower()
    cites = int(record.get("citation_count") or 0)
    blob = text_blob(record)
    must_terms = ["r3a", "clover", "rtlfixer", "meic", "veridebug", "fixbench", "rtl-repair", "verirag", "buggen", "formal", "equivalence"]
    if any(term in title for term in must_terms) or (int(record.get("score") or 0) >= 5 and (matches(blob, ["repair", "debug", "formal equivalence", "bug localization"]) or cites >= 25)):
        return "应读全文"
    return "可先读摘要"


def build_graph(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    seen_edges: set[Tuple[str, str, str]] = set()

    add_node(
        nodes,
        ROOT_PROJECT_ID,
        "MicroSurgeon red-blue RTL repair agent",
        "my_project",
        description="Blue repair agent strengthened by red-team diverse bug generation, memory/distillation, and correctness gates.",
    )

    for gap_id, gap in GAPS.items():
        add_node(nodes, gap_id, gap["label"], "gap", description=gap["description"])
        add_edge(edges, seen_edges, ROOT_PROJECT_ID, gap_id, "addresses_gap")

    for node_type, concepts in CONCEPTS.items():
        for label in concepts:
            add_node(nodes, norm_id(node_type, label), label, node_type)

    paper_ids_by_category: Dict[str, List[str]] = defaultdict(list)
    concept_to_papers: Dict[str, List[str]] = defaultdict(list)

    for idx, record in enumerate(records, start=1):
        pid = f"paper_{idx:03d}"
        add_node(
            nodes,
            pid,
            clean(record.get("title", "")) or f"Untitled paper {idx}",
            "paper",
            year=record.get("year"),
            venue=clean(record.get("venue", "")),
            doi=clean(record.get("doi", "")),
            url=clean(record.get("url", "")),
            score=record.get("score"),
            category=category_label(record),
            citation_count=record.get("citation_count"),
        )
        paper_ids_by_category[category_label(record)].append(pid)
        blob = text_blob(record)

        for node_type, concepts in CONCEPTS.items():
            edge_type = {
                "method": "uses",
                "task": "addresses",
                "benchmark": "evaluates_on",
                "evidence_gate": "validates_with",
            }[node_type]
            for label, terms in concepts.items():
                if matches(blob, terms):
                    cid = norm_id(node_type, label)
                    add_edge(edges, seen_edges, pid, cid, edge_type)
                    concept_to_papers[cid].append(pid)

        for gap_id, gap in GAPS.items():
            if matches(blob, gap["keywords"]):
                for node_type, concepts in CONCEPTS.items():
                    for label, terms in concepts.items():
                        cid = norm_id(node_type, label)
                        if cid in nodes and matches(blob, terms):
                            add_edge(edges, seen_edges, cid, gap_id, "leaves_open")

    # Connect related papers conservatively within each category by citation rank.
    for _, pids in paper_ids_by_category.items():
        for a, b in zip(pids[:12], pids[1:12]):
            add_edge(edges, seen_edges, a, b, "related_to", reason="same_litwatch_category")

    # Add concept summary counts.
    degree = Counter()
    for edge in edges:
        degree[edge["source"]] += 1
        degree[edge["target"]] += 1
    for node in nodes.values():
        node["degree"] = degree[node["id"]]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "artifacts/lit_watch/candidates_screened.jsonl",
        "min_score": 4,
        "nodes": list(nodes.values()),
        "edges": edges,
        "records": records,
    }


def write_json(path: Path, graph: Dict[str, Any]) -> None:
    payload = {k: v for k, v in graph.items() if k != "records"}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_graphml(path: Path, graph: Dict[str, Any]) -> None:
    ET.register_namespace("", "http://graphml.graphdrawing.org/xmlns")
    root = ET.Element("graphml", xmlns="http://graphml.graphdrawing.org/xmlns")
    keys = [
        ("d0", "node", "label", "string"),
        ("d1", "node", "type", "string"),
        ("d2", "node", "year", "string"),
        ("d3", "node", "category", "string"),
        ("d4", "node", "score", "string"),
        ("d5", "edge", "type", "string"),
        ("d6", "edge", "reason", "string"),
    ]
    for key_id, scope, name, attr_type in keys:
        ET.SubElement(root, "key", id=key_id, **{"for": scope, "attr.name": name, "attr.type": attr_type})
    g = ET.SubElement(root, "graph", id="MicroSurgeonLitWatch", edgedefault="directed")
    for node in graph["nodes"]:
        n = ET.SubElement(g, "node", id=node["id"])
        for key_id, attr in [("d0", "label"), ("d1", "type"), ("d2", "year"), ("d3", "category"), ("d4", "score")]:
            val = node.get(attr)
            if val is not None and val != "":
                ET.SubElement(n, "data", key=key_id).text = str(val)
    for idx, edge in enumerate(graph["edges"], start=1):
        e = ET.SubElement(g, "edge", id=f"e{idx}", source=edge["source"], target=edge["target"])
        ET.SubElement(e, "data", key="d5").text = edge["type"]
        if edge.get("reason"):
            ET.SubElement(e, "data", key="d6").text = edge["reason"]
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def write_html(path: Path, graph: Dict[str, Any], *, static_layout: bool = False) -> None:
    data = {k: v for k, v in graph.items() if k != "records"}
    layout_mode = "Static layout" if static_layout else "Dynamic layout"
    auto_freeze_js = "true" if static_layout else "false"
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MicroSurgeon LitWatch Knowledge Graph</title>
  <style>
    :root {{
      --bg: #f7f8fb; --panel: #ffffff; --ink: #1f2937; --muted: #667085; --line: #d7dce5;
      --paper: #2563eb; --method: #0f766e; --task: #7c3aed; --gate: #b45309; --bench: #64748b;
      --gap: #dc2626; --project: #111827;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; background: var(--bg); color: var(--ink); }}
    header {{ padding: 14px 18px; background: var(--panel); border-bottom: 1px solid var(--line); display:flex; gap:16px; align-items:center; justify-content:space-between; }}
    h1 {{ font-size: 18px; margin: 0; font-weight: 650; }}
    .meta {{ color: var(--muted); font-size: 12px; }}
    main {{ display: grid; grid-template-columns: 300px 1fr 360px; height: calc(100vh - 58px); }}
    aside {{ background: var(--panel); border-right: 1px solid var(--line); padding: 14px; overflow:auto; }}
    #details {{ border-right: 0; border-left: 1px solid var(--line); }}
    canvas {{ width: 100%; height: 100%; display:block; background: #fbfcff; }}
    .legend {{ display:grid; gap:8px; margin: 12px 0; }}
    .legend label {{ display:flex; gap:8px; align-items:center; font-size: 13px; }}
    .dot {{ width: 11px; height: 11px; border-radius: 50%; display:inline-block; }}
    input[type="search"] {{ width: 100%; padding: 8px 10px; border: 1px solid var(--line); border-radius: 6px; }}
    .stat {{ display:grid; grid-template-columns: 1fr auto; gap: 6px; font-size: 13px; padding: 6px 0; border-bottom: 1px solid #eef1f6; }}
    .hint {{ color: var(--muted); font-size: 12px; line-height: 1.4; }}
    .node-title {{ font-weight: 650; margin-bottom: 8px; }}
    .badge {{ display:inline-block; padding: 2px 6px; border-radius: 4px; background:#eef2ff; margin: 2px; font-size: 12px; }}
    .small {{ color: var(--muted); font-size: 12px; }}
    button {{ padding: 7px 9px; border: 1px solid var(--line); border-radius: 6px; background: white; cursor:pointer; }}
  </style>
</head>
<body>
<header>
  <div>
    <h1>MicroSurgeon LitWatch Knowledge Graph</h1>
    <div class="meta">Generated {html.escape(graph["generated_at"])} · {len(graph["nodes"])} nodes · {len(graph["edges"])} edges · {html.escape(layout_mode)}</div>
  </div>
  <div>
    <button id="freeze">Freeze Layout</button>
    <button id="reset">Reset Layout</button>
  </div>
</header>
<main>
  <aside>
    <input id="search" type="search" placeholder="Search paper/method/task..." />
    <div class="legend" id="legend"></div>
    <p class="hint">Drag nodes to reposition. Click any node for details. Use Freeze Layout to stop graph motion. Paper-paper links are conservative <code>related_to</code> links within the same LitWatch category; no citation graph was inferred from metadata.</p>
    <h3>Counts</h3>
    <div id="stats"></div>
  </aside>
  <canvas id="graph"></canvas>
  <aside id="details">
    <div class="node-title">Select a node</div>
    <p class="hint">The graph highlights how papers support LLM/agent for EDA, RTL repair/debug, correctness gates, timing ECO boundaries, and MicroSurgeon novelty gaps.</p>
  </aside>
</main>
<script>
const graph = {json.dumps(data, ensure_ascii=False)};
const colors = {{paper:'#2563eb', method:'#0f766e', task:'#7c3aed', evidence_gate:'#b45309', benchmark:'#64748b', gap:'#dc2626', my_project:'#111827'}};
const visible = new Set(Object.keys(colors));
let search = '';
const canvas = document.getElementById('graph');
const ctx = canvas.getContext('2d');
let width=0, height=0, selected=null, dragging=null, layoutFrozen=false;
const autoFreeze = {auto_freeze_js};
const nodes = graph.nodes.map((n,i)=>({{...n, x: 250 + (i%18)*38, y: 120 + Math.floor(i/18)*32, vx:0, vy:0}}));
const byId = Object.fromEntries(nodes.map(n=>[n.id,n]));
const edges = graph.edges.filter(e=>byId[e.source] && byId[e.target]);
function resize(){{ const r=canvas.getBoundingClientRect(); width=canvas.width=Math.floor(r.width*devicePixelRatio); height=canvas.height=Math.floor(r.height*devicePixelRatio); ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0); }}
window.addEventListener('resize', resize); resize();
function nodeRadius(n){{ return n.type==='paper' ? Math.max(4, Math.min(11, 4 + (n.score||0))) : n.type==='gap' ? 9 : n.type==='my_project' ? 12 : 7; }}
function isVisible(n){{ return visible.has(n.type) && (!search || (n.label||'').toLowerCase().includes(search) || (n.category||'').toLowerCase().includes(search)); }}
function freezeLayout(){{ layoutFrozen=true; nodes.forEach(n=>{{ n.vx=0; n.vy=0; }}); document.getElementById('freeze').textContent='Layout Frozen'; }}
function unfreezeLayout(){{ layoutFrozen=false; document.getElementById('freeze').textContent='Freeze Layout'; }}
function tick(){{
  if(layoutFrozen) return;
  const shown = nodes.filter(isVisible);
  for (const e of edges) {{
    const a=byId[e.source], b=byId[e.target]; if(!isVisible(a)||!isVisible(b)) continue;
    const dx=b.x-a.x, dy=b.y-a.y, d=Math.sqrt(dx*dx+dy*dy)||1, target=e.type==='related_to'?70:125, k=0.006;
    const f=(d-target)*k; a.vx+=dx/d*f; a.vy+=dy/d*f; b.vx-=dx/d*f; b.vy-=dy/d*f;
  }}
  for(let i=0;i<shown.length;i++) for(let j=i+1;j<shown.length;j++) {{
    const a=shown[i], b=shown[j], dx=b.x-a.x, dy=b.y-a.y, d2=dx*dx+dy*dy+0.01, d=Math.sqrt(d2), f=70/d2;
    a.vx-=dx/d*f; a.vy-=dy/d*f; b.vx+=dx/d*f; b.vy+=dy/d*f;
  }}
  for (const n of shown) {{
    if(n===dragging) continue;
    n.vx += ((width/devicePixelRatio)/2 - n.x)*0.0008; n.vy += ((height/devicePixelRatio)/2 - n.y)*0.0008;
    n.x += n.vx; n.y += n.vy; n.vx*=0.86; n.vy*=0.86;
    n.x=Math.max(20, Math.min((width/devicePixelRatio)-20, n.x)); n.y=Math.max(20, Math.min((height/devicePixelRatio)-20, n.y));
  }}
}}
function draw(){{
  tick(); ctx.clearRect(0,0,width,height);
  ctx.lineWidth=1;
  for (const e of edges) {{
    const a=byId[e.source], b=byId[e.target]; if(!isVisible(a)||!isVisible(b)) continue;
    ctx.strokeStyle = e.type==='addresses_gap' ? 'rgba(220,38,38,.45)' : e.type==='leaves_open' ? 'rgba(220,38,38,.25)' : 'rgba(100,116,139,.18)';
    ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
  }}
  for (const n of nodes) {{
    if(!isVisible(n)) continue; const r=nodeRadius(n);
    ctx.fillStyle=colors[n.type]||'#555'; ctx.beginPath(); ctx.arc(n.x,n.y,r,0,Math.PI*2); ctx.fill();
    if(n===selected) {{ ctx.strokeStyle='#111827'; ctx.lineWidth=3; ctx.stroke(); }}
    if(n.type!=='paper' || n.degree>8) {{ ctx.fillStyle='#111827'; ctx.font='11px Segoe UI'; ctx.fillText((n.label||'').slice(0,34), n.x+r+3, n.y+4); }}
  }}
  requestAnimationFrame(draw);
}}
draw();
function nearest(x,y){{ let best=null, bd=9999; for(const n of nodes){{ if(!isVisible(n)) continue; const d=Math.hypot(n.x-x,n.y-y); if(d<bd && d<18){{best=n;bd=d;}} }} return best; }}
canvas.addEventListener('mousedown', e=>{{ const r=canvas.getBoundingClientRect(); dragging=nearest(e.clientX-r.left,e.clientY-r.top); selected=dragging; showDetails(selected); }});
canvas.addEventListener('mousemove', e=>{{ if(dragging){{ const r=canvas.getBoundingClientRect(); dragging.x=e.clientX-r.left; dragging.y=e.clientY-r.top; dragging.vx=dragging.vy=0; }} }});
canvas.addEventListener('mouseup', ()=>dragging=null);
function showDetails(n){{ const d=document.getElementById('details'); if(!n) return; const out=edges.filter(e=>e.source===n.id).slice(0,25).map(e=>`<span class="badge">${{e.type}} → ${{(byId[e.target]||{{}}).label||e.target}}</span>`).join(''); const inn=edges.filter(e=>e.target===n.id).slice(0,25).map(e=>`<span class="badge">${{e.type}} ← ${{(byId[e.source]||{{}}).label||e.source}}</span>`).join(''); d.innerHTML=`<div class="node-title">${{n.label}}</div><div class="small">${{n.type}}${{n.year?' · '+n.year:''}}${{n.category?' · '+n.category:''}}</div><p>${{n.description||''}}</p><p>${{n.doi?'<b>DOI:</b> '+n.doi:''}}</p><p>${{n.url?'<a href="'+n.url+'" target="_blank">Open source URL</a>':''}}</p><h3>Outgoing</h3>${{out||'<p class="hint">None</p>'}}<h3>Incoming</h3>${{inn||'<p class="hint">None</p>'}}`; }}
const typeCounts = nodes.reduce((a,n)=>(a[n.type]=(a[n.type]||0)+1,a),{{}});
document.getElementById('stats').innerHTML=Object.entries(typeCounts).map(([k,v])=>`<div class="stat"><span>${{k}}</span><b>${{v}}</b></div>`).join('');
document.getElementById('legend').innerHTML=Object.entries(colors).map(([k,c])=>`<label><input type="checkbox" checked data-type="${{k}}"><span class="dot" style="background:${{c}}"></span>${{k}}</label>`).join('');
document.getElementById('legend').addEventListener('change', e=>{{ if(e.target.dataset.type){{ e.target.checked ? visible.add(e.target.dataset.type) : visible.delete(e.target.dataset.type); }} }});
document.getElementById('search').addEventListener('input', e=>{{ search=e.target.value.toLowerCase().trim(); }});
document.getElementById('freeze').addEventListener('click', freezeLayout);
document.getElementById('reset').addEventListener('click', ()=>{{ unfreezeLayout(); nodes.forEach((n,i)=>{{n.x=250+(i%18)*38; n.y=120+Math.floor(i/18)*32; n.vx=n.vy=0;}}); if(autoFreeze) setTimeout(freezeLayout, 5000); }});
if(autoFreeze) setTimeout(freezeLayout, 5000);
</script>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")


def write_markdown(path: Path, graph: Dict[str, Any]) -> None:
    records = graph["records"]
    node_counts = Counter(n["type"] for n in graph["nodes"])
    edge_counts = Counter(e["type"] for e in graph["edges"])
    category_counts = Counter(category_label(r) for r in records)

    lines = [
        "# MicroSurgeon LitWatch Literature Map",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Input: `artifacts/lit_watch/candidates_screened.jsonl` filtered to `score >= 4`, matching the imported Zotero set.",
        "",
        "## Graph Summary",
        "",
        f"- Nodes: {len(graph['nodes'])}",
        f"- Edges: {len(graph['edges'])}",
        f"- Papers: {node_counts.get('paper', 0)}",
        f"- Methods: {node_counts.get('method', 0)}",
        f"- Tasks: {node_counts.get('task', 0)}",
        f"- Evidence gates: {node_counts.get('evidence_gate', 0)}",
        f"- Benchmarks: {node_counts.get('benchmark', 0)}",
        f"- Gaps: {node_counts.get('gap', 0)}",
        "",
        "## Edge Counts",
        "",
    ]
    for edge_type, count in sorted(edge_counts.items()):
        lines.append(f"- `{edge_type}`: {count}")
    lines.extend(["", "## Category Counts", ""])
    for category, count in sorted(category_counts.items()):
        lines.append(f"- {category}: {count}")

    lines.extend(
        [
            "",
            "## How To Read The Graph",
            "",
            "- `paper -> method` uses: the paper explicitly uses or studies that method family.",
            "- `paper -> task` addresses: the paper targets that EDA/RTL task.",
            "- `paper -> benchmark` evaluates_on: the paper mentions or is categorized around that benchmark or dataset family.",
            "- `paper -> evidence_gate` validates_with: the paper relies on that validation signal.",
            "- `paper -> paper` related_to: conservative same-category relation, not a citation claim.",
            "- `method -> gap` leaves_open: the method touches a gap area but does not close the MicroSurgeon claim by itself.",
            "- `my_project -> gap` addresses_gap: proposed MicroSurgeon contribution areas.",
            "",
            "## Gap Map",
            "",
        ]
    )
    for gap_id, gap in GAPS.items():
        incoming = [e for e in graph["edges"] if e["target"] == gap_id]
        lines.append(f"- **{gap['label']}**: {gap['description']} Incoming edges: {len(incoming)}.")

    lines.extend(
        [
            "",
            "## Markdown 总表",
            "",
            "| 文献 | 类别 | 与我项目的关系 | 可引用的观点 | 不能过度声称的地方 | 后续应读全文/只读摘要 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for record in records:
        title = clean(record.get("title", "")).replace("|", "\\|")
        doi = clean(record.get("doi", ""))
        title_cell = f"{title} ({record.get('year') or 'n.d.'})"
        if doi:
            title_cell += f"<br>DOI: `{doi}`"
        row = [
            title_cell,
            category_label(record),
            project_relation(record),
            citable_claim(record),
            overclaim_guard(record),
            reading_priority(record),
        ]
        lines.append("| " + " | ".join(cell.replace("\n", " ") for cell in row) + " |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate MicroSurgeon literature knowledge graph.")
    parser.add_argument("--input", type=Path, default=Path("artifacts/lit_watch/candidates_screened.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/lit_watch"))
    parser.add_argument("--min-score", type=int, default=4)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    records = load_records(args.input, args.min_score)
    graph = build_graph(records)
    graph["source"] = str(args.input)
    graph["min_score"] = args.min_score

    json_path = args.out_dir / "literature_graph.json"
    graphml_path = args.out_dir / "literature_graph.graphml"
    html_path = args.out_dir / "literature_graph.html"
    static_html_path = args.out_dir / "literature_graph_static.html"
    md_path = args.out_dir / "literature_map.md"

    write_json(json_path, graph)
    write_graphml(graphml_path, graph)
    write_html(html_path, graph, static_layout=False)
    write_html(static_html_path, graph, static_layout=True)
    write_markdown(md_path, graph)

    print(f"Papers: {len(records)}")
    print(f"Nodes: {len(graph['nodes'])}")
    print(f"Edges: {len(graph['edges'])}")
    print(f"Wrote: {html_path}")
    print(f"Wrote: {static_html_path}")
    print(f"Wrote: {graphml_path}")
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
