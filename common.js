/* =====================================================
   SOLAR SENTINEL — Shared Utilities, API Client & Auth
   ===================================================== */

const API = "https://solar-flare-api-1mvi.onrender.com";

/* ─── AUTH ─────────────────────────────────────────── */
function getToken()  { return localStorage.getItem("ss_token"); }
function getUser()   { try { return JSON.parse(localStorage.getItem("ss_user") || "null"); } catch { return null; } }
function logout()    { localStorage.removeItem("ss_token"); localStorage.removeItem("ss_user"); window.location.href = "/login.html"; }

/** Call on every protected page. Redirects to /login.html if not authenticated. */
async function requireAuth() {
  const token = getToken();
  if (!token) { window.location.href = "/login.html"; return false; }
  try {
    const res = await fetch(`${API}/api/auth/me`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!res.ok) { logout(); return false; }
    const user = await res.json();
    localStorage.setItem("ss_user", JSON.stringify(user));
    renderUserBadge(user);
    return true;
  } catch {
    // Network error — allow page to load (Render may be waking up)
    const user = getUser();
    if (user) { renderUserBadge(user); return true; }
    window.location.href = "/login.html"; return false;
  }
}

function renderUserBadge(user) {
  const el = document.getElementById("userBadge");
  if (!el || !user) return;
  el.innerHTML = `
    <div style="display:flex;align-items:center;gap:.6rem;">
      <div style="width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,var(--orange),var(--purple));display:flex;align-items:center;justify-content:center;font-size:.85rem;font-weight:700;color:white;flex-shrink:0;">
        ${(user.username||"U")[0].toUpperCase()}
      </div>
      <div style="display:flex;flex-direction:column;line-height:1.2;">
        <span style="font-size:.78rem;font-weight:600;color:white;">${user.username||"User"}</span>
        <span style="font-size:.65rem;color:rgba(255,255,255,.35);font-family:var(--font-m);">${user.email||""}</span>
      </div>
      <button onclick="logout()" title="Sign out" style="margin-left:.25rem;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:7px;color:rgba(255,255,255,.5);font-size:.72rem;padding:.3rem .6rem;cursor:pointer;transition:all .2s;font-family:var(--font-m);" onmouseover="this.style.background='rgba(239,68,68,.15)';this.style.color='#f87171'" onmouseout="this.style.background='rgba(255,255,255,.06)';this.style.color='rgba(255,255,255,.5)'">
        ↩ Logout
      </button>
    </div>`;
}

/* ─── API HELPERS ───────────────────────────────────── */
function getAuthHeaders() {
  const token = getToken();
  return token ? { "Authorization": `Bearer ${token}` } : {};
}

async function get(path) {
  const r = await fetch(`${API}${path}`, { headers: getAuthHeaders() });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

/* ─── FORMATTING ────────────────────────────────────── */
function fmtDT(s) {
  if (!s) return "–";
  try {
    const d = new Date(s.replace("Z", "+00:00"));
    return d.toUTCString().replace("GMT","UTC").split(",")[1].trim().slice(0,17);
  } catch { return s.slice(0,16).replace("T"," ") + " UTC"; }
}

function kpColor(v) {
  const n = parseFloat(v);
  return n >= 7 ? "#ef4444" : n >= 5 ? "#ff9800" : n >= 3 ? "#ffd166" : "#00d4aa";
}
function kpLabel(v) {
  const n = parseFloat(v);
  return n >= 8 ? { text:"SEVERE",   bg:"rgba(239,68,68,.2)",   color:"#f87171" }
       : n >= 6 ? { text:"STRONG",   bg:"rgba(239,68,68,.15)",  color:"#fb923c" }
       : n >= 5 ? { text:"MODERATE", bg:"rgba(255,152,0,.15)",  color:"#fbbf24" }
       : n >= 3 ? { text:"MINOR",    bg:"rgba(255,209,102,.15)",color:"#fde68a" }
       :          { text:"QUIET",    bg:"rgba(0,212,170,.15)",   color:"#00d4aa" };
}
function flareCSS(c) {
  if (!c) return "cls-q";
  const x = c[0].toUpperCase();
  return x==="X"?"cls-x":x==="M"?"cls-m":x==="C"?"cls-c":x==="B"?"cls-b":"cls-q";
}

/* ─── TOAST ─────────────────────────────────────────── */
function toast(msg, type="ok") {
  const c = document.getElementById("toasts");
  if (!c) return;
  const t = document.createElement("div");
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => { t.style.animation="toastOut .4s ease forwards"; setTimeout(()=>t.remove(),400); }, 4500);
}

/* ─── CLOCK ─────────────────────────────────────────── */
function startClock() {
  const el = document.getElementById("clock");
  if (!el) return;
  const tick = () => {
    const n = new Date(), p = x => String(x).padStart(2,"0");
    el.textContent = `${p(n.getUTCHours())}:${p(n.getUTCMinutes())}:${p(n.getUTCSeconds())} UTC`;
  };
  tick(); setInterval(tick, 1000);
}

/* ─── GAUGE ─────────────────────────────────────────── */
function drawGauge(canvas, value, max=9) {
  const ctx = canvas.getContext("2d");
  const w=canvas.width, h=canvas.height, cx=w/2, cy=h-15;
  const r = Math.min(w*.44, h*.82);
  ctx.clearRect(0,0,w,h);
  ctx.beginPath(); ctx.arc(cx,cy,r,Math.PI,2*Math.PI);
  ctx.strokeStyle="rgba(255,255,255,.06)"; ctx.lineWidth=16; ctx.lineCap="round"; ctx.stroke();
  const pct = Math.min(value/max,1), fillEnd = Math.PI + pct*Math.PI;
  const g = ctx.createLinearGradient(cx-r,cy,cx+r,cy);
  g.addColorStop(0,"#00d4aa"); g.addColorStop(.4,"#ffd166"); g.addColorStop(.7,"#ff6b35"); g.addColorStop(1,"#ef4444");
  ctx.beginPath(); ctx.arc(cx,cy,r,Math.PI,fillEnd);
  ctx.strokeStyle=g; ctx.lineWidth=16; ctx.lineCap="round"; ctx.stroke();
  ctx.shadowColor=kpColor(value); ctx.shadowBlur=14;
  ctx.beginPath(); ctx.arc(cx,cy,r,Math.max(fillEnd-.04,Math.PI),fillEnd);
  ctx.strokeStyle="white"; ctx.lineWidth=4; ctx.stroke(); ctx.shadowBlur=0;
}

/* ─── COUNTER ANIM ──────────────────────────────────── */
function countUp(el, target, dec=0, dur=900) {
  const s=parseFloat(el.textContent)||0, e=parseFloat(target)||0, t0=performance.now();
  const step=now=>{
    const p=Math.min((now-t0)/dur,1), ease=p<.5?2*p*p:-1+(4-2*p)*p;
    el.textContent=(s+(e-s)*ease).toFixed(dec);
    if(p<1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/* ─── INIT ──────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  startClock();
  // Auto-highlight active nav link
  const page = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-item").forEach(a => {
    const href = (a.getAttribute("href") || "").split("/").pop();
    a.classList.toggle("active", href === page || (page === "" && href === "index.html"));
  });
});
