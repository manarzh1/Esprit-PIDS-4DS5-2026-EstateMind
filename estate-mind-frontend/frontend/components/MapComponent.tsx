"use client";

import { useEffect, useRef, useState } from "react";

// ── Données statiques 24 gouvernorats (fallback si API indisponible) ──────────
export const GOUVERNORATS = [
  { name:"Tunis",       lat:36.8065, lng:10.1815, ppm2:3200, listings:2341, region:"Nord-Est",    median:280000, top_type:"appartement" },
  { name:"Ariana",      lat:36.8663, lng:10.1647, ppm2:2900, listings:892,  region:"Nord-Est",    median:245000, top_type:"appartement" },
  { name:"Ben Arous",   lat:36.7453, lng:10.2281, ppm2:2700, listings:654,  region:"Nord-Est",    median:220000, top_type:"maison"      },
  { name:"Manouba",     lat:36.8101, lng:9.7849,  ppm2:2200, listings:431,  region:"Nord-Est",    median:185000, top_type:"maison"      },
  { name:"Nabeul",      lat:36.4513, lng:10.7357, ppm2:2600, listings:1203, region:"Nord-Est",    median:210000, top_type:"villa"       },
  { name:"Zaghouan",    lat:36.4029, lng:10.1429, ppm2:1400, listings:124,  region:"Nord",        median:120000, top_type:"terrain"     },
  { name:"Bizerte",     lat:37.2744, lng:9.8739,  ppm2:1800, listings:456,  region:"Nord",        median:155000, top_type:"appartement" },
  { name:"Béja",        lat:36.7256, lng:9.1817,  ppm2:1100, listings:134,  region:"Nord-Ouest",  median:95000,  top_type:"maison"      },
  { name:"Jendouba",    lat:36.5012, lng:8.7757,  ppm2:900,  listings:98,   region:"Nord-Ouest",  median:78000,  top_type:"terrain"     },
  { name:"Le Kef",      lat:36.1826, lng:8.7148,  ppm2:850,  listings:76,   region:"Nord-Ouest",  median:72000,  top_type:"maison"      },
  { name:"Siliana",     lat:36.0849, lng:9.3708,  ppm2:780,  listings:58,   region:"Nord-Ouest",  median:65000,  top_type:"terrain"     },
  { name:"Sousse",      lat:35.8256, lng:10.6369, ppm2:2800, listings:1098, region:"Centre-Est",  median:235000, top_type:"appartement" },
  { name:"Monastir",    lat:35.7643, lng:10.8113, ppm2:2600, listings:743,  region:"Centre-Est",  median:215000, top_type:"villa"       },
  { name:"Mahdia",      lat:35.5047, lng:11.0622, ppm2:1800, listings:312,  region:"Centre-Est",  median:155000, top_type:"villa"       },
  { name:"Sfax",        lat:34.7398, lng:10.7600, ppm2:2100, listings:876,  region:"Centre-Est",  median:175000, top_type:"appartement" },
  { name:"Kairouan",    lat:35.6712, lng:10.1006, ppm2:1100, listings:234,  region:"Centre",      median:92000,  top_type:"maison"      },
  { name:"Kasserine",   lat:35.1671, lng:8.8307,  ppm2:700,  listings:87,   region:"Centre-Ouest",median:58000,  top_type:"terrain"     },
  { name:"Sidi Bouzid", lat:35.0382, lng:9.4858,  ppm2:650,  listings:67,   region:"Centre-Ouest",median:54000,  top_type:"terrain"     },
  { name:"Gabès",       lat:33.8881, lng:10.0982, ppm2:1300, listings:198,  region:"Sud",         median:110000, top_type:"maison"      },
  { name:"Médenine",    lat:33.3549, lng:10.5055, ppm2:1500, listings:312,  region:"Sud",         median:128000, top_type:"villa"       },
  { name:"Tataouine",   lat:32.9211, lng:10.4518, ppm2:600,  listings:43,   region:"Sud",         median:48000,  top_type:"terrain"     },
  { name:"Gafsa",       lat:34.4250, lng:8.7842,  ppm2:800,  listings:112,  region:"Sud-Ouest",   median:68000,  top_type:"maison"      },
  { name:"Tozeur",      lat:33.9197, lng:8.1336,  ppm2:1200, listings:89,   region:"Sud-Ouest",   median:102000, top_type:"villa"       },
  { name:"Kébili",      lat:33.7038, lng:8.9690,  ppm2:700,  listings:54,   region:"Sud-Ouest",   median:57000,  top_type:"terrain"     },
];

export const SAMPLE_LISTINGS = [
  { lat:36.894, lng:10.186, title:"Villa S+4",        city:"La Marsa", price:650000, surface:280,  trust:0.87, type:"villa"        },
  { lat:36.453, lng:10.740, title:"Terrain 1200m²",   city:"Hammamet", price:180000, surface:1200, trust:0.34, type:"terrain"      },
  { lat:35.832, lng:10.630, title:"Appt S+2",         city:"Sousse",   price:215000, surface:95,   trust:0.72, type:"appartement"  },
  { lat:36.817, lng:10.163, title:"Studio meublé",    city:"Tunis",    price:130000, surface:52,   trust:0.91, type:"studio"       },
  { lat:34.740, lng:10.762, title:"Local commercial", city:"Sfax",     price:320000, surface:180,  trust:0.61, type:"bureau_local" },
  { lat:35.764, lng:10.815, title:"Villa bord de mer",city:"Monastir", price:480000, surface:220,  trust:0.78, type:"villa"        },
  { lat:36.878, lng:10.170, title:"Appt S+3",         city:"Ariana",   price:260000, surface:115,  trust:0.82, type:"appartement"  },
  { lat:37.274, lng:9.874,  title:"Maison R+1",       city:"Bizerte",  price:195000, surface:140,  trust:0.69, type:"maison"       },
  { lat:33.889, lng:10.098, title:"Villa Oasis",      city:"Gabès",    price:290000, surface:200,  trust:0.55, type:"villa"        },
  { lat:35.505, lng:11.062, title:"Appt vue mer",     city:"Mahdia",   price:175000, surface:88,   trust:0.80, type:"appartement"  },
];

export function getPpm2Color(ppm2: number): string {
  if (ppm2 < 800)  return "#6B7FE8";
  if (ppm2 < 1500) return "#6B9FE8";
  if (ppm2 < 2200) return "#52C896";
  if (ppm2 < 2800) return "#E8A84C";
  return "#E05C5C";
}

function getTrustColor(t: number) {
  return t >= .75 ? "#52C896" : t >= .5 ? "#E8A84C" : "#E05C5C";
}

function govPopup(g: typeof GOUVERNORATS[0]) {
  const c = getPpm2Color(g.ppm2);
  return `<div style="font-family:sans-serif;min-width:210px">
    <div style="font-size:14px;font-weight:600;color:#F2F0EC;margin-bottom:10px;
      border-bottom:1px solid rgba(255,255,255,.1);padding-bottom:8px">
      📍 ${g.name} <span style="font-size:10px;color:#6B6966">${g.region}</span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
      <div style="background:rgba(255,255,255,.05);border-radius:6px;padding:8px">
        <div style="font-size:10px;color:#6B6966;margin-bottom:3px">PRIX/M²</div>
        <div style="font-size:15px;font-weight:700;color:${c}">${g.ppm2.toLocaleString("fr-FR")} TND</div>
      </div>
      <div style="background:rgba(255,255,255,.05);border-radius:6px;padding:8px">
        <div style="font-size:10px;color:#6B6966;margin-bottom:3px">ANNONCES</div>
        <div style="font-size:15px;font-weight:700;color:#F2F0EC">${g.listings.toLocaleString("fr-FR")}</div>
      </div>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:11px;color:#6B6966">
      <span>Médian : <b style="color:#C8A96E">${g.median.toLocaleString("fr-FR")} TND</b></span>
      <span>Top : <b style="color:#F2F0EC">${g.top_type}</b></span>
    </div>
  </div>`;
}

function listingPopup(l: typeof SAMPLE_LISTINGS[0]) {
  const tc = getTrustColor(l.trust);
  return `<div style="font-family:sans-serif;min-width:180px">
    <div style="font-size:13px;font-weight:600;color:#F2F0EC;margin-bottom:6px">${l.title}</div>
    <div style="font-size:11px;color:#6B6966;margin-bottom:8px">📍 ${l.city} · ${l.type.replace("_"," ")}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">
      <div style="background:rgba(255,255,255,.05);border-radius:5px;padding:6px">
        <div style="font-size:9px;color:#6B6966">PRIX</div>
        <div style="font-size:13px;font-weight:600;color:#C8A96E">${(l.price/1000).toFixed(0)}K TND</div>
      </div>
      <div style="background:rgba(255,255,255,.05);border-radius:5px;padding:6px">
        <div style="font-size:9px;color:#6B6966">PRIX/M²</div>
        <div style="font-size:13px;font-weight:600;color:#F2F0EC">${Math.round(l.price/l.surface).toLocaleString("fr-FR")}</div>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:6px">
      <span style="font-size:10px;color:#6B6966">Trust</span>
      <div style="flex:1;height:3px;background:rgba(255,255,255,.08);border-radius:2px">
        <div style="height:100%;width:${l.trust*100}%;background:${tc};border-radius:2px"></div>
      </div>
      <span style="font-size:11px;font-weight:600;color:${tc}">${l.trust.toFixed(2)}</span>
    </div>
  </div>`;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export type LayerMode = "circles" | "heatmap" | "clusters";

interface HeatPoint { lat: number; lon: number; ppm2: number; }

interface Props {
  filterType?:   string;
  filterRegion?: string;
  showListings?: boolean;
  layerMode?:    LayerMode;
  onGouvSelect?: (g: typeof GOUVERNORATS[0] | null) => void;
}

// ── Chargement des plugins Leaflet ────────────────────────────────────────────

async function loadLeaflet(): Promise<any> {
  const win = window as any;
  if (win.L) return win.L;
  await new Promise<void>(res => {
    const s = document.createElement("script");
    s.src   = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js";
    s.onload = () => res();
    document.head.appendChild(s);
  });
  return win.L;
}

async function loadHeatPlugin(): Promise<void> {
  const win = window as any;
  if (win.L?.heatLayer) return;
  await new Promise<void>(res => {
    const s = document.createElement("script");
    s.src   = "https://cdnjs.cloudflare.com/ajax/libs/Leaflet.heat/0.2.0/leaflet-heat.js";
    s.onload = () => res();
    document.head.appendChild(s);
  });
}

async function loadClusterPlugin(): Promise<void> {
  const win = window as any;
  if (win.L?.markerClusterGroup) return;

  // CSS du cluster
  if (!document.getElementById("cluster-css")) {
    const cssLinks = [
      "https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.css",
      "https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.Default.css",
    ];
    cssLinks.forEach(href => {
      const l = document.createElement("link");
      l.rel   = "stylesheet"; l.href = href;
      document.head.appendChild(l);
    });
    document.getElementById("cluster-css") || (() => {
      const d = document.createElement("div"); d.id = "cluster-css";
      document.head.appendChild(d);
    })();
  }

  await new Promise<void>(res => {
    const s = document.createElement("script");
    s.src   = "https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.js";
    s.onload = () => res();
    document.head.appendChild(s);
  });
}

// ── Composant principal ───────────────────────────────────────────────────────

export default function MapComponent({
  filterType, filterRegion,
  showListings = true,
  layerMode    = "circles",
  onGouvSelect,
}: Props) {
  const divRef      = useRef<HTMLDivElement>(null);
  const mapRef      = useRef<any>(null);
  const layersRef   = useRef<any[]>([]);
  const initialised = useRef(false);
  const [heatPts,   setHeatPts]   = useState<HeatPoint[]>([]);
  const [dataStatus,setDataStatus]= useState<"loading"|"live"|"demo">("loading");

  // ── Chargement des points heatmap depuis l'API ────────────────────────────
  useEffect(() => {
    fetch("/api/territorial/spatial?level=all")
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.heatmap_data?.length) {
          setHeatPts(d.heatmap_data);
          setDataStatus("live");
        } else {
          // Génère des points de démo depuis les gouvernorats
          const demo: HeatPoint[] = GOUVERNORATS.flatMap(g =>
            Array.from({ length: Math.min(g.listings, 40) }, (_, i) => ({
              lat: g.lat + (Math.random() - 0.5) * 0.8,
              lon: g.lng + (Math.random() - 0.5) * 0.8,
              ppm2: g.ppm2 * (0.8 + Math.random() * 0.4),
            }))
          );
          setHeatPts(demo);
          setDataStatus("demo");
        }
      })
      .catch(() => {
        const demo: HeatPoint[] = GOUVERNORATS.flatMap(g =>
          Array.from({ length: Math.min(g.listings, 40) }, (_, i) => ({
            lat: g.lat + (Math.random() - 0.5) * 0.8,
            lon: g.lng + (Math.random() - 0.5) * 0.8,
            ppm2: g.ppm2 * (0.8 + Math.random() * 0.4),
          }))
        );
        setHeatPts(demo);
        setDataStatus("demo");
      });
  }, []);

  // ── Init Leaflet ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (initialised.current) return;
    initialised.current = true;

    if (!document.getElementById("lf-css")) {
      const l = document.createElement("link");
      l.id = "lf-css"; l.rel = "stylesheet";
      l.href = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css";
      document.head.appendChild(l);
    }

    loadLeaflet().then(L => {
      if (!document.getElementById("lf-overrides")) {
        const s = document.createElement("style");
        s.id = "lf-overrides";
        s.textContent = `
          .leaflet-popup-content-wrapper{background:#18181C!important;border:1px solid rgba(255,255,255,.08)!important;border-radius:10px!important;box-shadow:0 8px 32px rgba(0,0,0,.6)!important;color:#F2F0EC!important}
          .leaflet-popup-content{margin:14px 16px!important}
          .leaflet-popup-tip{background:#18181C!important}
          .leaflet-popup-close-button{color:#6B6966!important;top:8px!important;right:10px!important}
          .leaflet-control-zoom a{background:#18181C!important;color:#F2F0EC!important;border-color:rgba(255,255,255,.1)!important}
          .leaflet-control-zoom a:hover{background:#2a2a2e!important}
          .leaflet-control-attribution{background:rgba(9,9,11,.7)!important;color:#6B6966!important;font-size:9px!important}
          .leaflet-control-attribution a{color:#C8A96E!important}
          /* Cluster styles custom */
          .marker-cluster-small, .marker-cluster-medium, .marker-cluster-large {
            background:rgba(200,169,110,.15)!important;border:2px solid rgba(200,169,110,.4)!important;
          }
          .marker-cluster-small div, .marker-cluster-medium div, .marker-cluster-large div {
            background:rgba(200,169,110,.3)!important;color:#F2F0EC!important;font-weight:600;font-size:11px;
          }
          .leaflet-data-layer { opacity: 1 !important; }
        `;
        document.head.appendChild(s);
      }

      if (!divRef.current || mapRef.current) return;

      const map = L.map(divRef.current, { center: [33.8, 9.5], zoom: 7 });
      mapRef.current = map;

      const carto = L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        { attribution: "© OSM © CARTO", subdomains: "abcd", maxZoom: 18 }
      );
      const osm = L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        { attribution: "© OpenStreetMap", maxZoom: 18 }
      );

      carto.addTo(map);
      let tilesLoaded = false;
      carto.on("tileload", () => { tilesLoaded = true; });
      setTimeout(() => { if (!tilesLoaded) { map.removeLayer(carto); osm.addTo(map); } }, 5000);

      requestAnimationFrame(() => { map.invalidateSize(); });
      setTimeout(() => map.invalidateSize(), 300);
      setTimeout(() => map.invalidateSize(), 800);
      if (typeof ResizeObserver !== "undefined" && divRef.current) {
        new ResizeObserver(() => map.invalidateSize()).observe(divRef.current);
      }
    });

    return () => { mapRef.current?.remove(); mapRef.current = null; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Redessine quand mode ou filtres changent ──────────────────────────────
  useEffect(() => {
    if (!mapRef.current || heatPts.length === 0) return;
    drawLayers();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterType, filterRegion, showListings, layerMode, heatPts]);

  async function drawLayers() {
    const L = (window as any).L;
    if (!L || !mapRef.current) return;
    const map = mapRef.current;

    // Nettoyage
    layersRef.current.forEach(l => { try { map.removeLayer(l); } catch {} });
    layersRef.current = [];

    if (layerMode === "heatmap") {
      await loadHeatPlugin();
      const L2 = (window as any).L;
      if (!L2.heatLayer) return;

      // Normalise l'intensité selon ppm2
      const maxPpm2 = Math.max(...heatPts.map(p => p.ppm2), 1);
      const pts = heatPts
        .filter(p => p.lat && p.lon)
        .map(p => [p.lat, p.lon, p.ppm2 / maxPpm2]);

      const heat = L2.heatLayer(pts, {
        radius:  28,
        blur:    22,
        maxZoom: 13,
        max:     1.0,
        gradient: {
          0.0: "#0d47a1",
          0.2: "#1565c0",
          0.4: "#1D9E75",
          0.6: "#E8A84C",
          0.8: "#E05C5C",
          1.0: "#b71c1c",
        },
      }).addTo(map);
      layersRef.current.push(heat);

      // Légende gradient dynamique
      const legendCtrl = L.control({ position: "bottomleft" });
      legendCtrl.onAdd = () => {
        const d = L.DomUtil.create("div");
        d.style.cssText = "background:rgba(9,9,11,.85);border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:10px 14px;font-family:sans-serif;color:#F2F0EC;min-width:160px";
        d.innerHTML = `
          <div style="font-size:10px;color:#6B6966;text-transform:uppercase;letter-spacing:.06em;margin-bottom:7px">Densité prix/m²</div>
          <div style="height:10px;border-radius:5px;background:linear-gradient(to right,#0d47a1,#1D9E75,#E8A84C,#E05C5C,#b71c1c);margin-bottom:5px"></div>
          <div style="display:flex;justify-content:space-between;font-size:10px;color:#6B6966">
            <span>Bas</span><span>Moyen</span><span>Élevé</span>
          </div>
        `;
        return d;
      };
      legendCtrl.addTo(map);
      layersRef.current.push(legendCtrl);
      return;
    }

    if (layerMode === "clusters") {
      await loadClusterPlugin();
      const L2 = (window as any).L;
      if (!L2.markerClusterGroup) return;

      const clusterGroup = L2.markerClusterGroup({
        maxClusterRadius: 50,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        iconCreateFunction: (cluster: any) => {
          const count = cluster.getChildCount();
          const color  = count > 100 ? "#E05C5C" : count > 30 ? "#E8A84C" : "#52C896";
          return L2.divIcon({
            className: "",
            html: `<div style="
              background:${color}22;border:2px solid ${color}66;
              border-radius:50%;width:38px;height:38px;
              display:flex;align-items:center;justify-content:center;
              font-size:12px;font-weight:700;color:${color};
              box-shadow:0 0 12px ${color}44;
            ">${count}</div>`,
            iconSize: [38, 38],
          });
        },
      });

      // Tous les points heatmap comme marqueurs clusterisés
      heatPts.forEach(pt => {
        if (!pt.lat || !pt.lon) return;
        const color = getPpm2Color(pt.ppm2);
        const icon  = L2.divIcon({
          className: "",
          html: `<div style="width:8px;height:8px;background:${color};border:1.5px solid rgba(255,255,255,.6);border-radius:50%;box-shadow:0 0 5px ${color}88"></div>`,
          iconSize: [8, 8], iconAnchor: [4, 4],
        });
        const marker = L2.marker([pt.lat, pt.lon], { icon });
        marker.bindPopup(`
          <div style="font-family:sans-serif;color:#F2F0EC;font-size:12px">
            <b style="color:${color}">${Math.round(pt.ppm2).toLocaleString("fr-FR")} TND/m²</b>
          </div>`, { maxWidth: 160 });
        clusterGroup.addLayer(marker);
      });

      map.addLayer(clusterGroup);
      layersRef.current.push(clusterGroup);
      return;
    }

    // ── Mode "circles" (défaut) ───────────────────────────────────────────────
    GOUVERNORATS
      .filter(g => !filterRegion || g.region === filterRegion)
      .forEach(g => {
        const color  = getPpm2Color(g.ppm2);
        const radius = Math.sqrt(g.listings) * 1800;

        const halo = L.circle([g.lat, g.lng], {
          radius: radius * 1.4, fillColor: color, fillOpacity: 0.06,
          color: "transparent", weight: 0, interactive: false,
        }).addTo(map);

        const circle = L.circle([g.lat, g.lng], {
          radius, fillColor: color, fillOpacity: 0.28,
          color, weight: 1.5, opacity: 0.70,
        }).addTo(map);

        circle.bindPopup(govPopup(g), { maxWidth: 260 });
        circle.on("mouseover", function (this: any) {
          this.setStyle({ fillOpacity: 0.55, weight: 2.5 });
          onGouvSelect?.(g);
        });
        circle.on("mouseout", function (this: any) {
          this.setStyle({ fillOpacity: 0.28, weight: 1.5 });
        });
        circle.on("click", () => onGouvSelect?.(g));

        const lbl = L.divIcon({
          className: "",
          html: `<div style="font-family:sans-serif;font-size:10px;font-weight:500;
            color:rgba(242,240,236,.85);text-shadow:0 1px 3px rgba(0,0,0,.9);
            white-space:nowrap;pointer-events:none;text-align:center">
            ${g.name}<br>
            <span style="font-size:9px;color:${color};font-weight:600">
              ${g.ppm2.toLocaleString("fr-FR")} TND
            </span>
          </div>`,
          iconAnchor: [0, 0],
        });
        const lm = L.marker([g.lat - 0.15, g.lng], { icon: lbl, interactive: false }).addTo(map);
        layersRef.current.push(halo, circle, lm);
      });

    // Annonces individuelles
    if (showListings) {
      SAMPLE_LISTINGS
        .filter(l => !filterType || l.type === filterType)
        .forEach(l => {
          const color = getTrustColor(l.trust);
          const icon  = L.divIcon({
            className: "",
            html: `<div style="width:10px;height:10px;background:${color};border:2px solid rgba(255,255,255,.7);border-radius:50%;box-shadow:0 0 6px ${color}88"></div>`,
            iconSize: [10, 10], iconAnchor: [5, 5],
          });
          const m = L.marker([l.lat, l.lng], { icon })
            .addTo(map)
            .bindPopup(listingPopup(l), { maxWidth: 220 });
          layersRef.current.push(m);
        });
    }
  }

  return (
    <div style={{ position: "relative" }}>
      {/* Badge source des données */}
      {dataStatus !== "loading" && (
        <div style={{
          position: "absolute", top: 10, right: 10, zIndex: 1000,
          background: "rgba(9,9,11,.85)", border: "1px solid rgba(255,255,255,.1)",
          borderRadius: 6, padding: "3px 9px", fontSize: 9,
          color: dataStatus === "live" ? "#52C896" : "#E8A84C",
          fontFamily: "monospace",
        }}>
          {dataStatus === "live" ? "● DONNÉES RÉELLES" : "● DONNÉES DÉMO"}
        </div>
      )}
      <div
        ref={divRef}
        style={{
          width: "100%", height: 480, minHeight: 480,
          borderRadius: 12, overflow: "hidden", background: "#09090B",
        }}
      />
    </div>
  );
}
