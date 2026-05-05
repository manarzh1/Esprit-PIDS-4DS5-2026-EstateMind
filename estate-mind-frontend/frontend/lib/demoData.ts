/* ================================================================
   Estate Mind — Demo Data (used when API is not reachable)
   40 realistic Tunisian real estate listings
   ================================================================ */

export interface Listing {
  id:number; title:string; city:string; property_type:string;
  price:number; surface:number; price_per_m2:number;
  trust_score:number; trust_level:string; legal_risk_score:number;
  url:string; source:string; description?:string;
}

export const ALL_LISTINGS: Listing[] = [
  // ── LA MARSA ────────────────────────────────────────────────────
  {id:1, title:"Apartment S+3 La Marsa 120m²",     city:"La Marsa", property_type:"apartment",price:315000,surface:120,price_per_m2:2625,trust_score:.84,trust_level:"Reliable", legal_risk_score:.12,url:"#",source:"tayara",   description:"Renovated apartment, notarized deed, sea view."},
  {id:2, title:"Villa S+4 La Marsa piscine 300m²",  city:"La Marsa", property_type:"villa",    price:850000,surface:300,price_per_m2:2833,trust_score:.79,trust_level:"Reliable", legal_risk_score:.15,url:"#",source:"mubawab",  description:"Luxurious villa with pool, 5 min from beach."},
  {id:3, title:"Studio meublé La Marsa 48m²",       city:"La Marsa", property_type:"studio",   price:145000,surface:48, price_per_m2:3021,trust_score:.91,trust_level:"Reliable", legal_risk_score:.08,url:"#",source:"remax",    description:"Fully furnished studio, notarized deed."},
  // ── HAMMAMET ────────────────────────────────────────────────────
  {id:4, title:"Villa S+4 Hammamet Nord piscine",   city:"Hammamet", property_type:"villa",    price:520000,surface:240,price_per_m2:2167,trust_score:.77,trust_level:"Reliable", legal_risk_score:.18,url:"#",source:"mubawab",  description:"Large villa with pool, title deed."},
  {id:5, title:"Appartement S+2 Hammamet Sud 90m²", city:"Hammamet", property_type:"apartment",price:195000,surface:90, price_per_m2:2167,trust_score:.68,trust_level:"Moderate", legal_risk_score:.31,url:"#",source:"tayara",   description:"Close to the beach, renovated."},
  {id:6, title:"Villa R+1 Hammamet 180m² jardin",   city:"Hammamet", property_type:"villa",    price:380000,surface:180,price_per_m2:2111,trust_score:.82,trust_level:"Reliable", legal_risk_score:.14,url:"#",source:"tecnocasa",description:"Beautiful garden, title deed, quiet area."},
  {id:7, title:"Terrain 500m² Hammamet constructible",city:"Hammamet",property_type:"land",   price:110000,surface:500,price_per_m2:220, trust_score:.45,trust_level:"Moderate", legal_risk_score:.52,url:"#",source:"tayara",   description:"Buildable land near highway."},
  // ── TUNIS ───────────────────────────────────────────────────────
  {id:8, title:"Studio meublé Centre Tunis 52m²",   city:"Tunis",    property_type:"studio",   price:130000,surface:52, price_per_m2:2500,trust_score:.91,trust_level:"Reliable", legal_risk_score:.09,url:"#",source:"remax",    description:"Equipped studio, notarized deed."},
  {id:9, title:"Appartement S+2 Lac 1 95m²",        city:"Tunis",    property_type:"apartment",price:280000,surface:95, price_per_m2:2947,trust_score:.76,trust_level:"Reliable", legal_risk_score:.19,url:"#",source:"century21",description:"Lac 1 district, excellent condition."},
  {id:10,title:"Appartement S+3 Menzah 130m²",      city:"Tunis",    property_type:"apartment",price:320000,surface:130,price_per_m2:2462,trust_score:.88,trust_level:"Reliable", legal_risk_score:.11,url:"#",source:"tecnocasa",description:"High floor, panoramic view, parking."},
  {id:11,title:"Local commercial Tunis centre 80m²", city:"Tunis",    property_type:"commercial",price:250000,surface:80,price_per_m2:3125,trust_score:.62,trust_level:"Moderate", legal_risk_score:.41,url:"#",source:"mubawab", description:"Great location, high foot traffic."},
  {id:12,title:"Terrain Tunis Nord 300m² viabilisé", city:"Tunis",    property_type:"land",    price:180000,surface:300,price_per_m2:600, trust_score:.55,trust_level:"Moderate", legal_risk_score:.48,url:"#",source:"tayara",   description:"Utility-connected land, quiet neighborhood."},
  // ── SOUSSE ──────────────────────────────────────────────────────
  {id:13,title:"Appartement S+2 Sousse vue mer 95m²",city:"Sousse",  property_type:"apartment",price:215000,surface:95, price_per_m2:2263,trust_score:.72,trust_level:"Moderate", legal_risk_score:.28,url:"#",source:"tecnocasa",description:"200m from beach, well located."},
  {id:14,title:"Villa S+3 Sousse 200m² piscine",     city:"Sousse",  property_type:"villa",    price:450000,surface:200,price_per_m2:2250,trust_score:.81,trust_level:"Reliable", legal_risk_score:.16,url:"#",source:"remax",    description:"Large pool, quiet, title deed."},
  {id:15,title:"Studio Sousse bord de mer 45m²",     city:"Sousse",  property_type:"studio",   price:95000, surface:45, price_per_m2:2111,trust_score:.66,trust_level:"Moderate", legal_risk_score:.35,url:"#",source:"tayara",   description:"Sea view, ground floor."},
  {id:16,title:"Appartement S+1 Sahloul 72m²",       city:"Sousse",  property_type:"apartment",price:155000,surface:72, price_per_m2:2153,trust_score:.78,trust_level:"Reliable", legal_risk_score:.22,url:"#",source:"mubawab",  description:"Secure residence, parking."},
  // ── NABEUL ──────────────────────────────────────────────────────
  {id:17,title:"Terrain 400m² Nabeul zone urbaine",  city:"Nabeul",  property_type:"land",     price:95000, surface:400,price_per_m2:237, trust_score:.31,trust_level:"Suspect",  legal_risk_score:.72,url:"#",source:"tayara",   description:"Buildable land, irregular situation."},
  {id:18,title:"Villa S+3 Nabeul 160m² jardin",      city:"Nabeul",  property_type:"villa",    price:295000,surface:160,price_per_m2:1844,trust_score:.74,trust_level:"Reliable", legal_risk_score:.24,url:"#",source:"mubawab",  description:"Large garden, quiet street."},
  {id:19,title:"Appartement S+2 Nabeul 85m²",        city:"Nabeul",  property_type:"apartment",price:165000,surface:85, price_per_m2:1941,trust_score:.69,trust_level:"Moderate", legal_risk_score:.32,url:"#",source:"tecnocasa",description:"Central location, 10 min from beach."},
  {id:20,title:"Terrain agricole Nabeul 1200m²",     city:"Nabeul",  property_type:"land",     price:72000, surface:1200,price_per_m2:60,  trust_score:.22,trust_level:"Suspect",  legal_risk_score:.81,url:"#",source:"tayara",   description:"Agricultural use, documentation incomplete."},
  // ── SFAX ────────────────────────────────────────────────────────
  {id:21,title:"Local commercial Sfax centre 180m²", city:"Sfax",    property_type:"commercial",price:320000,surface:180,price_per_m2:1778,trust_score:.61,trust_level:"Moderate", legal_risk_score:.43,url:"#",source:"tayara",   description:"Storefront, high foot traffic."},
  {id:22,title:"Appartement S+3 Sfax 120m²",         city:"Sfax",    property_type:"apartment",price:190000,surface:120,price_per_m2:1583,trust_score:.73,trust_level:"Reliable", legal_risk_score:.25,url:"#",source:"mubawab",  description:"High floor, panoramic view."},
  {id:23,title:"Maison R+1 Sfax 140m² jardin",       city:"Sfax",    property_type:"house",    price:235000,surface:140,price_per_m2:1679,trust_score:.80,trust_level:"Reliable", legal_risk_score:.17,url:"#",source:"century21",description:"Large garden, renovated, title deed."},
  {id:24,title:"Villa Sfax route Tunis 220m²",        city:"Sfax",    property_type:"villa",    price:380000,surface:220,price_per_m2:1727,trust_score:.71,trust_level:"Reliable", legal_risk_score:.27,url:"#",source:"remax",    description:"Main road, easy access."},
  // ── BIZERTE ─────────────────────────────────────────────────────
  {id:25,title:"Maison R+1 Bizerte 140m²",            city:"Bizerte", property_type:"house",    price:195000,surface:140,price_per_m2:1393,trust_score:.69,trust_level:"Moderate", legal_risk_score:.33,url:"#",source:"mubawab",  description:"Family house, large garden."},
  {id:26,title:"Appartement S+2 Bizerte 88m²",        city:"Bizerte", property_type:"apartment",price:135000,surface:88, price_per_m2:1534,trust_score:.74,trust_level:"Reliable", legal_risk_score:.23,url:"#",source:"tayara",   description:"City centre, good condition."},
  // ── MONASTIR ────────────────────────────────────────────────────
  {id:27,title:"Appartement S+2 Monastir 90m²",       city:"Monastir",property_type:"apartment",price:210000,surface:90, price_per_m2:2333,trust_score:.82,trust_level:"Reliable", legal_risk_score:.14,url:"#",source:"tecnocasa",description:"Secure residence, parking."},
  {id:28,title:"Villa S+3 Monastir 170m² piscine",    city:"Monastir",property_type:"villa",    price:395000,surface:170,price_per_m2:2324,trust_score:.77,trust_level:"Reliable", legal_risk_score:.21,url:"#",source:"mubawab",  description:"Pool, garden, 5 min from airport."},
  // ── ARIANA ──────────────────────────────────────────────────────
  {id:29,title:"Appartement S+2 Ariana 95m²",         city:"Ariana",  property_type:"apartment",price:235000,surface:95, price_per_m2:2474,trust_score:.85,trust_level:"Reliable", legal_risk_score:.13,url:"#",source:"remax",    description:"Modern building, parking, secure."},
  {id:30,title:"Appartement S+3 Ariana Sup 125m²",    city:"Ariana",  property_type:"apartment",price:295000,surface:125,price_per_m2:2360,trust_score:.76,trust_level:"Reliable", legal_risk_score:.20,url:"#",source:"century21",description:"High floor, balcony, panoramic view."},
  {id:31,title:"Villa R+1 Ariana 190m²",               city:"Ariana",  property_type:"villa",    price:420000,surface:190,price_per_m2:2211,trust_score:.83,trust_level:"Reliable", legal_risk_score:.15,url:"#",source:"tecnocasa",description:"Quiet street, large garden, title deed."},
  // ── MAHDIA ──────────────────────────────────────────────────────
  {id:32,title:"Villa S+3 Mahdia bord de mer 180m²", city:"Mahdia",  property_type:"villa",    price:290000,surface:180,price_per_m2:1611,trust_score:.71,trust_level:"Reliable", legal_risk_score:.26,url:"#",source:"mubawab",  description:"Sea view, private beach access."},
  {id:33,title:"Appartement S+1 Mahdia 70m²",         city:"Mahdia",  property_type:"apartment",price:110000,surface:70, price_per_m2:1571,trust_score:.65,trust_level:"Moderate", legal_risk_score:.37,url:"#",source:"tayara",   description:"Coastal city, quiet area."},
  // ── GAFSA / KAIROUAN ────────────────────────────────────────────
  {id:34,title:"Maison Kairouan 120m² jardin",         city:"Kairouan",property_type:"house",    price:85000, surface:120,price_per_m2:708, trust_score:.62,trust_level:"Moderate", legal_risk_score:.40,url:"#",source:"tayara",   description:"Traditional house, large courtyard."},
  {id:35,title:"Terrain Kairouan 600m²",               city:"Kairouan",property_type:"land",     price:38000, surface:600,price_per_m2:63,  trust_score:.38,trust_level:"Suspect",  legal_risk_score:.65,url:"#",source:"tayara",   description:"Rural land, limited documentation."},
  // ── BEN AROUS ───────────────────────────────────────────────────
  {id:36,title:"Appartement S+3 Ben Arous 110m²",     city:"Ben Arous",property_type:"apartment",price:225000,surface:110,price_per_m2:2045,trust_score:.79,trust_level:"Reliable", legal_risk_score:.19,url:"#",source:"mubawab",  description:"Near metro, well maintained."},
  {id:37,title:"Maison R+1 Ben Arous 130m²",           city:"Ben Arous",property_type:"house",    price:195000,surface:130,price_per_m2:1500,trust_score:.72,trust_level:"Reliable", legal_risk_score:.26,url:"#",source:"tecnocasa",description:"Family home, quiet neighborhood."},
  // ── MANOUBA ─────────────────────────────────────────────────────
  {id:38,title:"Villa Manouba 200m² piscine",          city:"Manouba", property_type:"villa",    price:360000,surface:200,price_per_m2:1800,trust_score:.76,trust_level:"Reliable", legal_risk_score:.22,url:"#",source:"remax",    description:"Pool, garden, quiet area."},
  // ── GABES / MEDENINE ────────────────────────────────────────────
  {id:39,title:"Villa Médenine 150m² avec jardin",     city:"Médenine",property_type:"villa",    price:175000,surface:150,price_per_m2:1167,trust_score:.58,trust_level:"Moderate", legal_risk_score:.45,url:"#",source:"tayara",   description:"Large garden, quiet, accessible."},
  {id:40,title:"Appartement S+2 Gabès 80m²",           city:"Gabès",   property_type:"apartment",price:95000, surface:80, price_per_m2:1188,trust_score:.64,trust_level:"Moderate", legal_risk_score:.38,url:"#",source:"mubawab",  description:"City centre, needs renovation."},
  // ── ZAGHOUAN / ZAGHOUAN ─────────────────────────────────────────
  {id:41,title:"Terrain agricole Zaghouan 2000m²",     city:"Zaghouan",property_type:"land",     price:45000, surface:2000,price_per_m2:22,  trust_score:.28,trust_level:"Suspect",  legal_risk_score:.74,url:"#",source:"tayara",   description:"Agricultural land, incomplete paperwork."},
  {id:42,title:"Maison Zaghouan 110m² cachet",         city:"Zaghouan",property_type:"house",    price:120000,surface:110,price_per_m2:1091,trust_score:.67,trust_level:"Moderate", legal_risk_score:.34,url:"#",source:"mubawab",  description:"Character home, mountain views."},
];

/* ─── Derived subsets ─────────────────────────────────────────── */
export const DEMO_DROPS = {
  drops: ALL_LISTINGS
    .filter(l=>l.trust_score>=.5)
    .slice(0,12)
    .map((l,i)=>{
      const pcts=[5.9,8.7,10.3,7.2,12.1,6.4,9.8,15.2,8.5,11.3,7.6,13.4];
      const pct=pcts[i]||7.0;
      const initial=Math.round(l.price/(1-pct/100));
      return {...l,initial_price:initial,current_price:l.price,drop_pct:pct,drop_amount:initial-l.price};
    }),
  total:12, avg_drop_pct:9.4, max_drop_pct:15.2,
};

export const DEMO_NEGO = ALL_LISTINGS
  .filter(l=>l.trust_score>=.4)
  .slice(0,10)
  .map((l,i)=>{
    const days=[87,134,212,95,156,78,203,110,145,67];
    const scores=[.72,.88,.94,.68,.82,.65,.79,.86,.71,.90];
    const reds=[10.8,13.2,14.1,10.2,12.3,9.8,13.8,11.5,10.9,14.6];
    const types=["private","private","info_agency","private","active_reseller","private","private","info_agency","active_reseller","private"];
    return {...l,days_on_market:days[i]||90,negociation_score:scores[i]||.7,
      estimated_reduction_pct:reds[i]||10,seller_type:types[i]||"private"};
  });
