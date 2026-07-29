/* ─────────────────────────────────────────────
   SOLAR SENTINEL — Dashboard Logic
   ───────────────────────────────────────────── */

// ─── CONFIG ───────────────────────────────────────────
// Change this to your deployed Render backend URL after deployment.
// During local development, set to "http://localhost:8000"
const API_BASE = window.location.hostname === "localhost"
  ? "http://localhost:8000"
  : "https://solar-flare-api.onrender.com"; // ← Update with your Render URL

const REFRESH_INTERVAL_MS = 60000; // 60 seconds

// ─── STATE ────────────────────────────────────────────
let flareChartInstance = null;
let kpChartInstance = null;
let gaugeCtx = null;
let lastAlertIds = new Set();

// ─── HELPERS ──────────────────────────────────────────
function fmt(val, decimals = 1) {
  if (val === null || val === undefined || val === "" || val === "–") return "–";
  const n = parseFloat(val);
  return isNaN(n) ? String(val) : n.toFixed(decimals);
}

function fmtDateTime(isoStr) {
  if (!isoStr) return "–";
  try {
    const d = new Date(isoStr.replace("Z", "+00:00"));
    return d.toUTCString().replace("GMT", "UTC").split(",")[1].trim().slice(0, 17);
  } catch { return isoStr.slice(0, 16).replace("T", " ") + " UTC"; }
}

function flareClassCSS(cls) {
  if (!cls) return "cls-q";
  const c = cls[0].toUpperCase();
  if (c === "X") return "cls-x";
  if (c === "M") return "cls-m";
  if (c === "C") return "cls-c";
  if (c === "B") return "cls-b";
  return "cls-q";
}

function kpColor(kp) {
  const v = parseFloat(kp);
  if (v >= 7) return "#ef4444";
  if (v >= 5) return "#ff9800";
  if (v >= 3) return "#ffd166";
  return "#00d4aa";
}

function kpLabel(kp) {
  const v = parseFloat(kp);
  if (v >= 8) return { text: "SEVERE", bg: "rgba(239,68,68,0.2)", color: "#f87171" };
  if (v >= 6) return { text: "STRONG", bg: "rgba(239,68,68,0.15)", color: "#fb923c" };
  if (v >= 5) return { text: "MODERATE", bg: "rgba(255,152,0,0.15)", color: "#fbbf24" };
  if (v >= 3) return { text: "MINOR", bg: "rgba(255,209,102,0.15)", color: "#fde68a" };
  return { text: "QUIET", bg: "rgba(0,212,170,0.15)", color: "#00d4aa" };
}

function showToast(msg, type = "info") {
  const container = document.getElementById("toastContainer");
  const t = document.createElement("div");
  t.className = `toast ${type === "alert" ? "alert-toast" : "success-toast"}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => {
    t.style.animation = "toastOut 0.4s ease forwards";
    setTimeout(() => t.remove(), 400);
  }, 4000);
}

async function fetchJSON(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json();
}

// ─── UTC CLOCK ────────────────────────────────────────
function startClock() {
  function tick() {
    const now = new Date();
    const pad = n => String(n).padStart(2, "0");
    document.getElementById("utcClock").textContent =
      `${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())} UTC`;
  }
  tick();
  setInterval(tick, 1000);
}

// ─── ANIMATED COUNTER ─────────────────────────────────
function animateCounter(el, target, decimals = 0, duration = 800) {
  const start = parseFloat(el.textContent) || 0;
  const end = parseFloat(target) || 0;
  const startTime = performance.now();
  function step(now) {
    const p = Math.min((now - startTime) / duration, 1);
    const ease = p < 0.5 ? 2 * p * p : -1 + (4 - 2 * p) * p;
    el.textContent = (start + (end - start) * ease).toFixed(decimals);
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ─── GAUGE (SEMI-CIRCLE) ──────────────────────────────
function drawGauge(canvas, value, max = 9) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const cx = w / 2, cy = h - 20;
  const r = Math.min(w * 0.42, h * 0.75);
  const startAngle = Math.PI;
  const endAngle = 2 * Math.PI;
  const pct = Math.min(value / max, 1);
  const fillEnd = startAngle + pct * Math.PI;

  // Track
  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, endAngle);
  ctx.strokeStyle = "rgba(255,255,255,0.07)";
  ctx.lineWidth = 18;
  ctx.lineCap = "round";
  ctx.stroke();

  // Fill gradient
  const grad = ctx.createLinearGradient(cx - r, cy, cx + r, cy);
  grad.addColorStop(0, "#00d4aa");
  grad.addColorStop(0.4, "#ffd166");
  grad.addColorStop(0.7, "#ff6b35");
  grad.addColorStop(1, "#ef4444");

  ctx.beginPath();
  ctx.arc(cx, cy, r, startAngle, fillEnd);
  ctx.strokeStyle = grad;
  ctx.lineWidth = 18;
  ctx.lineCap = "round";
  ctx.stroke();

  // Glow
  ctx.shadowColor = kpColor(value);
  ctx.shadowBlur = 15;
  ctx.beginPath();
  ctx.arc(cx, cy, r, Math.max(fillEnd - 0.05, startAngle), fillEnd);
  ctx.strokeStyle = "white";
  ctx.lineWidth = 4;
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Tick marks
  for (let i = 0; i <= 9; i++) {
    const angle = Math.PI + (i / 9) * Math.PI;
    const inner = r - 14;
    const outer = r + 4;
    const x1 = cx + inner * Math.cos(angle);
    const y1 = cy + inner * Math.sin(angle);
    const x2 = cx + outer * Math.cos(angle);
    const y2 = cy + outer * Math.sin(angle);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.strokeStyle = "rgba(255,255,255,0.2)";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }
}

// ─── FLARE HISTORY CHART ──────────────────────────────
function buildFlareChart(flares) {
  if (flareChartInstance) flareChartInstance.destroy();

  // Bucket flares into daily counts by class
  const buckets = {};
  flares.forEach(f => {
    const day = (f.begin_time || "").slice(0, 10);
    if (!day) return;
    if (!buckets[day]) buckets[day] = { C: 0, M: 0, X: 0 };
    const cls = (f.class_type || "C")[0].toUpperCase();
    if (buckets[day][cls] !== undefined) buckets[day][cls]++;
  });

  const labels = Object.keys(buckets).sort();
  const cData = labels.map(d => buckets[d].C);
  const mData = labels.map(d => buckets[d].M);
  const xData = labels.map(d => buckets[d].X);

  const canvas = document.getElementById("flareChart");
  const ctx = canvas.getContext("2d");

  flareChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels.map(l => l.slice(5)), // MM-DD
      datasets: [
        { label: "C-class", data: cData, backgroundColor: "rgba(0,212,170,0.7)", borderRadius: 4 },
        { label: "M-class", data: mData, backgroundColor: "rgba(255,152,0,0.8)", borderRadius: 4 },
        { label: "X-class", data: xData, backgroundColor: "rgba(239,68,68,0.9)", borderRadius: 4 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(8, 12, 26, 0.95)",
          titleColor: "rgba(255,255,255,0.7)",
          bodyColor: "white",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1,
        },
      },
      scales: {
        x: {
          stacked: true,
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: { color: "rgba(255,255,255,0.4)", font: { size: 11 } },
        },
        y: {
          stacked: true,
          beginAtZero: true,
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: { color: "rgba(255,255,255,0.4)", font: { size: 11 }, stepSize: 1 },
        },
      },
    },
  });
}

// ─── KP INDEX CHART ───────────────────────────────────
function buildKpChart(kpData) {
  if (kpChartInstance) kpChartInstance.destroy();

  const labels = kpData.slice(-48).map(k => {
    const t = k.time_tag || "";
    return t.slice(11, 16) || "";
  });

  const values = kpData.slice(-48).map(k => {
    const v = k.kp || k.Kp || 0;
    return parseFloat(String(v).replace(/[+-]/g, "")) || 0;
  });

  const colors = values.map(v => kpColor(v));

  const canvas = document.getElementById("kpChart");
  const ctx = canvas.getContext("2d");

  kpChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Kp Index",
        data: values,
        backgroundColor: colors,
        borderRadius: 3,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(8,12,26,0.95)",
          titleColor: "rgba(255,255,255,0.7)",
          bodyColor: "white",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1,
          callbacks: {
            label: ctx => `Kp: ${ctx.raw}`,
          },
        },
        annotation: {
          annotations: {
            g1: { type: "line", yMin: 4, yMax: 4, borderColor: "rgba(255,152,0,0.3)", borderWidth: 1, borderDash: [5, 5] },
            g3: { type: "line", yMin: 6, yMax: 6, borderColor: "rgba(239,68,68,0.3)", borderWidth: 1, borderDash: [5, 5] },
          },
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: { color: "rgba(255,255,255,0.35)", font: { size: 10 }, maxTicksLimit: 12 },
        },
        y: {
          min: 0, max: 9,
          grid: { color: "rgba(255,255,255,0.04)" },
          ticks: { color: "rgba(255,255,255,0.4)", font: { size: 11 }, stepSize: 1 },
        },
      },
    },
  });
}

// ─── RENDER FUNCTIONS ─────────────────────────────────

function renderMetrics(kpData, flares, cmes, wind) {
  // Kp
  const latestKp = kpData.length > 0
    ? parseFloat(String(kpData[kpData.length - 1]?.kp || kpData[kpData.length - 1]?.Kp || 0).replace(/[+-]/g, ""))
    : null;

  if (latestKp !== null) {
    animateCounter(document.getElementById("kpValue"), latestKp, 1);
    const label = kpLabel(latestKp);
    const badge = document.getElementById("kpBadge");
    badge.textContent = label.text;
    badge.style.background = label.bg;
    badge.style.color = label.color;
    document.getElementById("kpStatus").textContent = `Geomagnetic ${label.text.toLowerCase()} conditions`;
    drawGauge(document.getElementById("gaugeCanvas"), latestKp, 9);
    document.getElementById("gaugeValue").textContent = latestKp.toFixed(1);
    document.getElementById("gaugeLabel").textContent = label.text;
    document.getElementById("gaugeUpdated").textContent = `Updated ${new Date().toUTCString().slice(17, 25)} UTC`;
  }

  // Flares
  const recentFlares7 = flares.filter(f => {
    const d = new Date(f.begin_time || 0);
    return (Date.now() - d.getTime()) < 7 * 86400000;
  });
  document.getElementById("flareCount").textContent = recentFlares7.length;
  const latestFlare = flares[0];
  document.getElementById("flareLatest").textContent = latestFlare
    ? `Latest: ${latestFlare.class_type} — ${fmtDateTime(latestFlare.begin_time)}`
    : "No recent flares";
  const flareLbl = recentFlares7.some(f => (f.class_type || "").startsWith("X"))
    ? { text: "X-class", bg: "rgba(239,68,68,0.2)", color: "#f87171" }
    : recentFlares7.some(f => (f.class_type || "").startsWith("M"))
    ? { text: "M-class", bg: "rgba(255,152,0,0.15)", color: "#fbbf24" }
    : { text: "C-class", bg: "rgba(0,212,170,0.12)", color: "#00d4aa" };
  const fb = document.getElementById("flareBadge");
  fb.textContent = flareLbl.text;
  fb.style.background = flareLbl.bg;
  fb.style.color = flareLbl.color;

  // CMEs
  const recentCme7 = cmes.filter(c => {
    const d = new Date(c.start_time || 0);
    return (Date.now() - d.getTime()) < 7 * 86400000;
  });
  document.getElementById("cmeCount").textContent = recentCme7.length;
  const latestCme = cmes[0];
  document.getElementById("cmeLatestSpeed").textContent = latestCme?.speed_kms
    ? `Latest: ${latestCme.speed_kms} km/s — ${latestCme.type}`
    : latestCme ? `Latest: ${fmtDateTime(latestCme.start_time)}` : "No recent CMEs";
  const cb = document.getElementById("cmeBadge");
  cb.textContent = recentCme7.length > 3 ? "Active" : "Nominal";
  cb.style.background = recentCme7.length > 3 ? "rgba(255,107,53,0.2)" : "rgba(0,212,170,0.12)";
  cb.style.color = recentCme7.length > 3 ? "#ff6b35" : "#00d4aa";

  // Bz
  const bz = parseFloat(wind.bz_gsm || wind.Bz || 0);
  document.getElementById("bzValue").textContent = `${bz >= 0 ? "+" : ""}${bz.toFixed(1)} nT`;
  const bzEl = document.getElementById("bzStatus");
  const bzB = document.getElementById("bzBadge");
  if (bz < -10) {
    bzEl.textContent = "Strongly southward — storm risk HIGH";
    bzB.textContent = "High Risk";
    bzB.style.background = "rgba(239,68,68,0.2)"; bzB.style.color = "#f87171";
  } else if (bz < -5) {
    bzEl.textContent = "Southward — moderate storm risk";
    bzB.textContent = "Moderate";
    bzB.style.background = "rgba(255,152,0,0.15)"; bzB.style.color = "#fbbf24";
  } else if (bz > 0) {
    bzEl.textContent = "Northward — low storm risk";
    bzB.textContent = "Low Risk";
    bzB.style.background = "rgba(0,212,170,0.12)"; bzB.style.color = "#00d4aa";
  } else {
    bzEl.textContent = "Near neutral";
    bzB.textContent = "Nominal";
    bzB.style.background = "rgba(255,255,255,0.06)"; bzB.style.color = "rgba(255,255,255,0.5)";
  }
}

function renderPrediction(pred) {
  if (!pred) return;

  const cls = pred.predicted_class || "–";
  const badge = document.getElementById("predClassBadge");
  badge.textContent = cls;

  const clsColorMap = {
    "Quiet":   { bg: "rgba(0,212,170,0.15)", color: "#00d4aa", border: "rgba(0,212,170,0.3)" },
    "C-class": { bg: "rgba(6,182,212,0.15)",  color: "#06b6d4", border: "rgba(6,182,212,0.3)" },
    "M-class": { bg: "rgba(255,152,0,0.15)",  color: "#fb923c", border: "rgba(255,152,0,0.35)" },
    "X-class": { bg: "rgba(239,68,68,0.15)",  color: "#f87171", border: "rgba(239,68,68,0.4)" },
  };
  const style = clsColorMap[cls] || clsColorMap["C-class"];
  badge.style.background = style.bg;
  badge.style.color = style.color;
  badge.style.boxShadow = `0 0 30px ${style.border}`;

  document.getElementById("predConfidence").textContent =
    `Confidence: ${pred.confidence?.toFixed(1) || "–"}%`;
  document.getElementById("predUpdated").textContent =
    pred.generated_at ? fmtDateTime(pred.generated_at) : "–";

  // Probability bars
  const probs = pred.probabilities || {};
  const setProbBar = (id, pctId, val) => {
    const bar = document.getElementById(id);
    const pct = document.getElementById(pctId);
    setTimeout(() => { bar.style.width = `${val || 0}%`; }, 100);
    if (pct) pct.textContent = `${(val || 0).toFixed(1)}%`;
  };
  setProbBar("prob-quiet", "pct-quiet", probs.quiet);
  setProbBar("prob-c", "pct-c", probs.c_class);
  setProbBar("prob-m", "pct-m", probs.m_class);
  setProbBar("prob-x", "pct-x", probs.x_class);

  // Feature importances
  const feats = pred.feature_importances || {};
  const featList = document.getElementById("featureList");
  const sorted = Object.entries(feats).sort((a, b) => b[1] - a[1]).slice(0, 8);
  featList.innerHTML = sorted.map(([name, pct]) => `
    <div class="feature-bar-wrap">
      <div class="feature-name">${name.replace(/_/g, " ")}</div>
      <div class="feature-track">
        <div class="feature-fill" style="width: ${Math.min(pct * 3, 100)}%"></div>
      </div>
    </div>
  `).join("") || "<div style='color:rgba(255,255,255,0.3);font-size:.8rem'>No data</div>";

  // Meta
  const input = pred.input_summary || {};
  const trainedEl = document.getElementById("metaTrainedAt");
  const flaresEl = document.getElementById("metaInputFlares");
  const kpEl = document.getElementById("metaInputKp");
  if (trainedEl) trainedEl.querySelector("span:last-child").textContent =
    pred.model_trained_at ? fmtDateTime(pred.model_trained_at) : "–";
  if (flaresEl) flaresEl.querySelector("span:last-child").textContent =
    input.recent_flares_7d ?? "–";
  if (kpEl) kpEl.querySelector("span:last-child").textContent =
    input.avg_kp != null ? `${parseFloat(input.avg_kp).toFixed(2)}` : "–";
}

function renderFlares(flares) {
  const list = document.getElementById("flaresList");
  document.getElementById("flareTabCount").textContent = flares.length;
  if (!flares.length) {
    list.innerHTML = `<div class="no-alerts">No recent flares recorded</div>`;
    return;
  }
  list.innerHTML = flares.slice(0, 20).map(f => `
    <div class="event-item">
      <div class="event-class ${flareClassCSS(f.class_type)}">${f.class_type || "–"}</div>
      <div class="event-info">
        <div class="event-time">${fmtDateTime(f.begin_time)}</div>
        <div class="event-loc">${f.source_location || "Unknown location"} ${f.active_region ? `· AR${f.active_region}` : ""}</div>
      </div>
    </div>
  `).join("");
}

function renderCMEs(cmes) {
  const list = document.getElementById("cmeList");
  document.getElementById("cmeTabCount").textContent = cmes.length;
  if (!cmes.length) {
    list.innerHTML = `<div class="no-alerts">No recent CMEs recorded</div>`;
    return;
  }
  list.innerHTML = cmes.slice(0, 15).map(c => `
    <div class="event-item">
      <div class="event-class cls-b">${c.type || "CME"}</div>
      <div class="event-info">
        <div class="event-time">${fmtDateTime(c.start_time)}</div>
        <div class="event-loc">${c.speed_kms ? `${c.speed_kms} km/s` : "Speed N/A"} ${c.half_angle ? `· ${c.half_angle}° half-angle` : ""}</div>
        ${c.note ? `<div class="event-note">${c.note}</div>` : ""}
      </div>
    </div>
  `).join("");
}

function renderAlerts(alerts) {
  const body = document.getElementById("alertsBody");
  const countEl = document.getElementById("alertCount");
  countEl.textContent = alerts.length;

  if (!alerts.length) {
    body.innerHTML = `<div class="no-alerts">✅ No active space weather alerts</div>`;
    return;
  }

  // Show toast for new alerts
  alerts.forEach(a => {
    const id = a.serial_number || a.issue_datetime;
    if (id && !lastAlertIds.has(id)) {
      lastAlertIds.add(id);
      const msg = (a.message || "").slice(0, 80);
      if (msg) showToast(`🚨 New Alert: ${msg}...`, "alert");
    }
  });

  body.innerHTML = alerts.slice(0, 6).map(a => {
    const msg = a.message || "";
    const isWarn = msg.includes("WARNING") || msg.includes("WATCH");
    return `
      <div class="alert-item ${isWarn ? "warning" : ""}">
        <div class="alert-time">${a.issue_datetime ? fmtDateTime(a.issue_datetime) : "–"}</div>
        <div class="alert-msg">${msg.slice(0, 120)}${msg.length > 120 ? "…" : ""}</div>
      </div>
    `;
  }).join("");
}

function renderStorms(geo) {
  const list = document.getElementById("stormList");
  const storms = geo.storms || [];
  if (!storms.length) {
    list.innerHTML = `<div class="no-alerts">🟢 No recent geomagnetic storms</div>`;
    return;
  }
  list.innerHTML = storms.slice(0, 5).map(s => {
    const kpList = s.all_kp_index || [];
    const maxKp = kpList.length ? Math.max(...kpList.map(k => parseFloat(k.kpIndex || 0))) : 0;
    const g = maxKp >= 8 ? "G4-G5" : maxKp >= 6 ? "G3" : maxKp >= 5 ? "G2" : "G1";
    const severity = maxKp >= 7 ? "🔴" : maxKp >= 5 ? "🟠" : "🟡";
    return `
      <div class="storm-item">
        <div class="storm-severity">${severity}</div>
        <div class="storm-details">
          <div class="storm-time">${fmtDateTime(s.start_time)}</div>
          <div class="storm-desc">Class ${g} — Peak Kp: ${maxKp.toFixed(1)}</div>
        </div>
      </div>
    `;
  }).join("");
}

// ─── MAIN DATA FETCH ──────────────────────────────────
async function fetchAll() {
  try {
    const [flares, cmes, geo, pred, wind, alerts] = await Promise.allSettled([
      fetchJSON("/api/flares?days=30"),
      fetchJSON("/api/cme?days=30"),
      fetchJSON("/api/geomagnetic"),
      fetchJSON("/api/predict"),
      fetchJSON("/api/solar-wind"),
      fetchJSON("/api/alerts"),
    ]);

    const flaresData  = flares.status  === "fulfilled" ? flares.value  : [];
    const cmesData    = cmes.status    === "fulfilled" ? cmes.value    : [];
    const geoData     = geo.status     === "fulfilled" ? geo.value     : { storms: [], kp_index_72h: [] };
    const predData    = pred.status    === "fulfilled" ? pred.value    : null;
    const windData    = wind.status    === "fulfilled" ? wind.value    : {};
    const alertsData  = alerts.status  === "fulfilled" ? alerts.value  : [];

    const kpData = geoData.kp_index_72h || [];

    renderMetrics(kpData, flaresData, cmesData, windData);
    renderPrediction(predData);
    renderFlares(flaresData);
    renderCMEs(cmesData);
    renderAlerts(alertsData);
    renderStorms(geoData);
    buildFlareChart(flaresData);
    buildKpChart(kpData);

    document.getElementById("lastRefresh").textContent =
      `Last refresh: ${new Date().toUTCString().slice(17, 25)} UTC`;

  } catch (err) {
    console.error("Dashboard fetch error:", err);
    showToast("⚠️ Could not reach the backend API. Check your connection.", "alert");
  }
}

// ─── NAV HIGHLIGHTING ─────────────────────────────────
function initNavHighlight() {
  const sections = ["overview", "prediction", "events", "geomagnetic"];
  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        sections.forEach(id => {
          const link = document.getElementById(`nav-${id}`);
          if (link) link.classList.toggle("active", e.target.id === id);
        });
      }
    });
  }, { threshold: 0.4 });
  sections.forEach(id => {
    const el = document.getElementById(id);
    if (el) observer.observe(el);
  });
}

// ─── INIT ─────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  startClock();
  initNavHighlight();

  // Initial load
  fetchAll();

  // Auto-refresh every 60 seconds
  setInterval(fetchAll, REFRESH_INTERVAL_MS);

  showToast("🚀 SolarSentinel connected — loading live space weather data...", "success");
});
