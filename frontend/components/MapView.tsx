"use client";

import L from "leaflet";
import { useEffect, useRef } from "react";

import type { Slot } from "@/lib/types";

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
      if (slot.anh) {
        marker.bindPopup(
          `<div class="map-popup"><img src="${slot.anh}" alt="" loading="lazy" referrerPolicy="no-referrer"/><strong>${index + 1}. ${slot.ten_dia_diem}</strong></div>`,
          { maxWidth: 260 },
        );
      }
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
