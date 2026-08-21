"use client";

import L from "leaflet";
import { useEffect, useRef } from "react";

import type { Slot } from "@/lib/types";

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char] ?? char
  ));
}

function cityFromTitle(title: string) {
  const haystack = title.normalize("NFC");
  const cities: Array<[RegExp, string]> = [
    [/lâm\s*đồng|lam\s*dong|đà\s*lạt|da\s*lat|dalat/i, "Đà Lạt"],
    [/hội\s*an|hoi\s*an/i, "Hội An"],
    [/đà\s*nẵng|da\s*nang|danang/i, "Đà Nẵng"],
    [/nha\s*trang|nhatrang/i, "Nha Trang"],
    [/hà\s*nội|ha\s*noi|hanoi/i, "Hà Nội"],
    [/sài\s*gòn|sai\s*gon|tp\.?\s*hcm|hồ\s*chí\s*minh/i, "TP.HCM"],
    [/huế|(?:^|[^a-z])hue(?:$|[^a-z])/i, "Huế"],
    [/hạ\s*long|ha\s*long|halong/i, "Hạ Long"],
    [/sa\s*pa|sapa/i, "Sa Pa"],
    [/phú\s*quốc|phu\s*quoc/i, "Phú Quốc"],
    [/ninh\s*bình|ninh\s*binh/i, "Ninh Bình"],
    [/cần\s*thơ|can\s*tho/i, "Cần Thơ"],
    [/vũng\s*tàu|vung\s*tau/i, "Vũng Tàu"],
    [/cát\s*bà|cat\s*ba/i, "Cát Bà"],
  ];
  for (const [pattern, label] of cities) {
    if (pattern.test(haystack)) return label;
  }
  return "";
}

function normalizeCity(value: string) {
  return cityFromTitle(value) || value.trim();
}

function isGenericCountry(value: string) {
  return /^(việt\s*nam|vietnam)$/i.test(value.trim());
}

function slotCity(slot: Slot, fallbackCity = "") {
  const tripCity = normalizeCity(fallbackCity);
  const area = normalizeCity(slot.khu_vuc || "");
  if (tripCity && !isGenericCountry(tripCity)) return tripCity;
  if (area && !isGenericCountry(area)) return area;
  return "";
}

function placeReviewQuery(slot: Slot, fallbackCity = "") {
  const name = slot.ten_dia_diem.trim();
  const city = slotCity(slot, fallbackCity);
  const address = (slot.dia_chi_google || slot.dia_chi || "").trim();
  if (address) return `${name} ${address} review`;
  if (city) return `${name} ${city} review`;
  return `${name} review`;
}

function mapsHref(slot: Slot, fallbackCity = "") {
  const placeId = (slot.google_place_id || "").trim().replace(/^places\//, "");
  if (placeId) {
    return `https://www.google.com/maps/place/?q=place_id:${encodeURIComponent(placeId)}`;
  }
  const params = new URLSearchParams({
    name: slot.ten_dia_diem.trim(),
    lat: String(slot.toa_do.lat),
    lng: String(slot.toa_do.lng),
    city: fallbackCity,
    dia_diem_id: slot.dia_diem_id,
  });
  return `/api/maps/place?${params.toString()}`;
}

function placeReviewLinks(slot: Slot, fallbackCity = "") {
  const query = encodeURIComponent(placeReviewQuery(slot, fallbackCity));
  return {
    google: `https://www.google.com/search?q=${query}`,
    tiktok: `https://www.tiktok.com/search?q=${query}`,
    maps: mapsHref(slot, fallbackCity),
  };
}

function popupHtml(slot: Slot, index: number, fallbackCity = "") {
  const safeName = escapeHtml(slot.ten_dia_diem);
  const links = placeReviewLinks(slot, fallbackCity);
  const image = slot.anh
    ? `<img src="${escapeHtml(slot.anh)}" alt="" loading="lazy" referrerPolicy="no-referrer"/>`
    : "";
  return `<div class="map-popup">${image}<strong>${index + 1}. ${safeName}</strong><p>Xem thêm thông tin về địa điểm này trên:</p><div class="map-popup-actions"><a href="${links.google}" target="_blank" rel="noopener noreferrer">Google</a><a href="${links.tiktok}" target="_blank" rel="noopener noreferrer">TikTok</a><a href="${links.maps}" target="_blank" rel="noopener noreferrer">Maps</a></div></div>`;
}

export default function MapView({ slots, selectedId, onSelect, destination, title }: { slots: Slot[]; selectedId?: string; onSelect?: (id:string)=>void; destination?: string | null; title?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!ref.current) return;
    const map = L.map(ref.current).setView([21.0285, 105.8542], 13);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const fallbackCity = [destination, cityFromTitle(title || ""), ...slots.map((slot) => slot.khu_vuc)]
      .map((value) => String(value || "").trim())
      .find((value) => value && !isGenericCountry(value)) || "";
    const points = slots.map(
      (slot) => [slot.toa_do.lat, slot.toa_do.lng] as L.LatLngTuple,
    );
    const layers: L.Layer[] = [];
    points.forEach((point, index) => {
      const slot = slots[index];
      const marker = L.circleMarker(point, { radius: slot.dia_diem_id === selectedId ? 12 : 8, color: slot.dia_diem_id === selectedId ? "#bb4d45" : "#086b27", fillOpacity: 1 })
        .bindTooltip(`${index + 1}. ${slot.ten_dia_diem}`)
        .on("click", () => onSelectRef.current?.(slot.dia_diem_id));
      marker.bindPopup(popupHtml(slot, index, fallbackCity), { maxWidth: 280 });
      layers.push(marker);
      marker.addTo(map);
    });
    const line = L.polyline(points, { color: "#086b27", weight: 4 });
    layers.push(line);
    line.addTo(map);
    if (points.length) map.fitBounds(points, { padding: [30, 30] });
    return () => {
      layers.forEach((layer) => map.removeLayer(layer));
    };
  }, [slots, selectedId, destination, title]);

  return <div ref={ref} className="map" aria-label="Bản đồ lịch trình" />;
}
