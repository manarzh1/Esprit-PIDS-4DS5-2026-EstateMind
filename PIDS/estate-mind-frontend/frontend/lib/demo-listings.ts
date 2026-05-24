/* ══════════════════════════════════════════════════════════════════
   65 realistic Tunisian real estate listings
   Used by: SearchSection, OpportunitiesSection, PortfolioSection
   ══════════════════════════════════════════════════════════════════ */

export interface Listing {
  id: number;
  title: string;
  city: string;
  region: string;
  property_type: string;
  price: number;
  surface: number;
  price_per_m2: number;
  trust_score: number;
  trust_level: string;
  legal_risk_score: number;
  url: string;
  source: string;
  description: string;
  days_on_market: number;
  initial_price?: number;
}

function mk(id:number, title:string, city:string, region:string, type:string,
             price:number, surface:number, trust:number, legal:number,
             source:string, desc:string, days:number=45, initial?:number): Listing {
  const ppm2 = Math.round(price / surface);
  const tl = trust>=.75?"Reliable":trust>=.5?"Moderate":"Suspect";
  return {id,title,city,region,property_type:type,price,surface,price_per_m2:ppm2,
          trust_score:trust,trust_level:tl,legal_risk_score:legal,
          url:"#",source,description:desc,days_on_market:days,
          initial_price:initial||undefined};
}

export const DEMO_LISTINGS: Listing[] = [
  // ── Tunis ────────────────────────────────────────────────────────────
  mk(1, "S+3 Belvédère 115m² rénové",        "Tunis","North-East","apartment",  330000,115,.83,.14,"tayara",   "Bel appartement rénové, 3ème étage, ascenseur, parking.",52),
  mk(2, "S+2 Lac 2 avec terrasse",            "Tunis","North-East","apartment",  285000,95, .77,.19,"mubawab",  "Résidence sécurisée Lac 2, vue dégagée, parking.",       38),
  mk(3, "Studio meublé Centre Ville",         "Tunis","North-East","studio",     130000,48, .91,.09,"remax",    "Studio entièrement équipé, acte notarié.",               21),
  mk(4, "S+4 Ennasr 180m²",                  "Tunis","North-East","apartment",  480000,180,.68,.28,"tecnocasa","Grand appart familial, jardin commun, 2 parkings.",      63),
  mk(5, "Local commercial Bab Bhar 90m²",     "Tunis","North-East","commercial", 380000,90, .61,.42,"tayara",   "Rez-de-chaussée, fort passage piéton, bail actif.",      95),
  mk(6, "S+1 Menzah 6 65m²",                 "Tunis","North-East","apartment",  195000,65, .84,.12,"mubawab",  "Appartement calme, lumineux, proche mosquée.",           17),
  mk(7, "Villa R+1 Mutuelleville",            "Tunis","North-East","villa",      820000,260,.72,.21,"century21","Villa cossue, piscine, jardin 400m², garage 2 voitures.", 88, 860000),
  mk(8, "S+3 Menzah 9 rénovation récente",   "Tunis","North-East","apartment",  345000,120,.79,.16,"remax",    "Rénové 2025, ascenseur, gardien.",                       29),

  // ── La Marsa ─────────────────────────────────────────────────────────
  mk(9,  "S+3 La Marsa Plage 120m²",         "La Marsa","North-East","apartment", 520000,120,.86,.11,"tayara",   "Vue mer partielle, 200m plage, titre foncier.",          34),
  mk(10, "Villa S+4 bord de mer",             "La Marsa","North-East","villa",    1250000,280,.78,.18,"sothebys", "Accès direct plage, piscine, jardin 600m².",             72, 1300000),
  mk(11, "S+2 La Marsa Centre 95m²",          "La Marsa","North-East","apartment", 380000,95, .81,.15,"mubawab",  "2ème étage, balcon, vue mer lointaine.",                 41),
  mk(12, "Terrain constructible 500m²",       "La Marsa","North-East","land",      620000,500,.62,.39,"tayara",   "Zone villa, eau+électricité, plan masse fourni.",        128,660000),

  // ── Ariana ───────────────────────────────────────────────────────────
  mk(13, "S+3 Ariana Soghra 110m²",          "Ariana","North-East","apartment", 295000,110,.74,.22,"mubawab",  "Résidence clôturée, ascenseur, parking sous-sol.",       45),
  mk(14, "S+2 Riadh Andalous 88m²",          "Ariana","North-East","apartment", 245000,88, .82,.13,"tayara",   "Bel appart, fenêtres double vitrage, cuisine équipée.",  28),
  mk(15, "Villa S+3 Ariana Ville",           "Ariana","North-East","villa",      595000,210,.69,.29,"century21","Maison familiale avec jardin, puits.",                   67, 615000),
  mk(16, "Local + appartement duplex",       "Ariana","North-East","commercial", 420000,160,.55,.44,"tayara",   "Mixte commerce + logement, rentabilité 6%.",             82),

  // ── Ben Arous ────────────────────────────────────────────────────────
  mk(17, "S+2 Ezzahra 85m²",                "Ben Arous","North-East","apartment", 198000,85, .77,.19,"mubawab",  "Proche Centre comm., parking visiteurs.",                33),
  mk(18, "Maison R+1 Mégrine 140m²",        "Ben Arous","North-East","house",     285000,140,.65,.33,"tayara",   "Maison plain-pied + étage, jardin 120m².",              54),
  mk(19, "S+1 Borj Cedria vue mer",         "Ben Arous","North-East","apartment", 155000,62, .71,.25,"remax",    "Balcon avec vue sur le golfe.",                          37),

  // ── Hammamet ─────────────────────────────────────────────────────────
  mk(20, "Villa S+4 Hammamet Nord piscine",  "Hammamet","North-East","villa",     680000,240,.79,.18,"mubawab",  "Piscine privée, jardin 800m², titre foncier.",           55, 720000),
  mk(21, "S+3 Hammamet Plage 130m²",        "Hammamet","North-East","apartment", 450000,130,.83,.13,"tayara",   "Vue mer, résidence gardée, 2 parkings.",                 42),
  mk(22, "Villa S+3 Yasmine Hammamet",      "Hammamet","North-East","villa",      920000,320,.76,.20,"sothebys", "Zone touristique, rentabilité saisonnière prouvée.",     89, 950000),
  mk(23, "Terrain 800m² zone villa",        "Hammamet","North-East","land",       380000,800,.57,.41,"tayara",   "Permis de construire obtenu.",                           115,400000),
  mk(24, "S+2 résidence Manar 90m²",        "Hammamet","North-East","apartment", 265000,90, .81,.16,"mubawab",  "Piscine commune, à 500m de la plage.",                   30),

  // ── Nabeul ───────────────────────────────────────────────────────────
  mk(25, "S+3 Nabeul Centre 105m²",         "Nabeul","North-East","apartment",  235000,105,.69,.28,"tayara",   "3ème étage, ascenseur, proche commerces.",               48),
  mk(26, "Terrain zone urbaine 400m²",      "Nabeul","North-East","land",        95000,400,.31,.72,"tayara",   "Situation irrégulière à vérifier.",                      212, 112000),
  mk(27, "Villa S+3 Nabeul résid. fermée",  "Nabeul","North-East","villa",      480000,195,.77,.19,"mubawab",  "Résidence sécurisée, piscine partagée.",                 58),
  mk(28, "S+1 Nabeul vue mer 70m²",        "Nabeul","North-East","apartment",  185000,70, .73,.23,"remax",    "Balcon, 300m de la plage.",                              35),
  mk(29, "Ferme 5000m² oliviers",           "Nabeul","North","land",             220000,5000,.44,.55,"tayara",  "Titre agricole, 200 oliviers.",                          160),

  // ── Sousse ───────────────────────────────────────────────────────────
  mk(30, "S+3 Sousse Khezama 115m²",       "Sousse","Centre-East","apartment",  280000,115,.78,.18,"mubawab",  "Résidence sécurisée, piscine, parking.",                 39),
  mk(31, "S+2 Port El Kantaoui vue mer",   "Sousse","Centre-East","apartment",  320000,100,.82,.14,"tayara",   "Vue mer directe, meublé, locatif rentable.",             26),
  mk(32, "Villa S+4 Sousse Nord",          "Sousse","Centre-East","villa",      650000,230,.74,.22,"century21","Villa contemporaine, domotique, piscine chauffée.",      77, 680000),
  mk(33, "S+1 Sahloul 68m²",              "Sousse","Centre-East","apartment",  175000,68, .86,.11,"remax",    "Proche hôpital Sahloul, acte notarié.",                  22),
  mk(34, "Studio résidence balnéaire",     "Sousse","Centre-East","studio",     145000,45, .79,.17,"mubawab",  "Rentabilité locative été prouvée.",                      31),
  mk(35, "Local commercial Sousse Ville",  "Sousse","Centre-East","commercial", 290000,80, .63,.38,"tayara",   "Rue commerçante, clientèle assurée.",                    93, 310000),

  // ── Monastir ─────────────────────────────────────────────────────────
  mk(36, "S+3 Monastir Marina 120m²",     "Monastir","Centre-East","apartment", 320000,120,.82,.14,"mubawab",  "Vue sur la marina, résidence haut standing.",            35),
  mk(37, "Villa S+3 Monastir Ksibet",     "Monastir","Centre-East","villa",      520000,200,.71,.25,"tayara",   "Terrain 500m², jardin mature.",                          68, 540000),
  mk(38, "S+2 Skanes vue mer 95m²",      "Monastir","Centre-East","apartment",  265000,95, .76,.21,"remax",    "Proche aéroport, 400m plage.",                           40),
  mk(39, "Terrain Monastir zone C 600m²", "Monastir","Centre-East","land",       165000,600,.58,.40,"tayara",   "Zone constructible C, all utilities.",                   88),

  // ── Sfax ─────────────────────────────────────────────────────────────
  mk(40, "S+3 Sfax Centre 115m²",        "Sfax","Centre-East","apartment",    220000,115,.72,.24,"mubawab",   "Proche tribunal, état général bon.",                    44),
  mk(41, "Local commercial Sfax 180m²",  "Sfax","Centre-East","commercial",   380000,180,.61,.43,"tayara",    "Forte visibilité, loyer actuel 2.800 TND/mois.",        122, 400000),
  mk(42, "Villa R+1 Sfax El Ain",        "Sfax","Centre-East","villa",         445000,190,.75,.21,"century21", "Quartier résidentiel calme, jardin.",                    57),
  mk(43, "S+2 Thyna 88m²",              "Sfax","Centre-East","apartment",    180000,88, .67,.31,"tayara",    "Immeuble 2018, ascenseur.",                              49),
  mk(44, "Entrepôt zone industrielle",   "Sfax","Centre-East","commercial",   550000,800,.52,.47,"mubawab",   "Zone logistique, accès semi-remorque.",                 134),

  // ── Bizerte ──────────────────────────────────────────────────────────
  mk(45, "S+2 Bizerte Bord Lac 88m²",   "Bizerte","North","apartment",       195000,88, .78,.18,"mubawab",   "Vue lac, parking, 3ème étage.",                         36),
  mk(46, "Maison R+1 El Aïn 140m²",    "Bizerte","North","house",            255000,140,.66,.32,"tayara",    "Grande terrasse, jardin 180m².",                        62),
  mk(47, "Terrain plage Ras Jebel 1000m²","Bizerte","North","land",          180000,1000,.43,.56,"tayara",   "Accès direct plage, titre foncier.",                    190, 210000),
  mk(48, "S+3 Bizerte Centre 110m²",   "Bizerte","North","apartment",        225000,110,.71,.25,"remax",     "Rénové 2024, double vitrage.",                          44),

  // ── Mahdia ───────────────────────────────────────────────────────────
  mk(49, "Villa S+3 Mahdia bord mer",   "Mahdia","Centre-East","villa",        490000,210,.73,.23,"mubawab",   "Accès direct plage privée.",                            51, 515000),
  mk(50, "S+2 Mahdia Centre 92m²",     "Mahdia","Centre-East","apartment",    185000,92, .76,.20,"tayara",    "Proche marché, état correct.",                          38),
  mk(51, "Terrain zone villa 700m²",   "Mahdia","Centre-East","land",         155000,700,.59,.39,"mubawab",   "Zone R+2 autorisée, plan cadastral fourni.",             72),

  // ── Kairouan ─────────────────────────────────────────────────────────
  mk(52, "S+3 Kairouan Médina 105m²",  "Kairouan","Centre","apartment",       135000,105,.65,.33,"tayara",    "Proche Grande Mosquée, rénové.",                        58),
  mk(53, "Maison traditionnelle 200m²","Kairouan","Centre","house",            195000,200,.59,.40,"mubawab",   "Maison de caractère, patio intérieur.",                 105, 210000),

  // ── Gabès ────────────────────────────────────────────────────────────
  mk(54, "S+3 Gabès Centre 110m²",     "Gabès","South","apartment",           155000,110,.71,.26,"tayara",    "Bon état, proche services.",                            47),
  mk(55, "Villa S+2 Gabès Jara",       "Gabès","South","villa",               285000,160,.67,.31,"mubawab",   "Jardin 300m², quartier résidentiel.",                   69, 295000),

  // ── Médenine / Sud ───────────────────────────────────────────────────
  mk(56, "S+2 Djerba Midoun 95m²",    "Médenine","South","apartment",         225000,95, .74,.23,"tayara",    "Style traditionnel, Djerba, investissement touristique.", 53),
  mk(57, "Villa S+3 Djerba Houmt Souk","Médenine","South","villa",             420000,195,.71,.26,"mubawab",   "Piscine, 200m de la plage, rentabilité saisonnière.",    66, 445000),

  // ── Zaghouan / Siliana ───────────────────────────────────────────────
  mk(58, "Ferme 12 ha Zaghouan",       "Zaghouan","North","land",              380000,12000,.46,.52,"tayara",  "Titre agricole, irrigation, source naturelle.",          145),
  mk(59, "Maison campagne Siliana",    "Siliana","North-West","house",           88000,120,.58,.41,"tayara",   "Vue montagne, terrain attenant 2000m².",                 120),

  // ── Le Kef / Jendouba ────────────────────────────────────────────────
  mk(60, "S+2 Le Kef 85m²",          "Le Kef","North-West","apartment",        65000,85, .69,.28,"tayara",   "Centre-ville, bon état.",                               51),
  mk(61, "Terrain Le Kef zone C",     "Le Kef","North-West","land",             35000,400,.52,.46,"mubawab",  "Constructible, tout à pied.",                            78),

  // ── Gafsa / Tozeur ───────────────────────────────────────────────────
  mk(62, "Villa oasis Tozeur 180m²",  "Tozeur","South-West","villa",           280000,180,.68,.30,"tayara",   "Palmiers, piscine, rentabilité touristique forte.",      60),
  mk(63, "S+2 Gafsa Centre",         "Gafsa","South-West","apartment",         78000,88, .64,.34,"tayara",   "Proche université, demande locative stable.",            72),

  // ── Manouba ──────────────────────────────────────────────────────────
  mk(64, "S+3 Manouba 115m²",        "Manouba","North-East","apartment",      235000,115,.76,.21,"tayara",   "Proche RFM, quartier tranquille.",                      40),
  mk(65, "Villa S+4 Oued Ellil",     "Manouba","North-East","villa",          520000,220,.73,.24,"mubawab",  "Quartier résidentiel, garage 2 voitures.",              65, 545000),
];

/* ── Compute drops (listings with initial_price > current) ─────── */
export const DEMO_DROPS = DEMO_LISTINGS
  .filter(l => l.initial_price && l.initial_price > l.price)
  .map(l => ({
    ...l,
    initial_price: l.initial_price!,
    drop_pct:    parseFloat(((l.initial_price! - l.price) / l.initial_price! * 100).toFixed(1)),
    drop_amount: l.initial_price! - l.price,
  }))
  .sort((a,b) => b.drop_pct - a.drop_pct);

/* ── Rental yield by city (static market data) ──────────────────── */
export const DEMO_YIELD = [
  {city:"Tunis",    property_type:"apartment",median_rent:950, median_sale_price:295000,yield_brut_pct:3.86,yield_net_pct:2.89,verdict:"correct"},
  {city:"La Marsa", property_type:"apartment",median_rent:1100,median_sale_price:450000,yield_brut_pct:2.93,yield_net_pct:2.20,verdict:"low"},
  {city:"Hammamet", property_type:"villa",    median_rent:2200,median_sale_price:680000,yield_brut_pct:3.88,yield_net_pct:2.91,verdict:"correct"},
  {city:"Sousse",   property_type:"apartment",median_rent:820, median_sale_price:235000,yield_brut_pct:4.18,yield_net_pct:3.14,verdict:"correct"},
  {city:"Monastir", property_type:"apartment",median_rent:720, median_sale_price:210000,yield_brut_pct:4.11,yield_net_pct:3.09,verdict:"correct"},
  {city:"Nabeul",   property_type:"apartment",median_rent:680, median_sale_price:200000,yield_brut_pct:4.08,yield_net_pct:3.06,verdict:"correct"},
  {city:"Sfax",     property_type:"apartment",median_rent:590, median_sale_price:165000,yield_brut_pct:4.29,yield_net_pct:3.22,verdict:"correct"},
  {city:"Bizerte",  property_type:"apartment",median_rent:520, median_sale_price:185000,yield_brut_pct:3.37,yield_net_pct:2.53,verdict:"low"},
  {city:"Mahdia",   property_type:"villa",    median_rent:1400,median_sale_price:490000,yield_brut_pct:3.43,yield_net_pct:2.57,verdict:"low"},
  {city:"Tozeur",   property_type:"villa",    median_rent:1800,median_sale_price:280000,yield_brut_pct:7.71,yield_net_pct:5.79,verdict:"excellent"},
  {city:"Djerba",   property_type:"villa",    median_rent:2800,median_sale_price:420000,yield_brut_pct:8.00,yield_net_pct:6.00,verdict:"excellent"},
];

/* ── Market overview by city ────────────────────────────────────── */
export const DEMO_MARKET = {
  total: DEMO_LISTINGS.length,
  median_ppm2: 2700,
  top_city: "La Marsa",
  cities: [
    {city:"La Marsa", ppm2:4650,n:4,  median:4650,mean:4900},
    {city:"Hammamet", ppm2:3820,n:5,  median:3820,mean:4100},
    {city:"Tunis",    ppm2:3150,n:8,  median:3150,mean:3300},
    {city:"Sousse",   ppm2:2780,n:6,  median:2780,mean:2950},
    {city:"Monastir", ppm2:2620,n:4,  median:2620,mean:2750},
    {city:"Nabeul",   ppm2:2450,n:5,  median:2450,mean:2600},
    {city:"Sfax",     ppm2:2100,n:5,  median:2100,mean:2280},
    {city:"Bizerte",  ppm2:1870,n:4,  median:1870,mean:2000},
    {city:"Mahdia",   ppm2:1780,n:3,  median:1780,mean:1900},
    {city:"Ariana",   ppm2:2620,n:4,  median:2620,mean:2750},
    {city:"Ben Arous",ppm2:2150,n:3,  median:2150,mean:2280},
    {city:"Manouba",  ppm2:2120,n:2,  median:2120,mean:2200},
    {city:"Kairouan", ppm2:1280,n:2,  median:1280,mean:1350},
    {city:"Gabès",    ppm2:1320,n:2,  median:1320,mean:1400},
    {city:"Tozeur",   ppm2:1560,n:1,  median:1560,mean:1560},
  ],
};

export function filterListings(
  listings: Listing[], q="", city="", property_type="",
  price_min="", price_max="", surface_min="", trust_min="0", sort="trust_score"
): Listing[] {
  let res = [...listings];
  const ql = q.toLowerCase().trim();
  if (ql)          res = res.filter(r=>r.title.toLowerCase().includes(ql)||r.city.toLowerCase().includes(ql)||r.property_type.includes(ql)||r.description?.toLowerCase().includes(ql));
  if (city)        res = res.filter(r=>r.city.toLowerCase().includes(city.toLowerCase().trim()));
  if (property_type) res = res.filter(r=>r.property_type===property_type);
  if (price_min)   res = res.filter(r=>r.price>=Number(price_min));
  if (price_max)   res = res.filter(r=>r.price<=Number(price_max));
  if (surface_min) res = res.filter(r=>r.surface>=Number(surface_min));
  if (trust_min&&trust_min!=="0") res = res.filter(r=>r.trust_score>=Number(trust_min));
  if (sort==="price_asc")  res.sort((a,b)=>a.price-b.price);
  else if (sort==="price_desc") res.sort((a,b)=>b.price-a.price);
  else                     res.sort((a,b)=>b.trust_score-a.trust_score);
  return res;
}
