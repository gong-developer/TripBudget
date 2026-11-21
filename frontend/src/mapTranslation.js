import {api} from './api.js';
import {englishLabel,koreanLabelExpression} from './mapStyle.js';

// Update text expressions in place, keeping Leaflet overlays and camera intact.
export function attachMapTranslation(map,signal,onStatus){
 const translated={},attempted=new Set();
 let timer=null,busy=false,retryAfter=0,disposed=false;
 const schedule=()=>{
  clearTimeout(timer);
  if(!disposed&&!signal.aborted)timer=setTimeout(update,500);
 };
 async function update(){
  if(disposed||signal.aborted||busy||!map.isStyleLoaded())return;
  if(Date.now()<retryAfter){timer=setTimeout(update,retryAfter-Date.now());return;}
  const layers=map.getStyle().layers.filter(layer=>layer.type==='symbol'&&layer.layout?.['text-field']);
  const names=[];
  for(const feature of map.queryRenderedFeatures({layers:layers.map(layer=>layer.id)})){
   const properties=feature.properties||{};
   if(properties['name:ko']||properties.name_ko)continue;
   const name=englishLabel(properties);
   if(name&&name.length<=128&&!attempted.has(name)&&!names.includes(name))names.push(name);
   if(names.length>=24)break;
  }
  if(!names.length)return;
  busy=true;onStatus('translating');
  try{
   const result=await api('map/translate',{names},signal);
   if(disposed||signal.aborted)return;
   const changed=Object.entries(result.translations).some(([name,value])=>translated[name]!==value);
   Object.assign(translated,result.translations);
   // Bound expression size during long sessions.
   for(const name of Object.keys(translated).slice(0,-1000)){delete translated[name];attempted.delete(name);}
   if(result.available)names.forEach(name=>attempted.add(name));
   else {
    Object.keys(result.translations).forEach(name=>attempted.add(name));
    retryAfter=Date.now()+30000;
   }
   if(changed){
    const expression=koreanLabelExpression(translated);
    for(const layer of layers)map.setLayoutProperty(layer.id,'text-field',expression);
   }
   onStatus(result.available?'ready':'offline');
  }catch(error){
   if(error.name!=='AbortError'&&!disposed){retryAfter=Date.now()+30000;onStatus('offline');}
  }finally{
   busy=false;
   if(!disposed&&!signal.aborted)schedule();
  }
 }
 map.on('idle',schedule);
 schedule();
 return ()=>{disposed=true;clearTimeout(timer);map.off('idle',schedule);};
}
