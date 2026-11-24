"""Independent blind manual annotation workflow for AIDA 2154 supplementary check.

Responds to Formative Feedback 1 (2026-11-23):
- Selects 9 held-out test samples (1 per site) via a predeclared deterministic rule
  independent of model performance, predictions, or automatic mask scores:
  the chronological median held-out test sample per site (disjoint from the first
  test sample shown in test_examples.png and the first/last shown in selection_review.png).
- Generates a self-contained, offline, strictly BLIND HTML/Canvas annotation tool
  (contains NO CNN predictions and NO automatic masks) with 3 explicit classes:
    0 = Clear Non-Water / Land (default background)
    1 = Clear Water
    2 = Uncertain / Mixed Bank / Occluded (explicit annotation uncertainty)
- Scores the student's exported manual annotation JSON SEPARATELY from the original
  132-image weak-label evaluation, leaving all original model files and metrics untouched.

Usage (from repository root):
  python -B run.py -m cv_tools.independent_manual_eval --prepare
  python -B run.py -m cv_tools.independent_manual_eval --score <path-to-exported-json>
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw

WORKSPACE = Path(__file__).resolve().parents[4]
COURSE_DIR = WORKSPACE / "courses" / "AIDA-2154"
CNN_DIR = COURSE_DIR / "data" / "processed" / "point_cnn_20261113"
OUT_DIR = COURSE_DIR / "data" / "processed" / "manual_independent_eval_20261123"
TOOL_HTML = OUT_DIR / "manual_blind_annotation_tool.html"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stretch_rgb(arr_chw: np.ndarray, mode: str = "rgb") -> Image.Image:
    """Convert (4, 61, 61) reflectance [R, G, B, NIR] in [0, 1] to stretched RGB PIL image."""
    if mode == "rgb":
        rgb = np.stack([arr_chw[0], arr_chw[1], arr_chw[2]], axis=-1)
    elif mode == "nir_false":
        # False color: NIR -> R, Green -> G, Red -> B (water shows very dark/navy; vegetation bright red)
        rgb = np.stack([arr_chw[3], arr_chw[1], arr_chw[0]], axis=-1)
    else:
        raise ValueError(mode)
    out = np.zeros_like(rgb)
    for c in range(3):
        ch = rgb[..., c]
        lo, hi = np.percentile(ch, [2, 98])
        if hi <= lo + 1e-6:
            lo, hi = float(ch.min()), float(ch.max()) + 1e-6
        out[..., c] = np.clip((ch - lo) / (hi - lo), 0.0, 1.0)
    return Image.fromarray((out * 255).astype(np.uint8), mode="RGB")


def pil_to_data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def select_blind_nine() -> tuple[list[dict], np.ndarray, np.ndarray, np.ndarray, dict]:
    """Deterministic predeclared selection: chronological median held-out test sample per site."""
    mf = json.loads((CNN_DIR / "dataset_manifest.json").read_text(encoding="utf-8"))
    records = mf["records"]
    ds = np.load(CNN_DIR / "dataset.npz")
    x_all = ds["x"]
    y_all = ds["y"]
    pred_npz = np.load(CNN_DIR / "test_predictions.npz")
    test_indices = [int(i) for i in pred_npz["indices"]]
    test_probs = pred_npz["probabilities"]

    by_point: dict[str, list[tuple[int, int, dict]]] = {}
    for test_pos, global_idx in enumerate(test_indices):
        rec = records[global_idx]
        by_point.setdefault(rec["point_id"], []).append((test_pos, global_idx, rec))

    selected = []
    for pt in sorted(by_point):
        items = sorted(by_point[pt], key=lambda t: (t[2]["date"], t[1]))
        mid_i = len(items) // 2
        test_pos, global_idx, rec = items[mid_i]
        selected.append(
            {
                "point_id": pt,
                "record_id": rec["id"],
                "date_utc": rec["date"],
                "global_index": global_idx,
                "test_position": test_pos,
                "test_rank_within_site": f"{mid_i + 1} of {len(items)}",
                "crop_sha256": rec["crop_sha256"],
                "mask_sha256": rec["mask_sha256"],
            }
        )
    return selected, x_all, y_all, test_probs, mf


def build_html_tool(selected: list[dict], x_all: np.ndarray) -> str:
    """Create a 100% blind, self-contained HTML annotation app (ZERO model/mask leakage)."""
    payload = []
    for item in selected:
        crop = x_all[item["global_index"]]  # (4, 61, 61)
        payload.append(
            {
                "point_id": item["point_id"],
                "record_id": item["record_id"],
                "date_utc": item["date_utc"],
                "global_index": item["global_index"],
                "crop_sha256": item["crop_sha256"],
                "rgb_url": pil_to_data_url(stretch_rgb(crop, "rgb")),
                "nir_url": pil_to_data_url(stretch_rgb(crop, "nir_false")),
            }
        )
    data_json = json.dumps(payload)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>AIDA 2154 — Blind Manual Water Annotation (9 Independent Test Crops)</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #F1F7F7; color: #142F39; margin: 0; padding: 18px; }}
  .wrap {{ max-width: 1180px; margin: 0 auto; }}
  h1 {{ margin: 0 0 6px; font-size: 22px; color: #142F39; }}
  .sub {{ margin: 0 0 14px; font-size: 13px; color: #435D66; }}
  .bar {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; background: #FFF; border: 1px solid #CCDDDC; border-radius: 8px; padding: 10px 14px; margin-bottom: 14px; }}
  .btn {{ border: 1px solid #CBD5E1; background: #FFF; color: #142F39; padding: 7px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; }}
  .btn:hover {{ background: #F8FAFC; }}
  .btn.active-water {{ background: #0072B2; color: #FFF; border-color: #0072B2; }}
  .btn.active-unc {{ background: #D97706; color: #FFF; border-color: #D97706; }}
  .btn.active-land {{ background: #334155; color: #FFF; border-color: #334155; }}
  .btn.primary {{ background: #006F69; color: #FFF; border-color: #006F69; }}
  .btn.primary:hover {{ background: #005A55; }}
  .grid {{ display: grid; grid-template-columns: 500px 1fr; gap: 18px; align-items: start; }}
  .card {{ background: #FFF; border: 1px solid #CCDDDC; border-radius: 8px; padding: 14px; }}
  .canvas-wrap {{ position: relative; width: 488px; height: 488px; border: 2px solid #142F39; cursor: crosshair; user-select: none; background: #000; }}
  canvas {{ position: absolute; left: 0; top: 0; image-rendering: pixelated; }}
  .ref-box {{ display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }}
  .ref-img {{ width: 183px; height: 183px; image-rendering: pixelated; border: 1px solid #94A3B8; }}
  .pill {{ display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; margin-right: 6px; }}
  .pill-done {{ background: #DCFCE7; color: #166534; }}
  .pill-todo {{ background: #FEF3C7; color: #92400E; }}
  .site-tabs {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }}
  .tab {{ padding: 6px 10px; border-radius: 6px; border: 1px solid #CBD5E1; background: #FFF; cursor: pointer; font-size: 12px; font-weight: 600; }}
  .tab.current {{ border-color: #006F69; background: #E6F4F3; color: #006F69; }}
  .tab.marked {{ border-left: 4px solid #16A34A; }}
  textarea, select, input[type=text] {{ width: 100%; border: 1px solid #CBD5E1; border-radius: 6px; padding: 7px; font-family: inherit; font-size: 13px; }}
  .stats {{ font-size: 13px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 8px 10px; margin: 10px 0; }}
  .note {{ font-size: 12px; color: #475569; line-height: 1.5; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>AIDA 2154 — Independent Blind Manual Annotation (9 Held-Out Crops, 61 × 61 at 10 m)</h1>
  <p class="sub">
    <strong>Strictly Blind:</strong> No CNN predictions or automatic masks are loaded or shown.
    Default background = <strong>Clear Land (0)</strong>. Paint only <strong>Clear Water (1, blue)</strong> and <strong>Uncertain / Mixed Bank / Shadow (2, orange)</strong>.
    Progress auto-saves in your browser.
  </p>

  <div class="site-tabs" id="siteTabs"></div>

  <div class="bar">
    <button class="btn active-water" id="tool1" onclick="setTool(1)">[1] Clear Water (Blue)</button>
    <button class="btn" id="tool2" onclick="setTool(2)">[2] Uncertain / Mixed Bank (Orange)</button>
    <button class="btn" id="tool0" onclick="setTool(0)">[0] Eraser / Clear Land</button>
    <button class="btn" id="toolErase1" onclick="setSingleErase()" title="Switch to 1px single-pixel eraser (shortcut E; or Right-Click any pixel)">[E] Single-Pixel Erase (1px)</button>
    <button class="btn" style="background:#FFFBEB;border-color:#F59E0B;color:#92400E;" onclick="ringUncertain()" title="Fill 1-pixel orange ring around all blue water pixels (shortcut R, undoable with Ctrl+Z)">[R] Auto-Ring Orange Around Blue</button>
    <span style="margin-left:8px;font-size:13px;">Brush:
      <select id="brushSize" style="width:auto;display:inline-block;padding:4px 6px;">
        <option value="1" selected>1 px (10 m)</option>
        <option value="2">2 px (20 m)</option>
        <option value="3">3 px (30 m)</option>
      </select>
    </span>
    <span style="margin-left:8px;font-size:13px;">Overlay:
      <input type="range" id="opacity" min="0" max="100" value="65" oninput="renderOverlay()" style="vertical-align:middle;width:85px;" />
    </span>
    <label style="font-size:13px;margin-left:6px;"><input type="checkbox" id="showNir" onchange="renderBase()" /> View NIR False-Color on Canvas</label>
    <button class="btn" onclick="undo()" style="margin-left:auto;">Undo (Ctrl+Z)</button>
    <button class="btn" onclick="clearCurrent()">Clear Image</button>
    <button class="btn" onclick="document.getElementById('importFile').click()">Import JSON</button>
    <input type="file" id="importFile" accept=".json" style="display:none;" onchange="importJson(event)" />
    <button class="btn primary" onclick="exportJson()">Export Blind Annotation JSON</button>
  </div>

  <div class="grid">
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <strong id="imgHeader"></strong>
        <span id="imgStatus" class="pill pill-todo">Not marked yet</span>
      </div>
      <div class="canvas-wrap" id="canvasWrap">
        <canvas id="baseCanvas" width="488" height="488"></canvas>
        <canvas id="maskCanvas" width="488" height="488"></canvas>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:10px;">
        <button class="btn" onclick="go(-1)">← Previous Site</button>
        <button class="btn" onclick="markReviewed()">Mark Site Complete ✓</button>
        <button class="btn" onclick="go(1)">Next Site →</button>
      </div>
    </div>

    <div class="card">
      <h3 style="margin:0 0 8px;font-size:15px;">Reference Views (True-Color RGB &amp; NIR False-Color)</h3>
      <div class="ref-box">
        <div>
          <img id="refRgb" class="ref-img" alt="RGB reference" />
          <div class="note" style="text-align:center;">True-Color RGB</div>
        </div>
        <div>
          <img id="refNir" class="ref-img" alt="NIR false color reference" />
          <div class="note" style="text-align:center;">NIR–Green–Red (water = dark)</div>
        </div>
      </div>

      <div class="stats" id="pixelStats"></div>

      <label style="display:block;font-size:13px;font-weight:600;margin-bottom:4px;">Annotator Confidence (this 10 m crop):</label>
      <select id="confSelect" onchange="saveMeta()" style="margin-bottom:10px;">
        <option value="low">Low — narrow/blurry channel; bank boundary uncertain</option>
        <option value="medium" selected>Medium — main channel visible, bank pixels mixed</option>
        <option value="high">High — wide clear channel with crisp banks</option>
      </select>

      <label style="display:block;font-size:13px;font-weight:600;margin-bottom:4px;">Visual Observation / Uncertainty Note (English or Chinese):</label>
      <textarea id="noteBox" rows="3" placeholder="e.g., Narrow stream blurred at 10 m; bridge shadow crosses centre..." oninput="saveMeta()"></textarea>

      <div class="note" style="margin-top:12px;background:#FFF4E6;border:1px solid #F59E0B;border-radius:6px;padding:10px;">
        <strong>Protocol Reminder (for AIDA 2154):</strong><br/>
        • <strong>Blue (1)</strong> = pixels you are confident are water.<br/>
        • <strong>Orange (2)</strong> = mixed bank/water, bridge, shadow, or blurry pixels where 10 m resolution prevents confident labeling.<br/>
        • Leaving unsure bank pixels <strong>Orange (2)</strong> instead of guessing strengthens your uncertainty audit!<br/>
        • Click <strong>Export Blind Annotation JSON</strong> when all 9 sites are done, and save it to:<br/>
        <code>courses/AIDA-2154/data/processed/manual_independent_eval_20261123/manual_blind_annotations_9sites.json</code>
      </div>
    </div>
  </div>
</div>

<script>
const ITEMS = {data_json};
const N = 61, SCALE = 8, STORE_KEY = "aida2154_blind_manual_v1";
let cur = 0, tool = 1, drawing = false;
let state = loadState();
let undoStack = [];

function loadState() {{
  try {{
    const raw = localStorage.getItem(STORE_KEY);
    if (raw) {{
      const parsed = JSON.parse(raw);
      if (parsed && parsed.masks && parsed.masks.length === ITEMS.length) return parsed;
    }}
  }} catch (e) {{}}
  return {{
    annotator: "Miles (Renjun) Zhang",
    masks: ITEMS.map(() => new Array(N * N).fill(0)),
    confidence: ITEMS.map(() => "medium"),
    notes: ITEMS.map(() => ""),
    completed: ITEMS.map(() => false)
  }};
}}

function persist() {{
  try {{ localStorage.setItem(STORE_KEY, JSON.stringify(state)); }} catch (e) {{}}
}}

function setTool(t) {{
  tool = t;
  document.getElementById("tool1").className = "btn" + (t === 1 ? " active-water" : "");
  document.getElementById("tool2").className = "btn" + (t === 2 ? " active-unc" : "");
  document.getElementById("tool0").className = "btn" + (t === 0 ? " active-land" : "");
  const e1 = document.getElementById("toolErase1");
  if (e1) e1.className = "btn" + (t === 0 && document.getElementById("brushSize").value === "1" ? " active-land" : "");
}}

function setSingleErase() {{
  document.getElementById("brushSize").value = "1";
  setTool(0);
}}

function ringUncertain() {{
  const mask = state.masks[cur];
  if (!mask.some(v => v === 1)) {{
    alert("Paint some Clear Water (Blue) pixels first, then click Auto-Ring.");
    return;
  }}
  undoStack.push(mask.slice());
  if (undoStack.length > 40) undoStack.shift();
  const next = mask.slice();
  for (let y = 0; y < N; y++) {{
    for (let x = 0; x < N; x++) {{
      if (mask[y * N + x] !== 0) continue;
      let touchesBlue = false;
      for (let dy = -1; dy <= 1 && !touchesBlue; dy++) {{
        for (let dx = -1; dx <= 1; dx++) {{
          if (dx === 0 && dy === 0) continue;
          const nx = x + dx, ny = y + dy;
          if (nx >= 0 && nx < N && ny >= 0 && ny < N && mask[ny * N + nx] === 1) {{
            touchesBlue = true;
            break;
          }}
        }}
      }}
      if (touchesBlue) next[y * N + x] = 2;
    }}
  }}
  state.masks[cur] = next;
  persist();
  renderTabs();
  renderOverlay();
}}

function renderTabs() {{
  const el = document.getElementById("siteTabs");
  el.innerHTML = "";
  ITEMS.forEach((it, idx) => {{
    const b = document.createElement("button");
    const hasPaint = state.masks[idx].some(v => v !== 0) || state.completed[idx];
    b.className = "tab" + (idx === cur ? " current" : "") + (state.completed[idx] ? " marked" : "");
    b.textContent = `${{idx + 1}}. ${{it.point_id}} (${{it.date_utc.slice(0, 10)}})${{state.completed[idx] ? " ✓" : (hasPaint ? " •" : "")}}`;
    b.onclick = () => {{ cur = idx; undoStack = []; loadCurrent(); }};
    el.appendChild(b);
  }});
}}

function renderBase() {{
  const ctx = document.getElementById("baseCanvas").getContext("2d");
  ctx.imageSmoothingEnabled = false;
  const img = new Image();
  img.onload = () => {{
    ctx.clearRect(0, 0, N * SCALE, N * SCALE);
    ctx.drawImage(img, 0, 0, N * SCALE, N * SCALE);
    // Faint centre crosshair (exact GIS target pixel 30,30)
    ctx.strokeStyle = "rgba(255,255,255,0.45)";
    ctx.lineWidth = 1;
    const c = 30.5 * SCALE;
    ctx.beginPath(); ctx.moveTo(c - 12, c); ctx.lineTo(c + 12, c); ctx.moveTo(c, c - 12); ctx.lineTo(c, c + 12); ctx.stroke();
  }};
  img.src = document.getElementById("showNir").checked ? ITEMS[cur].nir_url : ITEMS[cur].rgb_url;
}}

function renderOverlay() {{
  const ctx = document.getElementById("maskCanvas").getContext("2d");
  ctx.clearRect(0, 0, N * SCALE, N * SCALE);
  const alpha = parseInt(document.getElementById("opacity").value, 10) / 100.0;
  const mask = state.masks[cur];
  let c0 = 0, c1 = 0, c2 = 0;
  for (let y = 0; y < N; y++) {{
    for (let x = 0; x < N; x++) {{
      const v = mask[y * N + x];
      if (v === 0) {{ c0++; continue; }}
      if (v === 1) {{
        c1++;
        ctx.fillStyle = `rgba(0, 114, 178, ${{alpha}})`;
      }} else {{
        c2++;
        ctx.fillStyle = `rgba(245, 158, 11, ${{alpha}})`;
      }}
      ctx.fillRect(x * SCALE, y * SCALE, SCALE, SCALE);
    }}
  }}
  const pct1 = (c1 / (N * N) * 100).toFixed(1);
  const pct2 = (c2 / (N * N) * 100).toFixed(1);
  document.getElementById("pixelStats").innerHTML =
    `<strong>Current Crop Pixel Counts (61×61 = 3,721):</strong><br/>` +
    `Clear Water (1): <strong>${{c1}}</strong> (${{pct1}}%) &nbsp;|&nbsp; ` +
    `Uncertain/Mixed (2): <strong>${{c2}}</strong> (${{pct2}}%) &nbsp;|&nbsp; ` +
    `Clear Land (0): <strong>${{c0}}</strong>`;
  const doneCount = state.completed.filter(Boolean).length;
  const st = document.getElementById("imgStatus");
  st.className = "pill " + (state.completed[cur] ? "pill-done" : "pill-todo");
  st.textContent = state.completed[cur] ? `Completed (${{doneCount}}/9 sites done)` : `In progress (${{doneCount}}/9 sites done)`;
}}

function loadCurrent() {{
  const it = ITEMS[cur];
  document.getElementById("imgHeader").textContent = `Site ${{cur + 1}}/9: ${{it.point_id}} — ${{it.date_utc.slice(0, 10)}} (Blind Crop)`;
  document.getElementById("refRgb").src = it.rgb_url;
  document.getElementById("refNir").src = it.nir_url;
  document.getElementById("confSelect").value = state.confidence[cur];
  document.getElementById("noteBox").value = state.notes[cur];
  renderTabs();
  renderBase();
  renderOverlay();
}}

function saveMeta() {{
  state.confidence[cur] = document.getElementById("confSelect").value;
  state.notes[cur] = document.getElementById("noteBox").value;
  persist();
}}

function markReviewed() {{
  state.completed[cur] = true;
  persist();
  renderTabs();
  renderOverlay();
  if (cur < ITEMS.length - 1) {{ cur++; undoStack = []; loadCurrent(); }}
}}

function go(delta) {{
  cur = (cur + delta + ITEMS.length) % ITEMS.length;
  undoStack = [];
  loadCurrent();
}}

function clearCurrent() {{
  undoStack.push(state.masks[cur].slice());
  state.masks[cur] = new Array(N * N).fill(0);
  state.completed[cur] = false;
  persist();
  renderTabs();
  renderOverlay();
}}

function undo() {{
  if (!undoStack.length) return;
  state.masks[cur] = undoStack.pop();
  persist();
  renderOverlay();
}}

function paintAt(ev, overrideTool = null, overrideBrush = null) {{
  const rect = document.getElementById("maskCanvas").getBoundingClientRect();
  const gx = Math.floor((ev.clientX - rect.left) / SCALE);
  const gy = Math.floor((ev.clientY - rect.top) / SCALE);
  const b = overrideBrush !== null ? overrideBrush : parseInt(document.getElementById("brushSize").value, 10);
  const val = overrideTool !== null ? overrideTool : tool;
  const half = Math.floor(b / 2);
  const mask = state.masks[cur];
  for (let dy = -half; dy < b - half; dy++) {{
    for (let dx = -half; dx < b - half; dx++) {{
      const x = gx + dx, y = gy + dy;
      if (x >= 0 && x < N && y >= 0 && y < N) mask[y * N + x] = val;
    }}
  }}
  renderOverlay();
}}

const mc = document.getElementById("maskCanvas");
let rightErasing = false;
mc.addEventListener("contextmenu", ev => ev.preventDefault());
mc.addEventListener("mousedown", ev => {{
  undoStack.push(state.masks[cur].slice());
  if (undoStack.length > 40) undoStack.shift();
  if (ev.button === 2) {{
    rightErasing = true;
    paintAt(ev, 0, 1);
  }} else {{
    drawing = true;
    paintAt(ev);
  }}
}});
window.addEventListener("mouseup", () => {{
  if (drawing || rightErasing) {{
    drawing = false;
    rightErasing = false;
    persist();
    renderTabs();
  }}
}});
mc.addEventListener("mousemove", ev => {{
  if (rightErasing) paintAt(ev, 0, 1);
  else if (drawing) paintAt(ev);
}});
window.addEventListener("keydown", ev => {{
  if (document.activeElement.tagName === "TEXTAREA") return;
  const k = ev.key.toLowerCase();
  if (k === "1") setTool(1);
  else if (k === "2") setTool(2);
  else if (k === "0") setTool(0);
  else if (k === "e") setSingleErase();
  else if (k === "r") ringUncertain();
  else if ((ev.ctrlKey || ev.metaKey) && k === "z") {{ ev.preventDefault(); undo(); }}
}});

function exportJson() {{
  const doneCount = state.completed.filter(Boolean).length;
  if (doneCount < ITEMS.length) {{
    if (!confirm(`You have marked ${{doneCount}}/9 sites complete. Export anyway?`)) return;
  }}
  const out = {{
    protocol: "AIDA2154_independent_blind_manual_check_v1",
    annotator: state.annotator,
    exported_utc: new Date().toISOString(),
    selection_rule: "chronological_median_held_out_test_sample_per_site",
    class_legend: {{ "0": "clear_non_water_land", "1": "clear_water", "2": "uncertain_mixed_bank_or_occluded" }},
    records: ITEMS.map((it, i) => ({{
      point_id: it.point_id,
      record_id: it.record_id,
      date_utc: it.date_utc,
      global_index: it.global_index,
      crop_sha256: it.crop_sha256,
      confidence: state.confidence[i],
      note: state.notes[i],
      completed: state.completed[i],
      mask_61x61: state.masks[i]
    }}))
  }};
  const blob = new Blob([JSON.stringify(out, null, 2)], {{ type: "application/json" }});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "manual_blind_annotations_9sites.json";
  a.click();
}}

function importJson(ev) {{
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {{
    try {{
      const parsed = JSON.parse(reader.result);
      if (!parsed.records || parsed.records.length !== ITEMS.length) {{
        alert("Invalid annotation JSON (expected 9 records).");
        return;
      }}
      parsed.records.forEach((r, i) => {{
        if (r.mask_61x61 && r.mask_61x61.length === N * N) state.masks[i] = r.mask_61x61.slice();
        if (r.confidence) state.confidence[i] = r.confidence;
        if (typeof r.note === "string") state.notes[i] = r.note;
        state.completed[i] = Boolean(r.completed);
      }});
      persist();
      undoStack = [];
      loadCurrent();
      alert("Imported saved progress successfully!");
    }} catch (e) {{
      alert("Failed to read JSON: " + e.message);
    }}
  }};
  reader.readAsText(file);
  ev.target.value = "";
}}

loadCurrent();
</script>
</body>
</html>
"""


def calc_metrics(truth_bool: np.ndarray, pred_bool: np.ndarray, valid_mask: np.ndarray) -> dict:
    tp = int(((truth_bool) & (pred_bool) & valid_mask).sum())
    fp = int(((~truth_bool) & (pred_bool) & valid_mask).sum())
    fn = int(((truth_bool) & (~pred_bool) & valid_mask).sum())
    tn = int(((~truth_bool) & (~pred_bool) & valid_mask).sum())
    return {
        "valid_pixels": tp + fp + fn + tn,
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "IoU": round(tp / max(tp + fp + fn, 1), 6),
        "precision": round(tp / max(tp + fp, 1), 6),
        "recall": round(tp / max(tp + fn, 1), 6),
    }


def compute_static_baseline_masks(records: list[dict], y_all: np.ndarray) -> dict[str, np.ndarray]:
    """Reproduce exact train-only per-point static majority mask (same rule as train_point_cnn.py)."""
    by_pt: dict[str, list[np.ndarray]] = {}
    for i, r in enumerate(records):
        if r["split"] == "train":
            by_pt.setdefault(r["point_id"], []).append(y_all[i])
    static = {}
    for pt, arrs in by_pt.items():
        stack = np.stack(arrs, axis=0)
        valid = stack != 255
        w_cnt = ((stack == 1) & valid).sum(axis=0)
        v_cnt = valid.sum(axis=0)
        static[pt] = (w_cnt * 2 >= np.maximum(v_cnt, 1)) & (v_cnt > 0)
    return static


def prepare() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    selected, x_all, _, _, _ = select_blind_nine()
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Independent blind manual check responding to Formative Feedback 1 (2026-11-23)",
        "selection_rule": (
            "Chronological median held-out test sample per site (items[len//2]), "
            "selected deterministically without viewing CNN predictions, errors, or automatic masks. "
            "Disjoint from first test sample shown in test_examples.png and first/last in selection_review.png."
        ),
        "blindness_guarantee": "HTML annotation tool embeds stretched RGB and NIR-Green-Red crops only; zero model predictions or automatic masks are included.",
        "selected_samples": selected,
    }
    (OUT_DIR / "blind_selection_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    TOOL_HTML.write_text(build_html_tool(selected, x_all), encoding="utf-8")
    print(f"Prepared 9 blind samples manifest: {OUT_DIR / 'blind_selection_manifest.json'}")
    print(f"Prepared offline blind HTML tool:  {TOOL_HTML}")


def score(annotation_path: Path) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ann = json.loads(annotation_path.read_text(encoding="utf-8"))
    selected, x_all, y_all, test_probs, mf = select_blind_nine()
    records = mf["records"]
    static_masks = compute_static_baseline_masks(records, y_all)

    sel_by_pt = {s["point_id"]: s for s in selected}
    per_site = []

    all_m_clear_t, all_cnn, all_auto, all_base, all_valid = [], [], [], [], []
    all_opt_t, all_pes_t, all_any_valid = [], [], []

    # Visual comparison sheet: 9 rows x 5 columns (RGB, Manual, Auto Mask, CNN Pred, Static Base)
    tile = 183  # 61 * 3
    pad, hdr = 12, 28
    sheet_w = pad * 6 + tile * 5
    sheet_h = 40 + 9 * (tile + hdr + pad) + pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    col_titles = ["RGB Crop (10 m)", "Manual Blind (Blue=Water, Org=Unc)", "Automatic Weak Mask", "Frozen CNN (>=0.5)", "Static Train Baseline"]
    for ci, ct in enumerate(col_titles):
        draw.text((pad + ci * (tile + pad), 12), ct, fill=(20, 47, 57))

    for row_i, rec_ann in enumerate(ann["records"]):
        pt = rec_ann["point_id"]
        sel = sel_by_pt[pt]
        assert rec_ann["crop_sha256"] == sel["crop_sha256"], f"Crop hash mismatch at {pt}"
        gidx = sel["global_index"]
        tpos = sel["test_position"]

        m_arr = np.array(rec_ann["mask_61x61"], dtype=np.int32).reshape(61, 61)
        auto_y = y_all[gidx]
        cnn_p = test_probs[tpos] >= 0.5
        base_p = static_masks[pt]

        # Valid masks: exclude provider unknown (255) AND manual uncertain (2) for clear-pixel scoring
        auto_known = auto_y != 255
        clear_valid = auto_known & (m_arr != 2)
        m_water = m_arr == 1

        cnn_clear = calc_metrics(m_water, cnn_p, clear_valid)
        base_clear = calc_metrics(m_water, base_p, clear_valid)
        auto_clear = calc_metrics(m_water, auto_y == 1, clear_valid)

        # Uncertainty sensitivity bounds on auto_known pixels:
        # optimistic = uncertain pixels agree with CNN; pessimistic = uncertain pixels disagree with CNN
        unc_mask = (m_arr == 2) & auto_known
        opt_truth = np.where(unc_mask, cnn_p, m_water)
        pes_truth = np.where(unc_mask, ~cnn_p, m_water)
        cnn_opt = calc_metrics(opt_truth, cnn_p, auto_known)
        cnn_pes = calc_metrics(pes_truth, cnn_p, auto_known)

        all_m_clear_t.append(m_water)
        all_cnn.append(cnn_p)
        all_auto.append(auto_y == 1)
        all_base.append(base_p)
        all_valid.append(clear_valid)
        all_opt_t.append(opt_truth)
        all_pes_t.append(pes_truth)
        all_any_valid.append(auto_known)

        per_site.append(
            {
                "point_id": pt,
                "date_utc": sel["date_utc"],
                "confidence": rec_ann.get("confidence", ""),
                "note": rec_ann.get("note", ""),
                "manual_water_pixels": int((m_arr == 1).sum()),
                "manual_uncertain_pixels": int((m_arr == 2).sum()),
                "manual_uncertain_pct_of_crop": round(float((m_arr == 2).mean() * 100), 2),
                "manual_uncertain_pct_of_channel_zone": round(
                    float((m_arr == 2).sum() / max(int(((m_arr == 1) | (m_arr == 2)).sum()), 1) * 100), 2
                ),
                "cnn_vs_manual_clear": cnn_clear,
                "baseline_vs_manual_clear": base_clear,
                "auto_mask_vs_manual_clear": auto_clear,
                "cnn_iou_uncertainty_bounds": [cnn_pes["IoU"], cnn_opt["IoU"]],
            }
        )

        # Render comparison row
        ry = 40 + row_i * (tile + hdr + pad)
        draw.text(
            (pad, ry),
            f"{pt} | {sel['date_utc'][:10]} | conf={rec_ann.get('confidence','')} | "
            f"CNN IoU={cnn_clear['IoU']*100:.1f}% (bounds {cnn_pes['IoU']*100:.1f}% to {cnn_opt['IoU']*100:.1f}%) | "
            f"Base={base_clear['IoU']*100:.1f}% | Auto={auto_clear['IoU']*100:.1f}% | Unc={int((m_arr==2).sum())} px",
            fill=(20, 47, 57),
        )
        iy = ry + 18

        def to_rgb_mask(bool_arr: np.ndarray, unk_arr: np.ndarray | None = None) -> Image.Image:
            im = np.zeros((61, 61, 3), dtype=np.uint8)
            im[bool_arr] = (0, 114, 178)
            if unk_arr is not None:
                im[unk_arr] = (245, 158, 11)
            return Image.fromarray(im, mode="RGB").resize((tile, tile), Image.NEAREST)

        rgb_img = stretch_rgb(x_all[gidx], "rgb").resize((tile, tile), Image.NEAREST)
        man_img = to_rgb_mask(m_arr == 1, m_arr == 2)
        auto_img = to_rgb_mask(auto_y == 1, auto_y == 255)
        cnn_img = to_rgb_mask(cnn_p)
        base_img = to_rgb_mask(base_p)
        for ci, im_t in enumerate([rgb_img, man_img, auto_img, cnn_img, base_img]):
            sheet.paste(im_t, (pad + ci * (tile + pad), iy))

    sheet.save(OUT_DIR / "independent_manual_comparison.png")

    # Pooled clear-pixel & uncertainty-bound metrics across all 9 sites
    m_t = np.stack(all_m_clear_t)
    c_p = np.stack(all_cnn)
    a_p = np.stack(all_auto)
    b_p = np.stack(all_base)
    v_m = np.stack(all_valid)
    av_m = np.stack(all_any_valid)

    pooled = {
        "cnn_vs_manual_clear": calc_metrics(m_t, c_p, v_m),
        "baseline_vs_manual_clear": calc_metrics(m_t, b_p, v_m),
        "auto_mask_vs_manual_clear": calc_metrics(m_t, a_p, v_m),
        "cnn_vs_manual_pessimistic_uncertain": calc_metrics(np.stack(all_pes_t), c_p, av_m),
        "cnn_vs_manual_optimistic_uncertain": calc_metrics(np.stack(all_opt_t), c_p, av_m),
        "total_manual_water_pixels": sum(r["manual_water_pixels"] for r in per_site),
        "total_manual_uncertain_pixels": sum(r["manual_uncertain_pixels"] for r in per_site),
    }

    try:
        rel_ann = annotation_path.resolve().relative_to(WORKSPACE).as_posix()
    except ValueError:
        rel_ann = annotation_path.name
    report = {
        "scored_utc": datetime.now(timezone.utc).isoformat(),
        "annotation_file": rel_ann,
        "annotation_file_sha256": sha256_bytes(annotation_path.read_bytes()),
        "annotator": ann.get("annotator", "Miles (Renjun) Zhang"),
        "note": (
            "Strictly separate supplementary evaluation on 9 blind median held-out crops. "
            "Does not alter or replace the original 132-image frozen evaluation (IoU 85.21% vs 84.41% baseline) "
            "or change the WITHHOLD disposition."
        ),
        "pooled": pooled,
        "per_site": per_site,
    }
    (OUT_DIR / "manual_eval_summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    with (OUT_DIR / "manual_eval_per_site.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([
            "point_id", "date_utc", "confidence", "manual_water_px", "manual_uncertain_px",
            "uncertain_pct_of_channel_zone", "cnn_iou_clear", "cnn_iou_pessimistic", "cnn_iou_optimistic",
            "baseline_iou_clear", "auto_mask_iou_clear", "note",
        ])
        for r in per_site:
            w.writerow([
                r["point_id"], r["date_utc"][:10], r["confidence"], r["manual_water_pixels"],
                r["manual_uncertain_pixels"], r["manual_uncertain_pct_of_channel_zone"],
                r["cnn_vs_manual_clear"]["IoU"], r["cnn_iou_uncertainty_bounds"][0],
                r["cnn_iou_uncertainty_bounds"][1], r["baseline_vs_manual_clear"]["IoU"],
                r["auto_mask_vs_manual_clear"]["IoU"], r["note"],
            ])

    print(json.dumps(pooled, indent=2))
    print(f"Saved summary, CSV, and comparison sheet under {OUT_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Blind manual annotation tool and independent evaluator for AIDA 2154.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true", help="Select 9 blind median test samples and build offline HTML tool.")
    group.add_argument("--score", type=Path, help="Score an exported manual_blind_annotations_9sites.json file.")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    else:
        score(args.score.resolve())


if __name__ == "__main__":
    main()
