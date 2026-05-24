/* ═══════════════════════════════════════════
   IMMO TUNISIA — API & Utilities
   ═══════════════════════════════════════════ */

const API = "http://localhost:8002/api";

// ── API Calls ─────────────────────────────────────────────────────────────
async function apiGet(endpoint) {
  const r = await fetch(API + endpoint);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function apiPost(endpoint, body) {
  const r = await fetch(API + endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ── Toast Notifications ───────────────────────────────────────────────────
function showToast(message, type = "info") {
  let container = document.querySelector(".toast-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  const icons = { success: "✓", error: "✗", info: "ℹ" };
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || "ℹ"}</span> ${message}`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ── Format Numbers ─────────────────────────────────────────────────────────
function fmt(n, decimals = 0) {
  if (n == null || isNaN(n)) return "—";
  return Number(n).toLocaleString("fr-TN", { maximumFractionDigits: decimals });
}

function fmtPct(n) {
  if (n == null) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${Number(n).toFixed(1)}%`;
}

// ── Active Nav Link ────────────────────────────────────────────────────────
function setActiveNav() {
  const current = window.location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-link").forEach(link => {
    const href = link.getAttribute("href") || "";
    if (href === current || (current === "" && href === "index.html")) {
      link.classList.add("active");
    }
  });
}
document.addEventListener("DOMContentLoaded", setActiveNav);

// ── Status Check ───────────────────────────────────────────────────────────
async function checkStatus() {
  try {
    const data = await apiGet("/status");
    const dot = document.querySelector(".status-dot");
    const txt = document.querySelector(".status-text");
    if (dot) dot.classList.add("online");
    if (txt) txt.textContent = "API connectée";
    return data;
  } catch {
    const dot = document.querySelector(".status-dot");
    const txt = document.querySelector(".status-text");
    if (dot) { dot.classList.remove("online"); dot.classList.add("error"); }
    if (txt) txt.textContent = "API non joignable";
    return null;
  }
}

// ── Plotly Chart Defaults ──────────────────────────────────────────────────
const CHART_LAYOUT = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "#FAFAF8",
  font: { family: "DM Sans, sans-serif", color: "#4E4E4A" },
  margin: { t: 32, r: 16, b: 48, l: 56 },
  xaxis: {
    gridcolor: "#E8E7E4",
    linecolor: "#DDDBD8",
    tickfont: { size: 11 },
  },
  yaxis: {
    gridcolor: "#E8E7E4",
    linecolor: "#DDDBD8",
    tickfont: { size: 11 },
  },
  legend: {
    bgcolor: "rgba(255,255,255,0.8)",
    bordercolor: "#DDDBD8",
    borderwidth: 1,
    font: { size: 11 },
  },
  hovermode: "x unified",
};

const CHART_CONFIG = {
  displayModeBar: true,
  modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d"],
  displaylogo: false,
  responsive: true,
};
