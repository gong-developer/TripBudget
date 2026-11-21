import { lazy, memo, Suspense, useCallback, useLayoutEffect, useEffect, useRef } from 'react';
import { MapContainer, Marker, Tooltip, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import { destinationLabel,destinationRegion } from '../destinationLabel';
import {countryStyle} from '../countries';
import {useReducedMotion} from '../useReducedMotion';
import Roulette from './Roulette';
const KoreanBasemap=lazy(()=>import('./KoreanBasemap'));
const KOREA_BOUNDS=L.latLngBounds([[32.8,124.5],[38.7,132.1]]);
const WORLD_BOUNDS=[[-85,-180],[85,180]];

const icon = L.divIcon({ className: 'city-marker', html: '<span>✈</span>', iconSize: [48,48], iconAnchor: [24,24] });
const placeIcon = L.divIcon({className:'sight-marker',html:'<span>●</span>',iconSize:[26,26],iconAnchor:[13,13]});
function CountryBoundaries({data,selectedCode,onSelect,disabled}) {
 const select=useRef(onSelect),blocked=useRef(disabled),timer=useRef(null);
 select.current=onSelect;blocked.current=disabled;
 const map=useMap();
 const style=useCallback(feature=>countryStyle(feature.properties.code,selectedCode),[selectedCode]);
 useEffect(()=>{const clear=()=>clearTimeout(timer.current);map.on('dragstart dblclick',clear);return()=>{clear();map.off('dragstart dblclick',clear)}},[map]);
 if(!data)return null;
 return <GeoJSON data={data} style={style} onEachFeature={(feature,layer)=>{
  layer.bindTooltip(()=>{const label=document.createElement('span');label.textContent=feature.properties.name;return label},{sticky:true});
  layer.on('click',event=>{clearTimeout(timer.current);if(blocked.current||event.originalEvent?.detail>1)return;timer.current=setTimeout(()=>{if(!blocked.current)select.current(feature.properties.code)},300)});
  layer.on('dblclick',()=>clearTimeout(timer.current));
 }}/>;
}

function MapScope({domestic}) {
 const map=useMap();
 useLayoutEffect(()=>{
  map.stop();
  map.setMinZoom(2);
  map.setMaxBounds(domestic?KOREA_BOUNDS.pad(.15):WORLD_BOUNDS);
  if(!domestic)return;
  const update=()=>{
   map.setMinZoom(2);
   map.setMinZoom(map.getBoundsZoom(KOREA_BOUNDS,false,L.point(48,48)));
  };
  update();map.on('resize',update);
  return()=>map.off('resize',update);
 },[map,domestic]);
 return null;
}

function MapVisibility({visible}){
 const map=useMap();
 useLayoutEffect(()=>{if(visible)map.invalidateSize({pan:false})},[map,visible]);
 return null;
}

function View({ cities, selected, focus, busy, nearby, country, domestic, visible }) {
  const map = useMap();
  const reduce = useReducedMotion();
  useLayoutEffect(() => {
    // Keep the destination hidden until the roulette reveals its result.
    if (busy||!visible) return;
    map.stop();
    if (focus && Number.isFinite(focus.lat) && Number.isFinite(focus.lng)) {
      const zoom=Math.max(map.getMinZoom(),focus.zoom);
      if(map.getZoom()!==zoom||!map.getCenter().equals([focus.lat,focus.lng],1e-7)) map.flyTo([focus.lat,focus.lng],zoom,{animate:!reduce,duration:.8});
    }
    else if (nearby.length) map.fitBounds(nearby.map(place=>[place.lat,place.lng]), {padding:[45,45],maxZoom:14,animate:false});
    else if (selected) map.flyTo([selected.lat,selected.lng],10,{animate:!reduce,duration:.8});
    else if (cities.length) map.fitBounds(cities.map(c => [c.lat,c.lng]), { padding: [55,55], maxZoom: 6, animate: false });
    else if (domestic) map.fitBounds(KOREA_BOUNDS,{padding:[24,24],animate:false});
    else if (country?.bounds) map.fitBounds(country.bounds,{padding:[35,35],maxZoom:8,animate:false});
    else map.setView([22,40], 2, { animate: false });
  }, [map, cities, selected?.lat, selected?.lng, focus, busy, nearby, country, domestic, visible, reduce]);
  return null;
}
function MapLock({busy}){
 const map=useMap();
 useLayoutEffect(()=>{
  if(!busy)return;
  map.stop();
  const handlers=['dragging','touchZoom','doubleClickZoom','scrollWheelZoom','boxZoom','keyboard']
   .filter(key=>map[key]?.enabled());
  handlers.forEach(key=>map[key].disable());
  return()=>handlers.forEach(key=>map[key].enable());
 },[map,busy]);
 return null;
}
const Markers=memo(function Markers({cities,nearby,select,placeSelect,selectedName}){
 return <>{cities.map(city=><Marker key={city.cityName} position={[city.lat,city.lng]} icon={icon}
   eventHandlers={{click:()=>select.current(city)}} title={destinationLabel(city)}><Tooltip key={selectedName===city.cityName?'selected':'candidate'} permanent={selectedName===city.cityName} direction="top" offset={[0,-18]}><strong>{destinationLabel(city)}</strong><br/>지역 · {destinationRegion(city)}</Tooltip></Marker>)}
   {nearby.map((place,i)=><Marker key={place.placeId||`sight-${i}`} position={[place.lat,place.lng]} icon={placeIcon} title={place.name} eventHandlers={{click:()=>placeSelect.current?.(place)}}><Tooltip>{i+1}. {place.name}</Tooltip></Marker>)}
 </>;
});
export default function TravelMap({cities,selected,focus,flight,spinning=false,onLand,onSelect,celebrate,nearby=[],onPlaceSelect,countryData=null,country=null,onCountrySelect,category='all',visible=true}) {
  const select=useRef(onSelect),placeSelect=useRef(onPlaceSelect);
  select.current=onSelect;placeSelect.current=onPlaceSelect;
  const domestic=category==='domestic';
  const busy=spinning||!!flight;
  return <div className={'map-shell'+(busy?' roulette-active':'')}>
    <MapContainer center={domestic?KOREA_BOUNDS.getCenter():[22,40]} zoom={domestic?6:2} minZoom={2} maxZoom={18} maxBounds={WORLD_BOUNDS} maxBoundsViscosity={1} preferCanvas className="travel-map">
      <MapVisibility visible={visible}/>
      <MapScope domestic={domestic}/>
      <MapLock busy={busy}/>
      <Suspense fallback={null}><KoreanBasemap/></Suspense>
      <CountryBoundaries data={countryData} selectedCode={domestic?'kr':country?.code} onSelect={onCountrySelect} disabled={busy}/>
      <View cities={cities} selected={selected} focus={focus} busy={busy} nearby={nearby} country={country} domestic={domestic} visible={visible}/>
      {!busy&&<Markers cities={cities} nearby={nearby} select={select} placeSelect={placeSelect} selectedName={selected?.cityName}/>}
    </MapContainer>
    {busy&&<Roulette flight={flight} onLand={onLand}/>}
    <div className="map-language-caption">한국어 우선 지도 · 등록 지명 사용 · 미확인 이름은 영어·원어 표시</div>
    {celebrate && <div className="confetti" aria-hidden="true">{Array.from({length:30},(_,i)=>
      <i key={celebrate+'-'+i} style={{left:(i*37%100)+'%',background:['#baff65','#b6a2ff','#ffcf67'][i%3],animationDelay:`${(i%5)*.08}s`}}/>)}</div>}
  </div>;
}
