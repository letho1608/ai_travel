"use client";

import L from "leaflet";
import { useEffect, useRef } from "react";

type Stop = {name:string;location:{lat:number;lng:number}};

export default function RoadTripMap({geometry,stops,label}:{geometry:{coordinates:number[][]};stops:Stop[];label:string}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(()=>{
    if(!ref.current)return;
    const map=L.map(ref.current).setView([stops[0].location.lat,stops[0].location.lng],7);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:"© OpenStreetMap contributors",maxZoom:19}).addTo(map);
    const points=geometry.coordinates.map(point=>[point[1],point[0]] as L.LatLngTuple);
    L.polyline(points,{color:"#7d4fb8",weight:5}).addTo(map);
    stops.forEach((stop,index)=>L.circleMarker([stop.location.lat,stop.location.lng],{radius:9,color:index===0?"#bb4d45":"#7d4fb8",fillOpacity:1}).bindTooltip(`${index+1}. ${stop.name}`).addTo(map));
    map.fitBounds(points,{padding:[30,30]});
    return()=>{map.remove();};
  },[geometry,stops]);
  return <div ref={ref} className="roadtrip-map" role="region" aria-label={label}/>;
}
