import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import TravelMap from './components/TravelMap';
import Itinerary from './components/Itinerary';

const won = n => n.toLocaleString('ko-KR')+'원';
export default function App(){
 const [mode,setMode]=useState('A'),[budget,setBudget]=useState(''),[allCities,setAllCities]=useState([]);
 const [cities,setCities]=useState([]),[selected,setSelected]=useState(null),[flight,setFlight]=useState(null);
 const [loading,setLoading]=useState(false),[aiLoading,setAiLoading]=useState(false),[result,setResult]=useState(null);
 const [error,setError]=useState(''),[aiError,setAiError]=useState(''),[status,setStatus]=useState('여행 예산을 입력해주세요.');
 const [health,setHealth]=useState(null),[boot,setBoot]=useState(0),[celebrate,setCelebrate]=useState(null);
 const generation=useRef(0),recommendRequest=useRef(null),aiRequest=useRef(null),flightRef=useRef(null),busyRef=useRef(false);
 const chosenBudget=useRef(0);
 useEffect(()=>{
  const controller=new AbortController();setError('');
  Promise.all([api('cities',null,controller.signal),api('health',null,controller.signal)])
   .then(([data,state])=>{setAllCities(data);setHealth(state)})
   .catch(e=>{if(e.name!=='AbortError')setError(e.message)});
  return ()=>controller.abort();
 },[boot]);
 useEffect(()=>()=>{recommendRequest.current?.abort();aiRequest.current?.abort()},[]);
 function reset(next='A'){
  generation.current++;recommendRequest.current?.abort();aiRequest.current?.abort();
  busyRef.current=false;flightRef.current=null;
  setMode(next);setCities([]);setSelected(null);setFlight(null);setLoading(false);setAiLoading(false);
  setResult(null);setAiError('');setCelebrate(null);
  setStatus(next==='A'?'여행 예산을 입력해주세요.':'예산과 상관없이, 우연이 고르는 여행!');
 }
 async function generate(city,amount){
  aiRequest.current?.abort();const controller=new AbortController();aiRequest.current=controller;
  const token=generation.current;
  setSelected(city);setResult(null);setAiError('');setAiLoading(true);chosenBudget.current=amount;
  try{
   const data=await api('generate-itinerary',{cityName:city.cityName,budget:amount},controller.signal);
   if(token===generation.current&&!controller.signal.aborted)setResult(data);
  }catch(e){if(!controller.signal.aborted&&token===generation.current)setAiError(e.message)}
  finally{if(!controller.signal.aborted&&token===generation.current)setAiLoading(false)}
 }
 async function recommend(event){
  event.preventDefault();
  const raw=budget.trim(),amount=Number(raw.replaceAll(',',''));
  if(!/^(?:\d+|\d{1,3}(?:,\d{3})+)$/.test(raw)||!Number.isSafeInteger(amount)||amount<=0||amount>100000000){
   setError('예산은 1원부터 1억원까지 숫자로 입력해주세요.');return;
  }
  reset('A');setError('');setLoading(true);chosenBudget.current=amount;
  const controller=new AbortController();recommendRequest.current=controller;const token=generation.current;
  try{
   const data=await api('recommend',{budget:amount},controller.signal);
   if(token!==generation.current||controller.signal.aborted)return;
   setCities(data.cities);
   setStatus(data.message+' 후보 비용 합계 '+won(data.totalCost)+' · 만족도 합계 '+data.totalSatisfaction+'점');
  }catch(e){if(!controller.signal.aborted)setError(e.message)}
  finally{if(token===generation.current)setLoading(false)}
 }
 function throwDart(){
  if(busyRef.current||!allCities.length)return;
  reset('B');busyRef.current=true;
  const city=allCities[Math.floor(Math.random()*allCities.length)];
  const next={id:generation.current,city};
  flightRef.current=next;setFlight(next);setStatus('펜이 날아갑니다… 어디에 도착할까요?');
 }
 function land(active){
  if(flightRef.current!==active||active.id!==generation.current)return;
  flightRef.current=null;busyRef.current=false;setFlight(null);setCities([active.city]);setCelebrate(active.id);
  setStatus('🎉 '+active.city.cityName+' 당첨! 아래에서 AI 일정을 확인하세요.');
  generate(active.city,active.city.estimatedCost);
 }
 return <><header className="topbar">
  <a className="brand" href="#" onClick={e=>e.preventDefault()}>Trip<span>Budget</span><small>AI SW · TRAVEL LAB</small></a>
  <nav className="flex gap-2" aria-label="추천 모드">
   <button className={mode==='A'?'active':'secondary'} aria-pressed={mode==='A'} onClick={()=>reset('A')}>A · 예산 맞춤</button>
   <button className={mode==='B'?'active':'secondary'} aria-pressed={mode==='B'} onClick={()=>reset('B')}>B · 랜덤 다트</button>
  </nav>
  <button className="secondary" onClick={()=>{reset();setBudget('');setError('');window.scrollTo({top:0})}}>↺ 처음으로</button>
 </header><main>
  <div className="flex flex-wrap justify-between gap-3"><p className="eyebrow">YOUR NEXT DESTINATION</p>
   <span className="muted text-sm">{health?(health.demoMode?'● 샘플 시연 모드':health.aiConfigured?'● AI 연결 준비됨':'● API 키 설정 필요'):'서버 연결 확인 중'}</span></div>
  <h1>{mode==='A'?'내 예산으로 어디까지 갈까?':'운명이 고르는 다음 여행지!'}</h1>
  <p className="muted mb-7">{mode==='A'?'예산 안에서 최적의 도시 조합을 찾고, AI가 3일 여행을 계획해요.':'지도에 펜을 던져 목적지를 정하면 AI가 여행 계획을 만들어줘요.'}</p>
  <section className="panel">
   {mode==='A'?<form onSubmit={recommend}>
    <label htmlFor="budget" className="block font-bold mb-3">여행 예산</label>
    <div className="flex flex-col md:flex-row gap-3"><input id="budget" inputMode="numeric" placeholder="예: 1,500,000" value={budget} maxLength={15} onChange={e=>setBudget(e.target.value)} aria-describedby="budget-help"/>
    <button className="active" disabled={loading}>{loading?'최적 조합 계산 중…':'추천받기 →'}</button></div>
    <p id="budget-help" className="muted text-sm mt-3">후보 최대 3곳의 비용 합계 ≤ 입력 예산 · 후보 중 한 곳을 선택하세요. 경비는 1인 3일 기준 시연용 추정치입니다.</p>
   </form>:<><button className="dart-button" disabled={!!flight||!allCities.length} onClick={throwDart}>{flight?'✈ 목적지로 날아가는 중…':'🎯 지도에 펜 던지기'}</button><p className="muted text-sm mt-3">랜덤 모드는 당첨 도시의 예상 경비를 일정 예산으로 사용합니다.</p></>}
  </section>
  {error&&<div className="error my-4" role="alert">{error}{!health&&<button className="secondary ml-4" onClick={()=>setBoot(n=>n+1)}>서버 다시 연결</button>}</div>}
  <p className="my-5 font-bold" role="status">{status}</p>
  <TravelMap cities={cities} flight={flight} onLand={land} celebrate={celebrate} onSelect={city=>generate(city,mode==='A'?chosenBudget.current:city.estimatedCost)}/>
  <div className="grid md:grid-cols-3 gap-4 mt-5">{cities.map(city=><button key={city.cityName} className={'city-card '+(selected?.cityName===city.cityName?'selected':'')} onClick={()=>generate(city,mode==='A'?chosenBudget.current:city.estimatedCost)}>
    <span className="text-xl font-black">{city.cityName}</span><span className="price">{won(city.estimatedCost)}</span><span className="muted text-sm">만족도 {city.satisfaction}점 · AI 일정 보기 →</span>
  </button>)}</div>
  <Itinerary city={selected} loading={aiLoading} result={result} error={aiError} onRetry={()=>generate(selected,chosenBudget.current)}/>
  <footer>AI 일정과 경비는 참고용이며 실제 가격·운영시간은 방문 전에 확인해주세요. 지도와 AI 생성에는 인터넷 연결이 필요합니다.</footer>
 </main></>;
}
