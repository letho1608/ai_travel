"use client";

import L from "leaflet";
import { useEffect, useRef } from "react";

import type { Slot } from "@/lib/types";

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char] ?? char
  ));
}

function placeReviewLinks(slot: Slot) {
  const name = slot.ten_dia_diem.trim();
  const query = encodeURIComponent(`${name} Hanoi review`);
  const coordinates = `${slot.toa_do.lat},${slot.toa_do.lng}`;
  const mapQuery = encodeURIComponent(`${name} ${coordinates}`);
  const placeId = slot.google_place_id?.trim();
  return {
    google: `https://www.google.com/search?q=${query}`,
    tiktok: `https://www.tiktok.com/search?q=${query}`,
    maps:
      slot.google_maps_url ||
      (placeId
        ? `https://www.google.com/maps/search/?api=1&query=${mapQuery}&query_place_id=${encodeURIComponent(placeId)}`
        : `https://www.google.com/maps/search/?api=1&query=${mapQuery}`),
  };
}

function popupHtml(slot: Slot, index: number) {
  const safeName = escapeHtml(slot.ten_dia_diem);
  const links = placeReviewLinks(slot);
  const image = slot.anh
    ? `<img src="${escapeHtml(slot.anh)}" alt="" loading="lazy" referrerPolicy="no-referrer"/>`
    : "";
  return `<div class="map-popup">${image}<strong>${index + 1}. ${safeName}</strong><p>Xem thêm thông tin về địa điểm này trên:</p><div class="map-popup-actions"><a href="${links.google}" target="_blank" rel="noopener noreferrer">Google</a><a href="${links.tiktok}" target="_blank" rel="noopener noreferrer">TikTok</a><a href="${links.maps}" target="_blank" rel="noopener noreferrer">Maps</a></div></div>`;
}

export default function MapView({ slots, selectedId, onSelect }: { slots: Slot[]; selectedId?: string; onSelect?: (id:string)=>void }) {
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
    const points = slots.map(
      (slot) => [slot.toa_do.lat, slot.toa_do.lng] as L.LatLngTuple,
    );
    const layers: L.Layer[] = [];
    points.forEach((point, index) => {
      const slot = slots[index];
      const marker = L.circleMarker(point, { radius: slot.dia_diem_id === selectedId ? 12 : 8, color: slot.dia_diem_id === selectedId ? "#bb4d45" : "#086b27", fillOpacity: 1 })
        .bindTooltip(`${index + 1}. ${slot.ten_dia_diem}`)
        .on("click", () => onSelectRef.current?.(slot.dia_diem_id));
      marker.bindPopup(popupHtml(slot, index), { maxWidth: 280 });
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
  }, [slots, selectedId]);

  return <div ref={ref} className="map" aria-label="Bản đồ lịch trình" />;
}
