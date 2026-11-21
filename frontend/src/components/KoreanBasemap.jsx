import { useEffect, useState } from 'react';
import { useMap } from 'react-leaflet';
import { maplibreGL } from '@maplibre/maplibre-gl-leaflet';
import { setWorkerUrl } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';
import { koreanMapStyle } from '../mapStyle';
import { attachMapTranslation } from '../mapTranslation';

setWorkerUrl(workerUrl);
const attribution='<a href="https://openfreemap.org/" target="_blank" rel="noreferrer">OpenFreeMap</a> · <a href="https://openmaptiles.org/" target="_blank" rel="noreferrer">OpenMapTiles</a> · © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>';

export default function KoreanBasemap(){
 const map=useMap(),[error,setError]=useState(false),[translation,setTranslation]=useState('ready');
 useEffect(()=>{
  const controller=new AbortController();let layer,stopTranslation;
  setError(false);
  async function load(){
   try{
    const response=await fetch('https://tiles.openfreemap.org/styles/positron',{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)])});
    if(!response.ok)throw new Error('Map style unavailable');
    const style=koreanMapStyle(await response.json());
    if(controller.signal.aborted)return;
    layer=maplibreGL({style,attributionControl:{customAttribution:attribution},interactive:false,localIdeographFontFamily:'sans-serif',
     renderWorldCopies:false}).addTo(map);
    const basemap=layer.getMaplibreMap();
    basemap.on('error',()=>{if(!controller.signal.aborted)setError(true)});
    stopTranslation=attachMapTranslation(basemap,controller.signal,setTranslation);
   }catch(e){if(!controller.signal.aborted)setError(true)}
  }
  load();
  return ()=>{controller.abort();stopTranslation?.();if(layer)map.removeLayer(layer)};
 },[map]);
 const notice=error?'지도 일부를 불러오지 못했어요. 인터넷 연결 후 새로고침해주세요.':translation==='translating'?'등록된 한국어 지명을 확인하고 있어요…':translation==='offline'?'한국어 지명 조회에 연결하지 못해 영어·원어 이름을 유지해요.':null;
 return notice?<div className="map-language-note" role="status">{notice}</div>:null;
}
