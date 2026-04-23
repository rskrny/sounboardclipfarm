"""
Knowledge graph visualization generator.

Produces a self-contained HTML file with an interactive D3.js
force-directed graph. Zero external dependencies at runtime.
D3.js is loaded from CDN. The graph data is embedded in the HTML.

The visualization shows:
- Nodes = chunks, colored by domain, sized by token count
- Edges = relationships (sequence within file, shared domain)
- Interactive: drag nodes, zoom, hover for details, search
- Updates every time the index is rebuilt

Usage:
    python -m retrieval.visualize          Generate viz from current index
    python -m retrieval.visualize --open   Generate and open in browser
"""

import json
import webbrowser
from pathlib import Path
from typing import Optional

from .config import RetrievalConfig
from .store import Store


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Knowledge Graph &mdash; Context Engineering</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: #0a0a0f;
    color: #e0e0e0;
    overflow: hidden;
}
#container { width: 100vw; height: 100vh; position: relative; }
svg#graph { width: 100%; height: 100%; }

/* Tab bar */
#tab-bar {
    position: absolute; top: 16px; right: 16px;
    display: flex; gap: 4px; z-index: 15;
}
.tab-btn {
    background: rgba(10,10,15,0.85);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    padding: 8px 18px;
    color: #888;
    font-size: 13px; font-weight: 500;
    cursor: pointer;
    backdrop-filter: blur(12px);
    transition: all 0.2s;
}
.tab-btn:hover { color: #ccc; border-color: rgba(255,255,255,0.3); }
.tab-btn.active { color: #4fc3f7; border-color: #4fc3f7; background: rgba(79,195,247,0.08); }

/* HUD overlay */
#hud {
    position: absolute; top: 16px; left: 16px;
    background: rgba(10, 10, 15, 0.85);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 16px 20px;
    backdrop-filter: blur(12px);
    min-width: 280px;
    max-width: 320px;
    z-index: 10;
}
#hud h1 { font-size: 14px; font-weight: 600; color: #fff; margin-bottom: 8px; }
#hud .stat { font-size: 12px; color: #888; margin: 2px 0; }
#hud .stat span { color: #4fc3f7; font-weight: 600; }

#search-box {
    margin-top: 10px; width: 100%;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    padding: 8px 12px;
    color: #fff; font-size: 13px;
    outline: none;
}
#search-box:focus { border-color: #4fc3f7; }
#search-box::placeholder { color: #555; }

/* Filter pills */
.filter-section { margin-top: 10px; }
.filter-label { font-size: 10px; color: #666; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px; }
.filter-row { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.filter-pill {
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 11px;
    cursor: pointer;
    border: 1px solid rgba(255,255,255,0.15);
    background: rgba(255,255,255,0.04);
    color: #aaa;
    transition: all 0.15s;
    user-select: none;
}
.filter-pill:hover { border-color: rgba(255,255,255,0.3); color: #ddd; }
.filter-pill.active { border-color: currentColor; background: rgba(255,255,255,0.08); color: #fff; }

/* Token sparkline */
#token-sparkline {
    margin-top: 10px;
    height: 20px;
    border-radius: 4px;
    overflow: hidden;
    display: flex;
    position: relative;
}
#token-sparkline .spark-seg {
    height: 100%;
    transition: opacity 0.15s;
    position: relative;
}
#token-sparkline .spark-seg:hover { opacity: 0.8; }
#spark-tooltip {
    position: absolute;
    background: rgba(0,0,0,0.9);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    color: #fff;
    pointer-events: none;
    opacity: 0;
    z-index: 25;
    white-space: nowrap;
}

/* Legend */
#legend {
    position: absolute; bottom: 16px; left: 16px;
    background: rgba(10, 10, 15, 0.85);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px;
    padding: 12px 16px;
    backdrop-filter: blur(12px);
    z-index: 10;
}
#legend h3 { font-size: 11px; color: #888; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 1px; }
.legend-item {
    display: flex; align-items: center; gap: 8px; margin: 3px 0; font-size: 12px;
    cursor: pointer; transition: opacity 0.15s;
}
.legend-item:hover { opacity: 0.8; }
.legend-item .count { color: #666; font-size: 10px; margin-left: auto; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }

/* Tooltip */
#tooltip {
    position: absolute;
    background: rgba(10, 10, 15, 0.95);
    border: 1px solid rgba(79, 195, 247, 0.3);
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 12px;
    max-width: 350px;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s;
    z-index: 20;
    backdrop-filter: blur(12px);
}
#tooltip .tt-title { font-weight: 600; color: #4fc3f7; margin-bottom: 4px; }
#tooltip .tt-file { color: #888; font-size: 11px; }
#tooltip .tt-meta { color: #aaa; margin-top: 6px; font-size: 11px; }
#tooltip .tt-hint { color: #555; margin-top: 6px; font-size: 10px; font-style: italic; }

/* Detail panel */
#detail-panel {
    position: absolute; top: 0; right: 0;
    width: 440px; height: 100vh;
    background: rgba(10, 10, 15, 0.95);
    border-left: 1px solid rgba(255,255,255,0.1);
    backdrop-filter: blur(16px);
    transform: translateX(100%);
    transition: transform 0.25s ease;
    z-index: 30;
    display: flex; flex-direction: column;
    overflow: hidden;
}
#detail-panel.open { transform: translateX(0); }

.detail-header {
    padding: 20px 24px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    flex-shrink: 0;
}
.detail-close {
    position: absolute; top: 16px; right: 16px;
    width: 28px; height: 28px;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.15);
    background: rgba(255,255,255,0.04);
    color: #888;
    font-size: 16px;
    cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.15s;
}
.detail-close:hover { color: #fff; border-color: rgba(255,255,255,0.3); }
.detail-title { font-size: 16px; font-weight: 600; color: #fff; margin-bottom: 8px; padding-right: 40px; line-height: 1.3; }

.detail-breadcrumb {
    display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px;
    font-size: 11px; color: #888;
}
.detail-breadcrumb .bc-item { color: #666; }
.detail-breadcrumb .bc-sep { color: #444; }
.detail-breadcrumb .bc-item:last-child { color: #4fc3f7; }

.detail-badges { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.badge {
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 500;
}
.badge-domain { border: 1px solid; }
.badge-type {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    color: #aaa;
}
.badge-tokens {
    background: rgba(79,195,247,0.08);
    border: 1px solid rgba(79,195,247,0.2);
    color: #4fc3f7;
}
.badge-tag {
    background: rgba(171,71,188,0.08);
    border: 1px solid rgba(171,71,188,0.2);
    color: #ce93d8;
}

.detail-file {
    font-size: 12px; color: #888;
    font-family: 'SF Mono', 'Consolas', monospace;
}

.detail-body {
    flex: 1; overflow-y: auto; padding: 16px 24px;
}

.detail-section-title {
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.8px;
    color: #666; margin: 16px 0 8px;
}
.detail-section-title:first-child { margin-top: 0; }

.detail-text {
    font-size: 13px; line-height: 1.6; color: #ccc;
    white-space: pre-wrap; word-wrap: break-word;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    padding: 14px 16px;
    max-height: 400px;
    overflow-y: auto;
}
.detail-text.code-content {
    font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
    font-size: 12px;
    line-height: 1.5;
    background: rgba(255,255,255,0.03);
    tab-size: 4;
}

.connected-list { list-style: none; }
.connected-item {
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    margin: 2px 0;
    display: flex; align-items: center; gap: 8px;
    transition: background 0.1s;
    color: #aaa;
}
.connected-item:hover { background: rgba(255,255,255,0.05); color: #fff; }
.connected-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.connected-type { color: #555; font-size: 10px; margin-left: auto; }

/* Minimap */
#minimap {
    position: absolute; bottom: 16px; right: 16px;
    width: 180px; height: 120px;
    background: rgba(10,10,15,0.85);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    backdrop-filter: blur(12px);
    z-index: 10;
    overflow: hidden;
}
#minimap canvas { width: 100%; height: 100%; }
.minimap-viewport {
    position: absolute;
    border: 1px solid rgba(79,195,247,0.5);
    background: rgba(79,195,247,0.05);
    pointer-events: none;
}

/* Dashboard view */
#dashboard {
    position: absolute; top: 0; left: 0;
    width: 100vw; height: 100vh;
    background: #0a0a0f;
    display: none;
    overflow-y: auto;
    padding: 60px 40px 40px;
    z-index: 5;
}
#dashboard.active { display: block; }

.dash-title { font-size: 22px; font-weight: 600; color: #fff; margin-bottom: 24px; }

.dash-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
}
.dash-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 20px;
}
.dash-card .card-label { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.8px; }
.dash-card .card-value { font-size: 28px; font-weight: 600; color: #fff; margin-top: 4px; }
.dash-card .card-sub { font-size: 12px; color: #555; margin-top: 2px; }

.dash-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-bottom: 32px;
}
@media (max-width: 900px) { .dash-row { grid-template-columns: 1fr; } }

.dash-panel {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 24px;
}
.dash-panel h2 { font-size: 14px; font-weight: 600; color: #fff; margin-bottom: 16px; }

/* Links */
.link { stroke-opacity: 0.15; }
.link.sequence { stroke: #4fc3f7; }
.link.domain { stroke: #ab47bc; stroke-dasharray: 4 2; }
.link.highlight { stroke-opacity: 0.6; stroke-width: 2px; }

/* Nodes */
.node circle { stroke: rgba(255,255,255,0.2); stroke-width: 1px; cursor: pointer; }
.node circle:hover { stroke: #fff; stroke-width: 2px; }
.node.dimmed circle { opacity: 0.15; }
.node.highlight circle { stroke: #fff; stroke-width: 2.5px; filter: drop-shadow(0 0 6px rgba(79, 195, 247, 0.5)); }
.node.selected circle { stroke: #4fc3f7; stroke-width: 3px; filter: drop-shadow(0 0 8px rgba(79, 195, 247, 0.6)); }

/* Scrollbar styling */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
</style>
</head>
<body>
<div id="container">
    <svg id="graph"></svg>

    <!-- Tab bar -->
    <div id="tab-bar">
        <div class="tab-btn active" data-view="graph">Graph</div>
        <div class="tab-btn" data-view="dashboard">Tokens</div>
    </div>

    <!-- HUD -->
    <div id="hud">
        <h1>Knowledge Graph</h1>
        <div class="stat">Chunks: <span id="stat-chunks">0</span></div>
        <div class="stat">Files: <span id="stat-files">0</span></div>
        <div class="stat">Domains: <span id="stat-domains">0</span></div>
        <div class="stat">Total tokens: <span id="stat-tokens">0</span></div>
        <input type="text" id="search-box" placeholder="Search chunks...">

        <div class="filter-section">
            <div class="filter-label">Domains</div>
            <div class="filter-row" id="domain-filters"></div>
        </div>
        <div class="filter-section">
            <div class="filter-label">Content Type</div>
            <div class="filter-row" id="type-filters"></div>
        </div>

        <div id="token-sparkline"></div>
        <div id="spark-tooltip"></div>
    </div>

    <!-- Legend -->
    <div id="legend"></div>

    <!-- Tooltip -->
    <div id="tooltip"></div>

    <!-- Detail panel -->
    <div id="detail-panel">
        <div class="detail-header">
            <button class="detail-close" id="detail-close">&times;</button>
            <div class="detail-title" id="detail-title"></div>
            <div class="detail-breadcrumb" id="detail-breadcrumb"></div>
            <div class="detail-badges" id="detail-badges"></div>
            <div class="detail-file" id="detail-file"></div>
        </div>
        <div class="detail-body" id="detail-body"></div>
    </div>

    <!-- Minimap -->
    <div id="minimap">
        <canvas id="minimap-canvas"></canvas>
    </div>

    <!-- Dashboard -->
    <div id="dashboard">
        <div class="dash-title">Token Budget Overview</div>
        <div class="dash-cards" id="dash-cards"></div>
        <div class="dash-row">
            <div class="dash-panel">
                <h2>Tokens by Domain</h2>
                <div id="chart-domain"></div>
            </div>
            <div class="dash-panel">
                <h2>Content Type Distribution</h2>
                <div id="chart-types"></div>
            </div>
        </div>
        <div class="dash-row">
            <div class="dash-panel" style="grid-column: span 2;">
                <h2>Tokens by File</h2>
                <div id="chart-files"></div>
            </div>
        </div>
    </div>
</div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
// --- Embedded graph data ---
const GRAPH_DATA = %%GRAPH_JSON%%;
const STATS = GRAPH_DATA.stats || {};

// --- Color palette by domain ---
const DOMAIN_COLORS = {
    'business-consulting': '#4fc3f7',
    'context-engineering': '#ab47bc',
    'software-dev': '#66bb6a',
    'course-creation': '#ffa726',
    'business-law': '#ef5350',
    'accounting-tax': '#26a69a',
    'research-authoring': '#ec407a',
    'gtm-strategy': '#7e57c2',
    'shared': '#78909c',
    null: '#78909c',
    undefined: '#78909c',
};
const DEFAULT_COLOR = '#78909c';
const TYPE_COLORS = { prose: '#4fc3f7', code: '#66bb6a', table: '#ffa726', metadata: '#78909c', mixed: '#ce93d8' };

function getColor(domain) { return DOMAIN_COLORS[domain] || DEFAULT_COLOR; }
function getRadius(tokens) { return Math.max(4, Math.min(16, Math.sqrt(tokens || 50) * 0.9)); }
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// --- Setup ---
let currentView = 'graph';
const width = window.innerWidth;
const height = window.innerHeight;
const svg = d3.select('#graph');
const g = svg.append('g');

// State
let activeFilters = { domains: new Set(), types: new Set() };
let selectedNode = null;
let isDragging = false;

// Zoom
const zoom = d3.zoom()
    .scaleExtent([0.1, 8])
    .on('zoom', (e) => {
        g.attr('transform', e.transform);
        updateMinimap(e.transform);
    });
svg.call(zoom);

// Data
const nodes = GRAPH_DATA.nodes;
const edges = GRAPH_DATA.edges;

// Compute connected neighbors for each node
const neighborMap = {};
nodes.forEach(n => { neighborMap[n.id] = new Set(); });
edges.forEach(e => {
    const sid = typeof e.source === 'object' ? e.source.id : e.source;
    const tid = typeof e.target === 'object' ? e.target.id : e.target;
    if (neighborMap[sid]) neighborMap[sid].add(tid);
    if (neighborMap[tid]) neighborMap[tid].add(sid);
});

// Stats
const fileSet = new Set(nodes.map(n => n.source_file));
const domainSet = new Set(nodes.map(n => n.domain).filter(Boolean));
const totalTokens = STATS.total_tokens || nodes.reduce((s, n) => s + (n.tokens || 0), 0);

document.getElementById('stat-chunks').textContent = nodes.length;
document.getElementById('stat-files').textContent = fileSet.size;
document.getElementById('stat-domains').textContent = domainSet.size;
document.getElementById('stat-tokens').textContent = totalTokens.toLocaleString();

// --- Domain filter pills ---
const domainFilters = document.getElementById('domain-filters');
const allDomainsList = ['all', ...domainSet, 'shared'];
allDomainsList.forEach(d => {
    const pill = document.createElement('div');
    pill.className = 'filter-pill' + (d === 'all' ? ' active' : '');
    pill.textContent = d === 'all' ? 'All' : d;
    if (d !== 'all') pill.style.color = getColor(d === 'shared' ? null : d);
    pill.dataset.domain = d;
    pill.addEventListener('click', () => toggleDomainFilter(d));
    domainFilters.appendChild(pill);
});

function toggleDomainFilter(domain) {
    if (domain === 'all') {
        activeFilters.domains.clear();
        domainFilters.querySelectorAll('.filter-pill').forEach(p => {
            p.classList.toggle('active', p.dataset.domain === 'all');
        });
    } else {
        const allPill = domainFilters.querySelector('[data-domain="all"]');
        allPill.classList.remove('active');
        const pill = domainFilters.querySelector(`[data-domain="${domain}"]`);
        if (activeFilters.domains.has(domain)) {
            activeFilters.domains.delete(domain);
            pill.classList.remove('active');
        } else {
            activeFilters.domains.add(domain);
            pill.classList.add('active');
        }
        if (activeFilters.domains.size === 0) allPill.classList.add('active');
    }
    applyFilters();
}

// --- Content type filter pills ---
const typeFilters = document.getElementById('type-filters');
const contentTypes = [...new Set(nodes.map(n => n.content_type).filter(Boolean))];
['all', ...contentTypes].forEach(t => {
    const pill = document.createElement('div');
    pill.className = 'filter-pill' + (t === 'all' ? ' active' : '');
    pill.textContent = t === 'all' ? 'All' : t;
    if (t !== 'all') pill.style.color = TYPE_COLORS[t] || '#888';
    pill.dataset.type = t;
    pill.addEventListener('click', () => toggleTypeFilter(t));
    typeFilters.appendChild(pill);
});

function toggleTypeFilter(type) {
    if (type === 'all') {
        activeFilters.types.clear();
        typeFilters.querySelectorAll('.filter-pill').forEach(p => {
            p.classList.toggle('active', p.dataset.type === 'all');
        });
    } else {
        const allPill = typeFilters.querySelector('[data-type="all"]');
        allPill.classList.remove('active');
        const pill = typeFilters.querySelector(`[data-type="${type}"]`);
        if (activeFilters.types.has(type)) {
            activeFilters.types.delete(type);
            pill.classList.remove('active');
        } else {
            activeFilters.types.add(type);
            pill.classList.add('active');
        }
        if (activeFilters.types.size === 0) allPill.classList.add('active');
    }
    applyFilters();
}

function applyFilters() {
    const hasDomain = activeFilters.domains.size > 0;
    const hasType = activeFilters.types.size > 0;
    node.classed('dimmed', d => {
        if (hasDomain) {
            const nd = d.domain || 'shared';
            if (!activeFilters.domains.has(nd)) return true;
        }
        if (hasType) {
            if (!activeFilters.types.has(d.content_type)) return true;
        }
        return false;
    });
}

// --- Token sparkline ---
const sparkContainer = document.getElementById('token-sparkline');
const sparkTooltip = document.getElementById('spark-tooltip');
if (STATS.tokens_by_domain && STATS.tokens_by_domain.length > 0) {
    const total = STATS.tokens_by_domain.reduce((s, d) => s + d.tokens, 0);
    STATS.tokens_by_domain.forEach(d => {
        const seg = document.createElement('div');
        seg.className = 'spark-seg';
        const pct = (d.tokens / total * 100);
        seg.style.width = Math.max(pct, 2) + '%';
        seg.style.background = getColor(d.domain === 'shared' ? null : d.domain);
        seg.addEventListener('mouseenter', (e) => {
            sparkTooltip.textContent = `${d.domain}: ${d.tokens.toLocaleString()} tokens (${pct.toFixed(1)}%)`;
            sparkTooltip.style.opacity = 1;
            const rect = sparkContainer.getBoundingClientRect();
            sparkTooltip.style.left = (e.clientX - rect.left) + 'px';
            sparkTooltip.style.top = (rect.top - 28) + 'px';
        });
        seg.addEventListener('mouseleave', () => { sparkTooltip.style.opacity = 0; });
        sparkContainer.appendChild(seg);
    });
}

// --- Legend with counts ---
const legendEl = document.getElementById('legend');
legendEl.innerHTML = '<h3>Domains</h3>';
const domainCounts = {};
nodes.forEach(n => {
    const d = n.domain || 'shared';
    domainCounts[d] = (domainCounts[d] || 0) + 1;
});
[...domainSet, null].forEach(d => {
    const label = d || 'shared';
    const color = getColor(d);
    const count = domainCounts[label] || domainCounts[d] || 0;
    const item = document.createElement('div');
    item.className = 'legend-item';
    item.innerHTML = `<div class="legend-dot" style="background:${color}"></div><span>${label}</span><span class="count">${count}</span>`;
    item.addEventListener('click', () => toggleDomainFilter(label));
    legendEl.appendChild(item);
});

// --- Force simulation ---
const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(40).strength(0.3))
    .force('charge', d3.forceManyBody().strength(-60).distanceMax(200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(d => getRadius(d.tokens) + 2))
    .force('x', d3.forceX(width / 2).strength(0.03))
    .force('y', d3.forceY(height / 2).strength(0.03));

// --- Draw edges ---
const link = g.append('g')
    .selectAll('line')
    .data(edges)
    .join('line')
    .attr('class', d => `link ${d.type}`);

// --- Draw nodes ---
const node = g.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .attr('class', 'node')
    .call(d3.drag()
        .on('start', dragStart)
        .on('drag', dragging)
        .on('end', dragEnd));

node.append('circle')
    .attr('r', d => getRadius(d.tokens))
    .attr('fill', d => getColor(d.domain));

// --- Tooltip (hover) ---
const tooltip = document.getElementById('tooltip');

node.on('mouseover', (event, d) => {
    if (isDragging) return;
    tooltip.innerHTML = `
        <div class="tt-title">${escapeHtml(d.label)}</div>
        <div class="tt-file">${escapeHtml(d.source_file)}</div>
        <div class="tt-meta">
            ${d.domain || 'shared'} &middot; ${d.content_type} &middot; ~${d.tokens} tokens
        </div>
        <div class="tt-hint">Click to view details</div>
    `;
    tooltip.style.opacity = 1;
    tooltip.style.left = (event.pageX + 14) + 'px';
    tooltip.style.top = (event.pageY - 10) + 'px';

    // Highlight neighbors
    const connected = new Set(neighborMap[d.id] || []);
    connected.add(d.id);
    node.classed('dimmed', n => !connected.has(n.id));
    node.classed('highlight', n => n.id === d.id);
    link.classed('highlight', e => {
        const sid = typeof e.source === 'object' ? e.source.id : e.source;
        const tid = typeof e.target === 'object' ? e.target.id : e.target;
        return sid === d.id || tid === d.id;
    });
})
.on('mousemove', (event) => {
    tooltip.style.left = (event.pageX + 14) + 'px';
    tooltip.style.top = (event.pageY - 10) + 'px';
})
.on('mouseout', () => {
    tooltip.style.opacity = 0;
    if (!selectedNode) {
        node.classed('dimmed', false).classed('highlight', false);
        link.classed('highlight', false);
        applyFilters();
    }
});

// --- Click to open detail panel ---
node.on('click', (event, d) => {
    if (isDragging) return;
    event.stopPropagation();
    openDetailPanel(d);
});

// Close panel on background click
svg.on('click', () => { closeDetailPanel(); });

function openDetailPanel(d) {
    selectedNode = d;
    node.classed('selected', n => n.id === d.id);

    const panel = document.getElementById('detail-panel');
    const titleEl = document.getElementById('detail-title');
    const bcEl = document.getElementById('detail-breadcrumb');
    const badgesEl = document.getElementById('detail-badges');
    const fileEl = document.getElementById('detail-file');
    const bodyEl = document.getElementById('detail-body');

    // Title
    titleEl.textContent = d.label;

    // Breadcrumb
    const hp = d.header_path || [];
    if (hp.length > 0) {
        bcEl.innerHTML = hp.map((h, i) =>
            `<span class="bc-item">${escapeHtml(h)}</span>` +
            (i < hp.length - 1 ? '<span class="bc-sep">/</span>' : '')
        ).join('');
    } else {
        bcEl.innerHTML = `<span class="bc-item">${escapeHtml(d.source_file)}</span>`;
    }

    // Badges
    const domainColor = getColor(d.domain);
    let badgeHtml = `<span class="badge badge-domain" style="color:${domainColor};border-color:${domainColor}">${d.domain || 'shared'}</span>`;
    badgeHtml += `<span class="badge badge-type">${d.content_type}</span>`;
    badgeHtml += `<span class="badge badge-tokens">~${d.tokens} tokens</span>`;
    if (d.tags && d.tags.length > 0) {
        d.tags.forEach(t => {
            badgeHtml += `<span class="badge badge-tag">${escapeHtml(t)}</span>`;
        });
    }
    badgesEl.innerHTML = badgeHtml;

    // File info
    const lineInfo = (d.start_line && d.end_line) ? ` L${d.start_line}-${d.end_line}` : '';
    fileEl.textContent = d.source_file + lineInfo;

    // Body: full text + connected chunks
    let bodyHtml = '<div class="detail-section-title">Content</div>';

    const fullText = (GRAPH_DATA.full_texts && GRAPH_DATA.full_texts[d.id]) || '';
    const isCode = d.content_type === 'code';
    bodyHtml += `<div class="detail-text${isCode ? ' code-content' : ''}">${escapeHtml(fullText)}</div>`;

    // Connected chunks
    const neighbors = [...(neighborMap[d.id] || [])];
    if (neighbors.length > 0) {
        bodyHtml += '<div class="detail-section-title">Connected Chunks</div>';
        bodyHtml += '<ul class="connected-list">';
        neighbors.forEach(nid => {
            const neighbor = nodes.find(n => n.id === nid);
            if (neighbor) {
                const nc = getColor(neighbor.domain);
                bodyHtml += `<li class="connected-item" data-node-id="${nid}">
                    <span class="connected-dot" style="background:${nc}"></span>
                    ${escapeHtml(neighbor.label)}
                    <span class="connected-type">${neighbor.content_type}</span>
                </li>`;
            }
        });
        bodyHtml += '</ul>';
    }

    bodyEl.innerHTML = bodyHtml;

    // Click handler for connected items
    bodyEl.querySelectorAll('.connected-item').forEach(item => {
        item.addEventListener('click', () => {
            const nid = parseInt(item.dataset.nodeId);
            const targetNode = nodes.find(n => n.id === nid);
            if (targetNode) {
                openDetailPanel(targetNode);
                // Center graph on node
                const transform = d3.zoomTransform(svg.node());
                svg.transition().duration(500).call(
                    zoom.transform,
                    d3.zoomIdentity.translate(width/2 - targetNode.x * transform.k, height/2 - targetNode.y * transform.k).scale(transform.k)
                );
            }
        });
    });

    panel.classList.add('open');
}

function closeDetailPanel() {
    selectedNode = null;
    document.getElementById('detail-panel').classList.remove('open');
    node.classed('selected', false).classed('dimmed', false).classed('highlight', false);
    link.classed('highlight', false);
    applyFilters();
}

document.getElementById('detail-close').addEventListener('click', (e) => {
    e.stopPropagation();
    closeDetailPanel();
});

// Escape key closes panel
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDetailPanel();
});

// --- Search ---
document.getElementById('search-box').addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    if (!q) {
        node.classed('dimmed', false).classed('highlight', false);
        applyFilters();
        return;
    }
    node.classed('dimmed', d => {
        const label = (d.label || '').toLowerCase();
        const file = (d.source_file || '').toLowerCase();
        const domain = (d.domain || '').toLowerCase();
        const tags = (d.tags || []).join(' ').toLowerCase();
        return !label.includes(q) && !file.includes(q) && !domain.includes(q) && !tags.includes(q);
    });
    node.classed('highlight', d => {
        const label = (d.label || '').toLowerCase();
        return label.includes(q);
    });
});

// --- Tick ---
simulation.on('tick', () => {
    link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
});

// --- Drag ---
function dragStart(event, d) {
    isDragging = false;
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x; d.fy = d.y;
}
function dragging(event, d) {
    isDragging = true;
    d.fx = event.x; d.fy = event.y;
}
function dragEnd(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null; d.fy = null;
    setTimeout(() => { isDragging = false; }, 50);
}

// --- Minimap ---
const minimapCanvas = document.getElementById('minimap-canvas');
const mmCtx = minimapCanvas.getContext('2d');
minimapCanvas.width = 180;
minimapCanvas.height = 120;

function updateMinimap(transform) {
    mmCtx.clearRect(0, 0, 180, 120);

    // Calculate bounds
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    nodes.forEach(n => {
        if (n.x < minX) minX = n.x;
        if (n.x > maxX) maxX = n.x;
        if (n.y < minY) minY = n.y;
        if (n.y > maxY) maxY = n.y;
    });
    const pad = 50;
    minX -= pad; maxX += pad; minY -= pad; maxY += pad;
    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;
    const scaleX = 180 / rangeX;
    const scaleY = 120 / rangeY;
    const mmScale = Math.min(scaleX, scaleY);

    // Draw nodes
    nodes.forEach(n => {
        const x = (n.x - minX) * mmScale;
        const y = (n.y - minY) * mmScale;
        mmCtx.fillStyle = getColor(n.domain);
        mmCtx.globalAlpha = 0.6;
        mmCtx.beginPath();
        mmCtx.arc(x, y, 2, 0, Math.PI * 2);
        mmCtx.fill();
    });

    // Draw viewport rectangle
    if (transform) {
        mmCtx.globalAlpha = 1;
        mmCtx.strokeStyle = 'rgba(79,195,247,0.6)';
        mmCtx.lineWidth = 1;
        const vx = (-transform.x / transform.k - minX) * mmScale;
        const vy = (-transform.y / transform.k - minY) * mmScale;
        const vw = (width / transform.k) * mmScale;
        const vh = (height / transform.k) * mmScale;
        mmCtx.strokeRect(vx, vy, vw, vh);
    }
}

// Initial minimap
simulation.on('end', () => updateMinimap(d3.zoomTransform(svg.node())));

// --- Tab switching ---
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const view = btn.dataset.view;
        if (view === currentView) return;
        currentView = view;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        if (view === 'dashboard') {
            document.getElementById('dashboard').classList.add('active');
            document.getElementById('hud').style.display = 'none';
            document.getElementById('legend').style.display = 'none';
            document.getElementById('minimap').style.display = 'none';
            svg.style('display', 'none');
            closeDetailPanel();
            buildDashboard();
        } else {
            document.getElementById('dashboard').classList.remove('active');
            document.getElementById('hud').style.display = '';
            document.getElementById('legend').style.display = '';
            document.getElementById('minimap').style.display = '';
            svg.style('display', '');
        }
    });
});

// --- Dashboard charts ---
let dashboardBuilt = false;
function buildDashboard() {
    if (dashboardBuilt) return;
    dashboardBuilt = true;

    // Summary cards
    const cardsEl = document.getElementById('dash-cards');
    const cards = [
        { label: 'Total Tokens', value: (STATS.total_tokens || 0).toLocaleString(), sub: 'across all chunks' },
        { label: 'Chunks', value: (STATS.total_chunks || 0).toLocaleString(), sub: `${STATS.file_count || 0} files` },
        { label: 'Avg Tokens/Chunk', value: (STATS.avg_tokens || 0).toLocaleString(), sub: 'information density' },
        { label: 'Domains', value: (STATS.domain_count || 0).toString(), sub: 'expertise areas' },
    ];
    cardsEl.innerHTML = cards.map(c => `
        <div class="dash-card">
            <div class="card-label">${c.label}</div>
            <div class="card-value">${c.value}</div>
            <div class="card-sub">${c.sub}</div>
        </div>
    `).join('');

    // Tokens by domain bar chart
    const domainData = STATS.tokens_by_domain || [];
    if (domainData.length > 0) {
        const chartW = 400, chartH = domainData.length * 36 + 20;
        const margin = { top: 10, right: 60, bottom: 10, left: 140 };
        const innerW = chartW - margin.left - margin.right;
        const innerH = chartH - margin.top - margin.bottom;

        const domainSvg = d3.select('#chart-domain').append('svg')
            .attr('width', chartW).attr('height', chartH);
        const dg = domainSvg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

        const yScale = d3.scaleBand().domain(domainData.map(d => d.domain)).range([0, innerH]).padding(0.3);
        const xScale = d3.scaleLinear().domain([0, d3.max(domainData, d => d.tokens)]).range([0, innerW]);

        dg.selectAll('rect').data(domainData).join('rect')
            .attr('y', d => yScale(d.domain))
            .attr('height', yScale.bandwidth())
            .attr('width', d => xScale(d.tokens))
            .attr('rx', 4)
            .attr('fill', d => getColor(d.domain === 'shared' ? null : d.domain))
            .attr('opacity', 0.8);

        dg.selectAll('.label').data(domainData).join('text')
            .attr('x', -8).attr('y', d => yScale(d.domain) + yScale.bandwidth() / 2)
            .attr('text-anchor', 'end').attr('dominant-baseline', 'middle')
            .attr('fill', '#aaa').attr('font-size', 12)
            .text(d => d.domain);

        dg.selectAll('.value').data(domainData).join('text')
            .attr('x', d => xScale(d.tokens) + 6).attr('y', d => yScale(d.domain) + yScale.bandwidth() / 2)
            .attr('dominant-baseline', 'middle')
            .attr('fill', '#666').attr('font-size', 11)
            .text(d => d.tokens.toLocaleString());
    }

    // Content type donut chart
    const typeData = STATS.content_types || [];
    if (typeData.length > 0) {
        const donutW = 280, donutH = 280;
        const radius = Math.min(donutW, donutH) / 2 - 20;

        const donutSvg = d3.select('#chart-types').append('svg')
            .attr('width', donutW).attr('height', donutH);
        const donutG = donutSvg.append('g').attr('transform', `translate(${donutW/2},${donutH/2})`);

        const pie = d3.pie().value(d => d.tokens).sort(null);
        const arc = d3.arc().innerRadius(radius * 0.55).outerRadius(radius);
        const labelArc = d3.arc().innerRadius(radius * 0.8).outerRadius(radius * 0.8);

        const arcs = donutG.selectAll('.arc').data(pie(typeData)).join('g').attr('class', 'arc');

        arcs.append('path')
            .attr('d', arc)
            .attr('fill', d => TYPE_COLORS[d.data.type] || '#78909c')
            .attr('stroke', '#0a0a0f').attr('stroke-width', 2)
            .attr('opacity', 0.8);

        arcs.append('text')
            .attr('transform', d => `translate(${labelArc.centroid(d)})`)
            .attr('text-anchor', 'middle').attr('fill', '#ddd').attr('font-size', 11)
            .text(d => d.data.type);

        // Center text
        donutG.append('text').attr('text-anchor', 'middle').attr('dy', '-0.3em')
            .attr('fill', '#fff').attr('font-size', 20).attr('font-weight', 600)
            .text(totalTokens.toLocaleString());
        donutG.append('text').attr('text-anchor', 'middle').attr('dy', '1.2em')
            .attr('fill', '#666').attr('font-size', 11)
            .text('total tokens');
    }

    // Tokens by file treemap
    const fileData = STATS.tokens_by_file || [];
    if (fileData.length > 0) {
        const tmW = document.getElementById('chart-files').clientWidth || 800;
        const tmH = Math.max(200, fileData.length * 20);

        const treemapData = {
            name: 'root',
            children: fileData.map(f => ({
                name: f.file.split('/').pop(),
                fullPath: f.file,
                value: f.tokens,
                domain: f.domain,
                chunks: f.chunks,
            }))
        };

        const root = d3.hierarchy(treemapData).sum(d => d.value).sort((a, b) => b.value - a.value);
        d3.treemap().size([tmW, tmH]).padding(3).round(true)(root);

        const tmSvg = d3.select('#chart-files').append('svg')
            .attr('width', tmW).attr('height', tmH);

        const cell = tmSvg.selectAll('g').data(root.leaves()).join('g')
            .attr('transform', d => `translate(${d.x0},${d.y0})`);

        cell.append('rect')
            .attr('width', d => d.x1 - d.x0)
            .attr('height', d => d.y1 - d.y0)
            .attr('rx', 4)
            .attr('fill', d => getColor(d.data.domain === 'shared' ? null : d.data.domain))
            .attr('opacity', 0.6)
            .attr('stroke', '#0a0a0f').attr('stroke-width', 1);

        cell.append('text')
            .attr('x', 6).attr('y', 16)
            .attr('fill', '#fff').attr('font-size', 11).attr('font-weight', 500)
            .text(d => {
                const w = d.x1 - d.x0;
                const name = d.data.name;
                return w > name.length * 7 ? name : name.substring(0, Math.floor(w / 7)) + '..';
            });

        cell.append('text')
            .attr('x', 6).attr('y', 30)
            .attr('fill', '#aaa').attr('font-size', 10)
            .text(d => {
                const w = d.x1 - d.x0;
                return w > 60 ? `${d.data.value.toLocaleString()} tok` : '';
            });

        // Tooltip for treemap cells
        cell.on('mouseover', (event, d) => {
            tooltip.innerHTML = `
                <div class="tt-title">${escapeHtml(d.data.fullPath)}</div>
                <div class="tt-meta">
                    ${d.data.domain} &middot; ${d.data.chunks} chunks &middot; ${d.data.value.toLocaleString()} tokens
                </div>
            `;
            tooltip.style.opacity = 1;
            tooltip.style.left = (event.pageX + 14) + 'px';
            tooltip.style.top = (event.pageY - 10) + 'px';
        })
        .on('mousemove', (event) => {
            tooltip.style.left = (event.pageX + 14) + 'px';
            tooltip.style.top = (event.pageY - 10) + 'px';
        })
        .on('mouseout', () => { tooltip.style.opacity = 0; });
    }
}

// Initial zoom to fit
setTimeout(() => {
    const bounds = g.node().getBBox();
    const dx = bounds.width, dy = bounds.height;
    const x = bounds.x + dx / 2, y = bounds.y + dy / 2;
    const scale = 0.8 / Math.max(dx / width, dy / height);
    const translate = [width / 2 - scale * x, height / 2 - scale * y];
    svg.transition().duration(750)
        .call(zoom.transform, d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale));
}, 1500);
</script>
</body>
</html>"""


def generate_visualization(
    config: RetrievalConfig,
    output_path: Optional[Path] = None,
    open_browser: bool = False,
) -> Path:
    """
    Generate an interactive knowledge graph HTML file.

    Reads graph data from the store and embeds it into a
    self-contained HTML file with D3.js visualization.
    """
    store = Store(config.db_path, config.store_dir)
    graph_data = store.get_chunk_relationships()

    # Add text previews for tooltips and full text for detail panel
    chunks = store.get_all_chunks()
    previews = {}
    full_texts = {}
    for c in chunks:
        previews[c["id"]] = c["text"][:300]
        full_texts[c["id"]] = c["text"]

    graph_data["previews"] = previews
    graph_data["full_texts"] = full_texts

    # Add aggregate stats for dashboard
    graph_data["stats"] = store.get_aggregate_stats()

    store.close()

    # Embed data into HTML
    graph_json = json.dumps(graph_data, indent=None)
    html = HTML_TEMPLATE.replace("%%GRAPH_JSON%%", graph_json)

    if output_path is None:
        output_path = config.knowledge_root / "retrieval" / "knowledge-graph.html"

    output_path = Path(output_path)
    output_path.write_text(html, encoding="utf-8")

    if open_browser:
        webbrowser.open(str(output_path.resolve()))

    return output_path


if __name__ == "__main__":
    import sys

    config = RetrievalConfig()
    root = Path.cwd()
    config.knowledge_root = root
    config.store_dir = root / "retrieval" / "store"
    config.db_path = config.store_dir / "metadata.db"

    open_flag = "--open" in sys.argv
    path = generate_visualization(config, open_browser=open_flag)
    print(f"Knowledge graph generated: {path}")
