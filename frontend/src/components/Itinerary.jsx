import { destinationLabel,isKoreanLabel } from '../destinationLabel';
import { itineraryDays } from '../itineraryData';
import {useEffect,useState} from 'react';

export default function Itinerary({city,days,loading,result,error,onRetry,onCancel}) {
 const [elapsed,setElapsed]=useState(0);
 useEffect(()=>{
  setElapsed(0);
  if(!loading)return;
  const started=Date.now(),timer=setInterval(()=>setElapsed(Math.floor((Date.now()-started)/1000)),1000);
  return()=>clearInterval(timer);
 },[loading]);
 if(!city)return null;
 const text=(result?.text||'').replace(/\bDAY\s*(\d+)\b/gi,'$1일차');
 const cards=itineraryDays(text);
 const hasCards=cards.length>0&&cards.every(day=>day.slots.length>0);
 const notes=text.split('\n').filter(line=>line.startsWith('• ')).map(line=>line.slice(2));
 return <section className="panel itinerary" aria-busy={loading}>
  <div className="eyebrow">나만의 여행 일정</div>
  <div className="feature-heading my-4"><h2>{destinationLabel(city)} · {days}일 여행</h2>{result&&<span className="badge">{result.source==='demo'?'샘플 일정 · AI 생성 아님':'✦ AI 생성 일정'}</span>}</div>
  <p className="muted mb-5">{city.destinationType==='region'?`${destinationLabel(city)} 지역의 명소를 골라 여행 동선으로 연결해요.`:(city.recommendedPlaces||[]).filter(isKoreanLabel).join(' · ')||destinationLabel(city)}</p>
  {city.nameTranslationNotice&&<p className="muted mb-5">원어 도시명: {city.originalName} · {city.nameTranslationNotice}</p>}
  {!loading&&!result&&!error&&<div><p className="muted mb-4">실제 명소 목록을 확인하고, 추천 이유·체류 시간·식사와 휴식이 담긴 일정을 만들어요. 같은 조건의 일정은 저장된 결과를 재사용해요.</p><button className="primary-action" onClick={onRetry}>{city.destinationType==='region'?'이 지역으로 AI 일정 만들기':'AI 일정 만들기'} <span aria-hidden="true">✦</span></button></div>}
  {loading&&<div><p role="status" className="pulse">✦ 실제 명소를 확인하고 날짜별 여행 일정을 만들고 있어요…</p><p className="muted text-sm mt-2">{elapsed}초 경과{elapsed>=15?' · 응답이 지연되고 있어요. 완료되면 자동으로 표시돼요.':''}</p><button className="secondary mt-4" onClick={onCancel}>생성 취소</button></div>}
  {error&&<div role="alert"><p className="error">{error}</p><button className="secondary mt-4" onClick={onRetry}>일정 생성 다시 시도</button></div>}
  {result&&<>
   <div className="itinerary-actions"><button className="secondary" onClick={onRetry} disabled={loading}>일정 다시 만들기</button><span className="muted">새 일정을 생성해 방문 구성을 바꿔볼 수 있어요.</span></div>
   {hasCards?<div className="day-grid">{cards.map(day=><article className="day-card" key={day.day}><div className="day-heading"><span>{String(day.day).padStart(2,'0')}</span><div><h3>{day.day}일차</h3>{day.title&&<p>{day.title}</p>}</div></div><ol>{day.slots.map((slot,i)=><li key={i}><span className="time-label">{slot.start?`${slot.start} · ${slot.stay}`:slot.period}</span>{slot.start?<><h4 className="visit-name">{slot.place}</h4><p>{slot.activity}</p><p className="visit-reason"><strong>추천 이유</strong> {slot.reason}</p><p className="visit-tip"><strong>방문 팁</strong> {slot.tip}</p><small className="visit-transfer">{slot.transfer}</small></>:<p>{slot.text}</p>}</li>)}</ol>{day.meals&&<div className="day-practical"><strong>식사 제안</strong><p>{day.meals}</p></div>}{day.rest&&<div className="day-practical"><strong>휴식</strong><p>{day.rest}</p></div>}</article>)}</div>:<p className="typewriter">{text}</p>}
   {notes.length>0&&<ul className="itinerary-notes">{notes.map((note,index)=><li key={index}>{note}</li>)}</ul>}
   <p className="muted text-sm mt-5">방문 시각과 체류 시간은 추천 계획이며, 실제 운영시간과 교통편은 방문 전에 확인해주세요.</p>
  </>}
 </section>;
}
