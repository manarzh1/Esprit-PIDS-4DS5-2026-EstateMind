"use client";

const FEATURES = [
  { icon:"⚖", title:"CDR Analysis", desc:"Automated analysis of Tunisian real estate regulations (Code des Droits Réels) to identify legal risks in listings." },
  { icon:"📋", title:"CATU Compliance", desc:"Systematic verification of CATU (Cadastre Tunisien) references and property registration requirements." },
  { icon:"🛡", title:"Legal Risk Scoring", desc:"ML model trained on legal cases to predict the probability of legal complications in each property transaction." },
  { icon:"📖", title:"RAG Legal Database", desc:"Retrieval-Augmented Generation over the complete Tunisian real estate legal corpus for instant legal answers." },
  { icon:"🔍", title:"Document Verification", desc:"Automated detection of missing, contradictory or suspicious legal documents in property listings." },
  { icon:"📝", title:"Compliance Reports", desc:"Auto-generated compliance reports ready for notaries, lawyers and real estate professionals." },
];

export default function BO5Page() {
  return (
    <div style={{display:"flex",flexDirection:"column",gap:20}}>
      {/* Header */}
      <div style={{display:"flex",alignItems:"center",gap:10}}>
        <span style={{display:"inline-block",background:"var(--mint)",color:"var(--green)",borderRadius:999,padding:"6px 14px",fontSize:11,fontWeight:800,textTransform:"uppercase",letterSpacing:".07em"}}>BO5</span>
        <span style={{fontSize:13,color:"var(--mut)",fontWeight:600}}>Legal Compliance — CDR · CATU · RAG · Risk Score</span>
      </div>

      {/* Coming soon hero */}
      <div className="panel" style={{padding:"48px 40px",textAlign:"center"}}>
        <div style={{fontSize:56,marginBottom:16}}>⚖</div>
        <div style={{display:"inline-block",background:"var(--mint)",color:"var(--green)",borderRadius:999,padding:"7px 16px",fontSize:11,fontWeight:800,textTransform:"uppercase",letterSpacing:".08em",marginBottom:16}}>
          In Development
        </div>
        <h2 style={{fontFamily:"var(--font-display)",fontSize:28,fontWeight:600,color:"var(--navy)",marginBottom:12}}>
          Legal Compliance Module
        </h2>
        <p style={{fontSize:15,color:"var(--mut)",lineHeight:1.7,maxWidth:520,margin:"0 auto 24px"}}>
          Automated Tunisian real estate legal compliance checking using RAG over the CDR corpus,
          CATU verification, and ML-powered legal risk scoring.
        </p>
        <div style={{display:"flex",gap:12,justifyContent:"center",flexWrap:"wrap",marginBottom:32}}>
          {["CDR Parser","CATU Checker","Legal RAG","Risk ML","Doc Verification","Notary Reports"].map(tag=>(
            <span key={tag} style={{background:"rgba(47,156,126,.1)",color:"var(--green)",borderRadius:999,padding:"6px 14px",fontSize:12,fontWeight:700,border:"1px solid rgba(47,156,126,.25)"}}>
              {tag}
            </span>
          ))}
        </div>
      </div>

      {/* Features grid */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:16}}>
        {FEATURES.map(f=>(
          <div key={f.title} className="panel" style={{padding:24,opacity:.85}}>
            <div style={{fontSize:32,marginBottom:14}}>{f.icon}</div>
            <h3 style={{fontSize:15,fontWeight:700,color:"var(--navy)",marginBottom:8}}>{f.title}</h3>
            <p style={{fontSize:13,color:"var(--mut)",lineHeight:1.7}}>{f.desc}</p>
          </div>
        ))}
      </div>

      {/* Legal framework covered */}
      <div className="panel" style={{padding:24}}>
        <div style={{fontSize:14,fontWeight:700,color:"var(--navy)",marginBottom:16}}>Legal Framework Covered</div>
        <div style={{display:"grid",gridTemplateColumns:"repeat(2,1fr)",gap:12}}>
          {[
            {code:"CDR Art. 4-17",title:"Property ownership & transfer",status:"Integrated"},
            {code:"CDR Art. 89-102",title:"Mortgage & collateral law",status:"Integrated"},
            {code:"CDR Art. 145-178",title:"Servitude & easements",status:"In progress"},
            {code:"CATU Reference",title:"Cadastral title verification",status:"In progress"},
            {code:"LOI 2001-92",title:"Real estate agency regulations",status:"Planned"},
            {code:"LOI 2016-71",title:"Investment incentives",status:"Planned"},
          ].map(item=>(
            <div key={item.code} style={{display:"flex",alignItems:"center",gap:12,padding:"12px 14px",background:"rgba(7,29,51,.03)",borderRadius:10,border:"1px solid var(--line)"}}>
              <div style={{flex:1}}>
                <div style={{fontSize:12,fontWeight:700,color:"var(--navy)",marginBottom:1}}>{item.code}</div>
                <div style={{fontSize:11,color:"var(--mut)"}}>{item.title}</div>
              </div>
              <span style={{
                fontSize:10,fontWeight:700,padding:"3px 10px",borderRadius:999,
                background:item.status==="Integrated"?"rgba(35,135,101,.1)":item.status==="In progress"?"rgba(191,118,24,.1)":"rgba(7,29,51,.06)",
                color:item.status==="Integrated"?"var(--ok)":item.status==="In progress"?"var(--warn)":"var(--mut)",
                border:`1px solid ${item.status==="Integrated"?"rgba(35,135,101,.3)":item.status==="In progress"?"rgba(191,118,24,.3)":"var(--line)"}`,
              }}>
                {item.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
