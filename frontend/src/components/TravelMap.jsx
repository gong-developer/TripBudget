import { useLayoutEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import { motion, useReducedMotion } from 'framer-motion';

const icon = L.divIcon({ className: 'city-marker', html: '<span>✈</span>', iconSize: [48,48], iconAnchor: [24,24] });
function View({ cities, flight }) {
  const map = useMap();
  useLayoutEffect(() => {
    if (flight) map.setView([flight.city.lat, flight.city.lng], 4, { animate: false });
    else if (cities.length) map.fitBounds(cities.map(c => [c.lat,c.lng]), { padding: [55,55], maxZoom: 6, animate: false });
    else map.setView([22,40], 2, { animate: false });
  }, [map, cities, flight]);
  return null;
}
function Dart({ flight, onLand }) {
  const map = useMap();
  const reduce = useReducedMotion();
  const [point,setPoint] = useState(null);
  useLayoutEffect(() => {
    const update = () => {
      const p = map.latLngToContainerPoint([flight.city.lat, flight.city.lng]);
      setPoint({ x:p.x-32, y:p.y-32 });
    };
    map.setView([flight.city.lat,flight.city.lng],4,{animate:false});
    update();
    map.on('resize',update);
    const handlers=['dragging','touchZoom','doubleClickZoom','scrollWheelZoom','boxZoom','keyboard'];
    handlers.forEach(key=>map[key]?.disable());
    map.zoomControl?.remove();
    return ()=>{
      map.off('resize',update);
      handlers.forEach(key=>map[key]?.enable());
      map.zoomControl?.addTo(map);
    };
  },[map,flight]);
  if(!point)return null;
  return <motion.div aria-hidden="true" className="dart"
    initial={{x:-80,y:-100,scale:2.8,rotate:-70,opacity:0}}
    animate={{x:[-80,point.x*.45,point.x],y:[-100,Math.min(-30,point.y-180),point.y],scale:[2.8,1.8,1],rotate:[-70,20,0],opacity:[0,1,1]}}
    transition={{duration:reduce?.01:1.35,times:[0,.6,1],ease:'easeIn'}}
    onAnimationComplete={()=>onLand(flight)}>📍</motion.div>;
}
export default function TravelMap({cities,flight,onLand,onSelect,celebrate}) {
  return <div className="map-shell">
    <MapContainer center={[22,40]} zoom={2} minZoom={2} className="travel-map">
      <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' noWrap />
      <View cities={cities} flight={flight}/>
      {!flight && cities.map(city=><Marker key={city.cityName} position={[city.lat,city.lng]} icon={icon}
        eventHandlers={{click:()=>onSelect(city)}} title={city.cityName}><Tooltip>{city.cityName}</Tooltip></Marker>)}
      {flight && <Dart key={flight.id} flight={flight} onLand={onLand}/>}
    </MapContainer>
    {celebrate && <div className="confetti" aria-hidden="true">{Array.from({length:30},(_,i)=>
      <motion.i key={celebrate+'-'+i} style={{left:(i*37%100)+'%',background:['#baff65','#b6a2ff','#ffcf67'][i%3]}}
        initial={{y:-30,rotate:0,opacity:1}} animate={{y:600,rotate:600,opacity:0}}
        transition={{duration:1.7,delay:(i%5)*.08}}/>)}</div>}
  </div>;
}
