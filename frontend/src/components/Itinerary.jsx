import { useEffect, useState } from 'react';
import { useReducedMotion } from 'framer-motion';
export default function Itinerary({city,loading,result,error,onRetry}) {
 const [count,setCount]=useState(0);
 const reduce=useReducedMotion();
 const text=result?.text || '';
 useEffect(()=>{
  setCount(0);
  if(!text || reduce)return;
  const timer=setInterval(()=>setCount(n=>Math.min(n+5,text.length)),18);
  const stop=setTimeout(()=>clearInterval(timer),Math.ceil(text.length/5)*18+30);
  return ()=>{clearInterval(timer);clearTimeout(stop)};
 },[text,reduce]);
 if(!city)return null;
 return <section className="panel itinerary" aria-busy={loading}>
   <div className="eyebrow">YOUR PERSONAL TRAVEL PLAN</div>
   <div className="flex flex-wrap items-center justify-between gap-4 my-4">
     <h2 className="text-3xl font-black">{city.cityName} · 3일 여행</h2>
     {result && <span className="badge">{result.source==='demo'?'샘플 일정 · AI 생성 아님':'✦ AI 생성 일정'}</span>}
   </div>
   <p className="muted mb-5">{city.recommendedPlaces.join(' · ')}</p>
   {loading && <p role="status" className="pulse">✦ AI가 여행 동선과 예산을 계획하고 있어요…</p>}
   {error && <div role="alert"><p className="error">{error}</p><button className="secondary mt-4" onClick={onRetry}>일정 생성 다시 시도</button></div>}
   {result && <>
     <div className="sr-only" aria-live="polite">{text}</div>
     <p className="typewriter" aria-hidden="true">{reduce?text:text.slice(0,count)}{!reduce&&count<text.length?'▍':''}</p>
     {!reduce&&count<text.length&&<button className="secondary mt-4" onClick={()=>setCount(text.length)}>전체 일정 바로 보기</button>}
   </>}
 </section>;
}
