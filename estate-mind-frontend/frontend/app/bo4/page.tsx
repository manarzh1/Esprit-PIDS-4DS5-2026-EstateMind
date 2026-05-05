"use client";

const FEATURES = [
  { icon:"🤖", title:"PPO Reinforcement Learning", desc:"Proximal Policy Optimization agent trained on Tunisian real estate market data to recommend optimal investment strategies." },
  { icon:"📊", title:"SHAP Explainability", desc:"Shapley values to explain every investment recommendation — understand exactly why the model suggests a particular action." },
  { icon:"💡", title:"Investment Scoring", desc:"Composite score combining trust score, rental yield, market trends, and legal risk for each identified opportunity." },
  { icon:"🎯", title:"Risk-Adjusted Returns", desc:"Automated calculation of risk-adjusted returns (Sharpe ratio) for each investment recommendation." },
  { icon:"📈", title:"Portfolio Optimization", desc:"Multi-asset portfolio optimization to maximize returns while managing risk across different Tunisian cities and property types." },
  { icon:"⚡", title:"Real-time Monitoring", desc:"Continuous monitoring of investment positions with automatic alerts when market conditions change significantly." },
];

export default function BO4Page() {
  return (
    <div style={{display:"flex",flexDirection:"column",gap:20}}>
      {/* Header */}
      <div style={{display:"flex",alignItems:"center",gap:10}}>
        <span style={{display:"inline-block",background:"var(--mint)",color:"var(--green)",borderRadius:999,padding:"6px 14px",fontSize:11,fontWeight:800,textTransform:"uppercase",letterSpacing:".07em"}}>BO4</span>
        <span style={{fontSize:13,color:"var(--mut)",fontWeight:600}}>Investment Decisions — PPO · SHAP · Scoring</span>
      </div>

      {/* Coming soon hero */}
      <div className="panel" style={{padding:"48px 40px",textAlign:"center"}}>
        <div style={{fontSize:56,marginBottom:16}}>💼</div>
        <div style={{display:"inline-block",background:"var(--mint)",color:"var(--green)",borderRadius:999,padding:"7px 16px",fontSize:11,fontWeight:800,textTransform:"uppercase",letterSpacing:".08em",marginBottom:16}}>
          In Development
        </div>
        <h2 style={{fontFamily:"var(--font-display)",fontSize:28,fontWeight:600,color:"var(--navy)",marginBottom:12}}>
          Investment Decisions Module
        </h2>
        <p style={{fontSize:15,color:"var(--mut)",lineHeight:1.7,maxWidth:520,margin:"0 auto 24px"}}>
          AI-powered investment recommendations using Reinforcement Learning (PPO) and SHAP explainability.
          This module is being developed and will be available in the next release.
        </p>
        <div style={{display:"flex",gap:12,justifyContent:"center",flexWrap:"wrap",marginBottom:32}}>
          {["PPO Agent","SHAP Values","Yield Optimizer","Risk Scoring","Portfolio Builder","ROI Forecasting"].map(tag=>(
            <span key={tag} style={{background:"rgba(47,156,126,.1)",color:"var(--green)",borderRadius:999,padding:"6px 14px",fontSize:12,fontWeight:700,border:"1px solid rgba(47,156,126,.25)"}}>
              {tag}
            </span>
          ))}
        </div>
      </div>

      {/* Planned features grid */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:16}}>
        {FEATURES.map(f=>(
          <div key={f.title} className="panel" style={{padding:24,opacity:.85}}>
            <div style={{fontSize:32,marginBottom:14}}>{f.icon}</div>
            <h3 style={{fontSize:15,fontWeight:700,color:"var(--navy)",marginBottom:8}}>{f.title}</h3>
            <p style={{fontSize:13,color:"var(--mut)",lineHeight:1.7}}>{f.desc}</p>
          </div>
        ))}
      </div>

      {/* Progress indicator */}
      <div className="panel" style={{padding:24}}>
        <div style={{fontSize:14,fontWeight:700,color:"var(--navy)",marginBottom:16}}>Development Progress</div>
        {[
          {label:"Data collection & feature engineering",pct:100},
          {label:"PPO environment design",pct:75},
          {label:"Model training & validation",pct:45},
          {label:"SHAP integration",pct:30},
          {label:"API endpoints",pct:20},
          {label:"Frontend integration",pct:0},
        ].map(item=>(
          <div key={item.label} style={{marginBottom:12}}>
            <div style={{display:"flex",justifyContent:"space-between",marginBottom:5}}>
              <span style={{fontSize:13,color:"var(--txt)"}}>{item.label}</span>
              <span style={{fontSize:12,fontWeight:700,color:item.pct===100?"var(--ok)":"var(--mut)"}}>{item.pct}%</span>
            </div>
            <div style={{height:6,background:"var(--line)",borderRadius:3,overflow:"hidden"}}>
              <div style={{height:"100%",width:`${item.pct}%`,background:item.pct===100?"var(--green)":"rgba(47,156,126,.5)",borderRadius:3,transition:"width 1s ease"}}/>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
