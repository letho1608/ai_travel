"use client";

import L from "leaflet";
import { useEffect, useRef } from "react";

import type { Slot } from "@/lib/types";

export default function MapView({ slots, selectedId, onSelect }: { slots: Slot[]; selectedId?: string; onSelect?: (id:string)=>void }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const map = L.map(ref.current).setView([21.0285, 105.8542], 13);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(map);
    const points = slots.map(
      (slot) => [slot.toa_do.lat, slot.toa_do.lng] as L.LatLngTuple,
    );
    points.forEach((point, index) =>
      L.circleMarker(point, { radius: slots[index].dia_diem_id === selectedId ? 12 : 8, color: slots[index].dia_diem_id === selectedId ? "#e4572e" : "#0f766e", fillOpacity: 1 })
        .bindTooltip(`${index + 1}. ${slots[index].ten_dia_diem}`)
        .on("click", () => onSelect?.(slots[index].dia_diem_id))
        .addTo(map),
    );
    L.polyline(points, { color: "#0f766e", weight: 4 }).addTo(map);
    if (points.length) map.fitBounds(points, { padding: [30, 30] });
    return () => {
      map.remove();
    };
  }, [slots, selectedId, onSelect]);

  return <div ref={ref} className="map" aria-label="Bản đồ lịch trình" />;
}
