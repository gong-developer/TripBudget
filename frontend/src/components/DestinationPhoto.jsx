import {useEffect,useRef,useState} from 'react';
import {api} from '../api';
import {destinationLabel} from '../destinationLabel';

const photos=new Map();
function loadPhoto(cityName){
 const cached=photos.get(cityName);
 if(cached&&cached.until>Date.now())return cached.request;
 const entry={until:Date.now()+300000,request:null};
 entry.request=api(`destination-photo?cityName=${encodeURIComponent(cityName)}`)
  .then(data=>{entry.until=Date.now()+(data.photo?3600000:300000);return data.photo||null})
  .catch(()=>null);
 photos.set(cityName,entry);
 if(photos.size>256)photos.delete(photos.keys().next().value);
 return entry.request;
}

function Photo({city,compact}){
 const frame=useRef(null);
 const [ready,setReady]=useState(false),[photo,setPhoto]=useState(null),[failed,setFailed]=useState(false);
 useEffect(()=>{
  let active=true,observer;
  const load=()=>loadPhoto(city.cityName).then(value=>{if(active){setPhoto(value);setReady(true)}});
  if(typeof IntersectionObserver==='undefined')load();
  else{
   observer=new IntersectionObserver(entries=>{
    if(entries.some(entry=>entry.isIntersecting)){observer.disconnect();load()}
   },{rootMargin:'120px'});
   observer.observe(frame.current);
  }
  return()=>{active=false;observer?.disconnect()};
 },[city.cityName]);
 const available=photo&&!failed;
 return <figure ref={frame} className={'destination-photo'+(compact?' destination-photo-compact':' destination-photo-hero')}>
  <div className="destination-photo-frame">
   {available?<img src={photo.url} alt={`${destinationLabel(city)} · ${photo.title}`} loading="lazy" decoding="async" referrerPolicy="no-referrer" onError={()=>setFailed(true)}/>:<div className="destination-photo-placeholder"><span aria-hidden="true">▧</span><small>{ready?'사진을 표시할 수 없어요':'사진 불러오는 중'}</small></div>}
   {!compact&&<span className="destination-photo-label">{destinationLabel(city)}{available&&photo.subjectType==='sight'&&<small>{photo.title}</small>}</span>}
  </div>
  {available&&<figcaption><a href={photo.sourceUrl} target="_blank" rel="noreferrer" title={`${photo.title} · ${photo.author} · ${photo.license}`}>
   {photo.authorUrl?`${photo.source} ↗`:`${photo.author} · ${photo.source} ↗`}
  </a>{photo.authorUrl&&<> · <a href={photo.authorUrl} target="_blank" rel="noreferrer">{photo.author}</a></>} · {photo.licenseUrl?<a href={photo.licenseUrl} target="_blank" rel="noreferrer">{photo.license}</a>:photo.license}{!compact&&<span>{photo.subjectType==='sight'?'선택 지역 안의 명소 사진 · 화면에 맞게 잘라 표시':'화면에 맞게 잘라 표시한 지역 사진'}</span>}</figcaption>}
 </figure>;
}

export default function DestinationPhoto({city,compact=false}){
 return <Photo key={city.cityName} city={city} compact={compact}/>;
}
