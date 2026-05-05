"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

const BOS = [
  { href:"/bo1", icon:"/assets/icons/search1.png", label:"Market Reliability"  },
  { href:"/bo2", icon:"/assets/icons/map1.png",    label:"Territorial Dynamics" },
  { href:"/bo3", icon:"/assets/icons/chart1.png",  label:"Price Estimation"     },
  { href:"/bo4", icon:"/assets/icons/report1.png", label:"Investment Decisions" },
  { href:"/bo5", icon:"/assets/icons/shield1.png", label:"Legal Compliance"     },
  { href:"/bo6", icon:"/assets/icons/ai1.png",     label:"Platform Operations"  },
];

export function Sidebar() {
  const path = usePathname();
  const [aiMsg,  setAiMsg]  = useState("");
  const [aiChat, setAiChat] = useState([
    {role:"bot",text:"Hello 👋 I can explain a trust score, compare two zones or generate a report."},
  ]);

  /* Mirror the static JS exactly:
     collapse-btn  → toggle .sidebar-collapsed on body
     ai-button     → toggle .assistant-open on body           */
  function toggleCollapse() {
    document.body.classList.toggle("sidebar-collapsed");
  }
  function toggleAI() {
    document.body.classList.toggle("assistant-open");
  }
  function closeAI() {
    document.body.classList.remove("assistant-open");
  }
  function sendMsg() {
    if (!aiMsg.trim()) return;
    const q = aiMsg.trim();
    setAiChat(c => [...c,
      {role:"user", text: q},
      {role:"bot",  text: `Analysing "${q.slice(0,30)}..." — check BO1 for trust scores and BO3 for pricing.`},
    ]);
    setAiMsg("");
  }

  return (
    <>
      {/* ── SIDEBAR — exact structure from dashboard.html ── */}
      <aside className="dash-sidebar" id="sidebar">

        <div className="dash-brand">
          <span className="logo-mark">
            <img src="/assets/logo1.png" alt="Estate Mind"
              style={{width:"100%",height:"100%",objectFit:"contain"}} />
          </span>
          <strong>Estate Mind</strong>
        </div>

        <button className="collapse-btn" onClick={toggleCollapse}>☰</button>

        <nav className="dash-nav">
          {BOS.map(bo => (
            <a key={bo.href} href={bo.href}
               className={path.startsWith(bo.href) ? "active" : ""}>
              <img src={bo.icon} alt="" />
              <span>{bo.label}</span>
            </a>
          ))}
        </nav>

        <div className="sidebar-card">
          <img src="/assets/avatar-advisor.png" alt="" />
          <p>Need a quick insight?</p>
          <button onClick={toggleAI}>Ask AI</button>
        </div>
      </aside>

      {/* ── AI button + panel — exact structure from dashboard.html ── */}
      <button className="ai-button" onClick={toggleAI}>
        <img src="/assets/icons/ai.png" alt="AI" />
      </button>

      <aside className="ai-panel">
        <div className="ai-head">
          <strong>Estate Mind AI Assistant</strong>
          <button onClick={closeAI}>×</button>
        </div>
        <div className="ai-chat">
          {aiChat.map((m,i) => (
            <p key={i} className={m.role === "bot" ? "bot" : "user"}>{m.text}</p>
          ))}
        </div>
        <div className="ai-input">
          <input
            value={aiMsg}
            onChange={e => setAiMsg(e.target.value)}
            onKeyDown={e => e.key === "Enter" && sendMsg()}
            placeholder="Ask a question..."
          />
          <button onClick={sendMsg}>➜</button>
        </div>
      </aside>
    </>
  );
}
