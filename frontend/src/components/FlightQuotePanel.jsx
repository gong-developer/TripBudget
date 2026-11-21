import {useEffect,useRef,useState} from 'react';
import {api} from '../api';
import CostBreakdown from './CostBreakdown';

const won=value=>value.toLocaleString('ko-KR')+'원';
const airportLabel=airport=>`${airport.code} · ${airport.name}${airport.distanceKm!=null?` · 약 ${airport.distanceKm}km`:''}`;
function returnDate(departure,days){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(departure))return '';
 const date=new Date(departure+'T00:00:00Z');
 if(!Number.isFinite(date.getTime()))return '';
 date.setUTCDate(date.getUTCDate()+days-1);return date.toISOString().slice(0,10);
}
function FlightLeg({label,segments}){
 return <div className="flight-leg"><strong>{label}</strong>{segments.map((segment,index)=><p key={index}>{segment.airline} {segment.flightNumber}<br/><span>{segment.departureAirport} {segment.departureTime} → {segment.arrivalAirport} {segment.arrivalTime}</span></p>)}</div>;
}
export default function FlightQuotePanel({city,settings,days,budget,onApply,disabled}){
 const [options,setOptions]=useState(null),[optionsError,setOptionsError]=useState(''),[attempt,setAttempt]=useState(0);
 const [departure,setDeparture]=useState(''),[arrival,setArrival]=useState(''),[date,setDate]=useState(settings.departureDate||'');
 const [loading,setLoading]=useState(false),[error,setError]=useState('');
 const search=useRef(null),busy=useRef(false),resultArea=useRef(null);
 const end=returnDate(date,days),quote=city.costBreakdown?.flightQuote;
 useEffect(()=>{
  const controller=new AbortController();setOptionsError('');
  api(`flights/options?${new URLSearchParams({cityName:city.cityName,origin:settings.origin})}`,null,controller.signal)
   .then(data=>{if(controller.signal.aborted)return;setOptions(data);setDeparture(data.departureDefault);setArrival(data.arrivalDefault)})
   .catch(error=>{if(!controller.signal.aborted)setOptionsError(error.message)});
  return()=>controller.abort();
 },[city.cityName,settings.origin,attempt]);
 useEffect(()=>()=>search.current?.abort(),[]);
 async function lookup(event){
  event.preventDefault();if(busy.current||disabled)return;
  busy.current=true;const controller=new AbortController();search.current=controller;setLoading(true);setError('');
  try{
   const data=await api('flights/search',{...settings,themes:settings.themes,days,cityName:city.cityName,departureAirport:departure,arrivalAirport:arrival,departureDate:date},controller.signal);
   if(controller.signal.aborted)return;
   onApply(data.costBreakdown,city.cityName);
   requestAnimationFrame(()=>resultArea.current?.scrollIntoView({block:'start',behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'}));
  }catch(error){if(!controller.signal.aborted)setError(error.message)}
  finally{if(!controller.signal.aborted){busy.current=false;setLoading(false)}}
 }
 const today=new Date(Date.now()+9*3600000).toISOString().slice(0,10);
 return <section className="panel flight-quote-panel" aria-label="선택 지역 항공권 가격" aria-busy={loading}>
  <div className="feature-heading"><div><p className="eyebrow">FLIGHT PRICE CHECK</p><h2>선택한 지역의 항공권 가격 확인</h2></div></div>
  <p className="flight-quote-help">추천은 예상 경비 기준입니다. 여기서 조회하면 선택한 지역의 항공료와 총경비만 다시 계산해요.</p>
  {!options&&!optionsError&&<p className="muted" role="status">출발·도착 공항을 확인하고 있어요…</p>}
  {optionsError&&<div role="alert"><p className="error">{optionsError}</p><button type="button" className="secondary" onClick={()=>setAttempt(value=>value+1)}>공항 다시 확인</button></div>}
  {options&&<>
   {!options.configured&&<p className="muted" role="status">현재 항공권 가격 조회를 사용할 수 없어요. 예상 경비 또는 직접 입력한 교통비를 이용해주세요. <button type="button" className="secondary" onClick={()=>setAttempt(value=>value+1)}>연결 다시 확인</button></p>}
   <form onSubmit={lookup}>
    <fieldset disabled={loading||disabled||!options.configured||days<2} className="flight-quote-fields">
     <label>출발 공항<select value={departure} onChange={event=>setDeparture(event.target.value)} required aria-label="항공권 출발 공항">{options.departureAirports.map(airport=><option key={airport.code} value={airport.code}>{airportLabel(airport)}</option>)}</select></label>
     <label>도착 공항<select value={arrival} onChange={event=>setArrival(event.target.value)} required aria-label="항공권 도착 공항"><option value="">공항을 선택해주세요</option>{options.arrivalAirports.map(airport=><option key={airport.code} value={airport.code}>{airportLabel(airport)}</option>)}</select></label>
     <label>출발일<input type="date" min={today} max="2100-12-18" value={date} onChange={event=>setDate(event.target.value)} required aria-label="항공권 출발일"/></label>
     <label>귀국일<input type="date" value={end} readOnly aria-label="항공권 귀국일"/><small>{days}일 여행 기준으로 계산해요.</small></label>
    </fieldset>
    <p className="flight-quote-help">공항 거리 표시는 직선거리이며, 이동 교통비와 항공편 운항 여부를 뜻하지 않아요. 도착 공항을 확인해주세요.</p>
    {days<2&&<p className="muted">왕복 항공권 조회는 2일 이상 여행에서 사용할 수 있어요.</p>}
    {!options.arrivalAirports.length&&<p className="muted">이 지역의 국가에서 선택 가능한 공항을 찾지 못했어요. 직접 확인한 왕복 교통비를 입력해주세요.</p>}
    <button type="submit" className="primary-action" disabled={loading||disabled||!options.configured||!date||!arrival||!departure||departure===arrival||days<2}>{loading?'출국·귀국 항공편 확인 중…':'항공권 가격 확인'}</button>
    <p className="flight-quote-help">1인·이코노미·왕복 검색입니다. 새 조건 조회는 최대 2회 외부 검색을 사용하고, 같은 조건은 잠시 재사용해요. 성공할 때만 경비가 변경돼요.</p>
   </form>
  </>}
  {error&&<p className="error mt-3" role="alert">{error}</p>}
  {city.savedFlightQuote&&!quote&&<p className="flight-quote-help">저장 당시 1인 항공료 {won(city.savedFlightQuote.pricePerPerson)}가 직접 입력 가격으로 복원됐어요. 현재 판매가는 다시 조회해주세요.</p>}
  {quote&&<div className="flight-quote-result" ref={resultArea}>
   <p className="eyebrow">항공료 반영 완료</p><h3>1인 왕복 검색가 {won(quote.pricePerPerson)}</h3>
   <p>{quote.departureAirport} ↔ {quote.arrivalAirport} · {quote.departureDate} ~ {quote.returnDate}</p>
   <p className="flight-quote-help">조회 시각 {new Date(quote.queriedAt).toLocaleString('ko-KR')} · Google Flights / SerpApi 검색 결과 · 캐시가 사용될 수 있어요.</p>
   <div className="flight-legs"><FlightLeg label="출국편" segments={quote.outbound}/><FlightLeg label="귀국편" segments={quote.inbound}/></div>
   {settings.people>1&&<p className="flight-quote-help">{settings.people}명 항공료는 1인 검색가 × {settings.people}명으로 추정합니다. 전원 동일 요금과 잔여 좌석은 확인하지 않았어요.</p>}
   <p className="flight-quote-help">공항↔여행지 추가 이동, 위탁 수하물·좌석 지정·결제 수수료는 별도 확인이 필요해요. 항공편 도착 시각에 따라 실제 여행 일정도 조정해주세요.</p>
   <a className="flight-source-link" href={quote.searchUrl} target="_blank" rel="noopener noreferrer">Google Flights에서 확인 ↗</a>
   <CostBreakdown city={city} budget={budget}/>
  </div>}
 </section>;
}
