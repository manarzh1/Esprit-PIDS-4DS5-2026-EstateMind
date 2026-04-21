"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, ScanSearch, TrendingUp, Cpu,
  Map, Globe, Search, Star, Zap
} from "lucide-react";

const NAV = [
  { href:"/",              label:"Dashboard",    Icon:LayoutDashboard },
  { href:"/recherche",     label:"Recherche",    Icon:Search           },
  { href:"/opportunites",  label:"Opportunités", Icon:Zap              },
  { href:"/analyse",       label:"Analyser",     Icon:ScanSearch       },
  { href:"/marche",        label:"Marché",       Icon:TrendingUp       },
  { href:"/territoire",    label:"Territoire",   Icon:Globe            },
  { href:"/carte",         label:"Carte",        Icon:Map              },
  { href:"/portefeuille",  label:"Portefeuille", Icon:Star             },
  { href:"/pipeline",      label:"Pipeline",     Icon:Cpu              },
];

export function NavBar() {
  const path = usePathname();
  return (
    <nav style={{
      borderBottom:"1px solid var(--bor)", padding:"0 18px",
      display:"flex", alignItems:"center", height:52,
      position:"sticky", top:0, zIndex:50,
      background:"rgba(9,9,11,0.93)", backdropFilter:"blur(12px)",
    }}>
      <Link href="/" style={{ display:"flex", alignItems:"center", gap:7, marginRight:20, textDecoration:"none", flexShrink:0 }}>
        <div style={{ width:24,height:24,borderRadius:5,background:"var(--gold)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:12 }}>🏛</div>
        <span style={{ fontSize:14,fontFamily:"var(--font-display)",fontWeight:600,color:"var(--txt)",letterSpacing:".02em" }}>Estate Mind</span>
        <span style={{ fontSize:9,color:"var(--mut)",fontFamily:"var(--font-mono)",background:"var(--el)",padding:"2px 5px",borderRadius:4,border:"1px solid var(--bor)" }}>v3.2</span>
      </Link>
      <div style={{ display:"flex", gap:1, overflowX:"auto" }}>
        {NAV.map(({ href, label, Icon }) => {
          const active = path === href;
          const isNew  = href === "/opportunites";
          return (
            <Link key={href} href={href} style={{
              display:"flex", alignItems:"center", gap:5,
              padding:"5px 9px", borderRadius:6, textDecoration:"none",
              fontSize:12, fontFamily:"var(--font-body)", flexShrink:0,
              color:      active ? "var(--gold)" : "var(--mut)",
              background: active ? "var(--gdim)"  : "transparent",
              transition:"all .15s", position:"relative",
            }}>
              <Icon size={12}/>{label}
              {isNew && !active && (
                <span style={{ fontSize:8, padding:"1px 4px", borderRadius:999, background:"rgba(200,169,110,.2)", color:"var(--gold)", border:"1px solid rgba(200,169,110,.3)", marginLeft:2 }}>
                  NEW
                </span>
              )}
            </Link>
          );
        })}
      </div>
      <div style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:6, flexShrink:0 }}>
        <div className="animate-pulse" style={{ width:5,height:5,borderRadius:"50%",background:"var(--ok)" }}/>
        <span style={{ fontSize:10, color:"var(--mut)" }}>Live</span>
      </div>
    </nav>
  );
}
