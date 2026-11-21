import { useEffect, useMemo, useRef, useState } from 'react';
import { api,compareDestinations } from './api';
import TravelMap from './components/TravelMap';
import Itinerary from './components/Itinerary';
import TripSettings,{defaultSettings} from './components/TripSettings';
import {themeLabel,selectedThemes} from './travelThemes';
import DestinationList from './components/DestinationList';
import CostDialog from './components/CostDialog';
import { destinationLabel,destinationRegion,isKoreanLabel,NAME_POLICY } from './destinationLabel';
import { parseBudget } from './budget';
import {groupDestinations,refreshDestinationGroup} from './destinationGroups';
import {readPlans,writePlans,importPlans,planIdentity} from './savedPlans';
import SavedPlansDialog from './components/SavedPlansDialog';
import SaveToast from './components/SaveToast';
import ListRouletteDialog from './components/ListRouletteDialog';
import FlightQuotePanel from './components/FlightQuotePanel';
import PlaceExplorer from './components/PlaceExplorer';
import SearchProgress from './components/SearchProgress';
import CountryPicker from './components/CountryPicker';
import ResultsTabs from './components/ResultsTabs';
import DestinationPhoto from './components/DestinationPhoto';
import {usePlannerNavigation} from './usePlannerNavigation';

const won = n => n.toLocaleString('ko-KR')+'원';
const EMPTY_PLACES=[];
const EMPTY_COUNTRIES=[];
export default function App(){
 const [mode,setMode]=useState('A'),[budget,setBudget]=useState('');
 const {page,navigate,backToSearch}=usePlannerNavigation();
 const [resultTab,setResultTab]=useState('destinations');
 const [listRouletteCities,setListRouletteCities]=useState(null);
 const parsedBudget=parseBudget(budget);
 const [{cities,groups:destinationGroups},setCandidates]=useState({cities:[],groups:[]});
 const [selected,setSelected]=useState(null),[flight,setFlight]=useState(null);
 function setCities(next){setCandidates({cities:next,groups:groupDestinations(next)})}
 const visibleCities=useMemo(()=>destinationGroups.flatMap(group=>group.cities),[destinationGroups]);
 const [mapFocus,setMapFocus]=useState(null);
 const [roulettePending,setRoulettePending]=useState(false);
 const [costCity,setCostCity]=useState(null);
 const [flightCosts,setFlightCosts]=useState({});
 const withFlightCost=city=>flightCosts[city.cityName]?{...city,estimatedCost:flightCosts[city.cityName].total,costBreakdown:flightCosts[city.cityName]}:city;
 const [loading,setLoading]=useState(false),[aiLoading,setAiLoading]=useState(false),[result,setResult]=useState(null);
 const [error,setError]=useState(''),[aiError,setAiError]=useState(''),[status,setStatus]=useState('여행 예산을 입력해주세요.');
 const [health,setHealth]=useState(null),[boot,setBoot]=useState(0),[celebrate,setCelebrate]=useState(null);
 const generation=useRef(0),recommendRequest=useRef(null),aiRequest=useRef(null),flightRef=useRef(null),busyRef=useRef(false);
 const chosenBudget=useRef(0),selectedNameRef=useRef(null);
 selectedNameRef.current=selected?.cityName;
 const [days,setDays]=useState(3);
 const [phase,setPhase]=useState(''),[results,setResults]=useState({});
 const [savedPlans,setSavedPlans]=useState(()=>readPlans()),[planNotice,setPlanNotice]=useState('');
 const [saveNotice,setSaveNotice]=useState(null),[savedPlansOpen,setSavedPlansOpen]=useState(false);
 const dismissSaveNotice=useMemo(()=>()=>setSaveNotice(null),[]);
 const [nearby,setNearby]=useState(null),[nearbyLoading,setNearbyLoading]=useState(false),[nearbyError,setNearbyError]=useState('');
 const [details,setDetails]=useState(null),[detailsLoading,setDetailsLoading]=useState(false),[detailsError,setDetailsError]=useState('');
 const extrasRequests=useRef({});
 const [settings,setSettings]=useState(defaultSettings);
 const tripOptions={...settings,themes:selectedThemes(settings),departureDate:settings.departureDate||null,days};
 const [category,setCategory]=useState('all');
 const [countryCode,setCountryCode]=useState(''),[countryData,setCountryData]=useState(null),[countryError,setCountryError]=useState('');
 const countries=useMemo(()=>countryData?countryData.features.map(feature=>feature.properties).sort((a,b)=>a.name.localeCompare(b.name,'ko')):EMPTY_COUNTRIES,[countryData]);
 const selectedCountry=countries.find(country=>country.code===countryCode)||null;
 const categories=[['all','전체'],['domestic','국내'],['international','해외']];
 const resultsPage=page==='results'&&cities.length>0;
 useEffect(()=>{if(page==='results'&&!cities.length)navigate('search',{replace:true})},[page,cities.length,navigate]);
 useEffect(()=>{
  setCostCity(null);
  document.getElementById(resultsPage?'results-title':'search-title')?.focus({preventScroll:true});
  window.scrollTo({top:0,left:0,behavior:'auto'});
 },[resultsPage]);
 useEffect(()=>{
  if(!resultsPage)return;
  const tabsStart=document.getElementById('results-tabs-start');
  if(tabsStart?.getBoundingClientRect().top<0)tabsStart.scrollIntoView({block:'start'});
  if(document.activeElement?.closest('.destination-select'))document.getElementById(`result-panel-${resultTab}`)?.focus({preventScroll:true});
 },[resultsPage,resultTab]);
 useEffect(()=>{
  const controller=new AbortController();setError('');
  api('health',null,controller.signal)
   .then(state=>setHealth(state))
   .catch(e=>{if(e.name!=='AbortError')setError(e.message)});
  return ()=>controller.abort();
 },[boot]);
 useEffect(()=>{
  const controller=new AbortController();setCountryError('');
  api('countries?v=travel-policy-20261104',null,controller.signal).then(data=>{if(!controller.signal.aborted)setCountryData(data)}).catch(e=>{if(!controller.signal.aborted)setCountryError(e.message)});
  return()=>controller.abort();
 },[boot]);
 useEffect(()=>()=>{recommendRequest.current?.abort();aiRequest.current?.abort();Object.values(extrasRequests.current).forEach(controller=>controller.abort())},[]);
 useEffect(()=>{
  if(selected&&!nearby&&!nearbyLoading&&!nearbyError)loadNearby();
 },[selected?.cityName,nearby,nearbyLoading,nearbyError]);
 function clearExtras(){
  setCostCity(null);
  setMapFocus(null);
  Object.values(extrasRequests.current).forEach(controller=>controller.abort());extrasRequests.current={};
  setNearby(null);setDetails(null);setNearbyError('');setDetailsError('');
  setNearbyLoading(false);setDetailsLoading(false);
 }
 function selectCity(city,{showDetails=true}={}){
  if(loading||flight)return;
  if(showDetails){setResultTab('places');navigate('results')}
  if(selected?.cityName===city.cityName){setMapFocus({...city,zoom:10});return;}
  generation.current++;aiRequest.current?.abort();setAiLoading(false);clearExtras();
  setMapFocus({...city,zoom:10});
  setSelected(withFlightCost(city));setResult(results[city.cityName]||null);setAiError('');setPlanNotice('');
  if(mode==='B')chosenBudget.current=city.estimatedCost;
 }
 function refreshGroup(lower){
  if(mode!=='A'||loading||flight||aiLoading)return;
  const groups=refreshDestinationGroup(destinationGroups,cities,lower);
  if(groups===destinationGroups)return;
  setCandidates({cities,groups});
  if(selected&&!groups.some(group=>group.cities.some(city=>city.cityName===selected.cityName))){
   generation.current++;aiRequest.current?.abort();clearExtras();
   setSelected(null);setResult(null);setAiError('');setPlanNotice('');setResultTab('destinations');
  }
  setStatus(`${(lower/10000).toLocaleString('ko-KR')}만원 이상 ~ ${((lower+500000)/10000).toLocaleString('ko-KR')}만원 미만 여행지를 새로 추천했어요.`);
 }
 function selectCountry(code){
  if(code===countryCode)return;
  reset(mode);setCountryCode(code);setCategory(code?(code==='kr'?'domestic':'international'):'all');setError('');
  const country=countries.find(item=>item.code===code);
  setStatus(country?`${country.name} 선택 완료! 여행 조건을 고르고 여행지를 찾아보세요.`:'국가 선택을 해제했어요. 전체 범위에서 여행지를 추천해요.');
 }
 function reset(next='A'){
  setFlightCosts({});
  setListRouletteCities(null);
  navigate('search',{replace:true});setResultTab('destinations');
  generation.current++;recommendRequest.current?.abort();aiRequest.current?.abort();
  busyRef.current=false;flightRef.current=null;setRoulettePending(false);
  clearExtras();setResults({});setPhase('');setPlanNotice('');
  setMode(next);setCities([]);setSelected(null);setFlight(null);setLoading(false);setAiLoading(false);
  setResult(null);setAiError('');setCelebrate(null);
  setStatus(next==='A'?'여행 예산을 입력해주세요.':'예산 제한 없이, 우연이 고르는 여행!');
 }
 async function updateSettings(next,nextDays=days){
  setSettings(next);setError('');
  if(page==='search'||!cities.length){reset(mode);setStatus('변경한 조건으로 여행지를 다시 찾아보세요.');return;}
  if(mode==='A'){reset(mode);await throwDart(null,{...next,days:nextDays,departureDate:next.departureDate||null});return;}
  generation.current++;recommendRequest.current?.abort();aiRequest.current?.abort();
  clearExtras();setResults({});setPhase('');
  const token=generation.current,controller=new AbortController();recommendRequest.current=controller;
  setResult(null);setAiLoading(false);setLoading(true);setAiError('');
  const options={...next,days:nextDays,departureDate:next.departureDate||null};
  try{
   const updated=await Promise.all(cities.map(async city=>{
    const cost=await api('estimate',{cityName:city.cityName,...options},controller.signal);
    return {...city,estimatedCost:cost.total,costBreakdown:cost};
   }));
   if(controller.signal.aborted||token!==generation.current)return;
   setCities(updated);
   const active=updated.find(city=>city.cityName===selected?.cityName);
   if(active){setSelected(active);if(mode==='B')chosenBudget.current=active.estimatedCost;}
   setStatus(mode==='A'&&updated.some(city=>city.costBreakdown.high>chosenBudget.current)?'조건 변경 후 예상 상한이 예산을 초과했어요. 예산에 맞춰 다시 뽑아주세요.':'여행지를 유지하고 경비를 다시 계산했어요.');
  }catch(e){if(!controller.signal.aborted&&token===generation.current){setSelected(null);setCities([]);setError(e.message)}}
  finally{if(!controller.signal.aborted&&token===generation.current)setLoading(false)}
 }
 async function generate(city,amount,refresh=false){
  if(aiLoading)return;
  aiRequest.current?.abort();const controller=new AbortController();aiRequest.current=controller;
  const token=generation.current;
  setSelected(city);setResult(null);setAiError('');setAiLoading(true);chosenBudget.current=amount;
  try{
   const data=await api('generate-itinerary',{cityName:city.cityName,budget:amount,...tripOptions,...(city.costBreakdown?.flightQuote?{departureDate:city.costBreakdown.flightQuote.departureDate,transportPerPerson:city.costBreakdown.flightQuote.pricePerPerson}:{}),...(refresh?{refresh:true}:{})},controller.signal);
   if(token===generation.current&&!controller.signal.aborted){setResult(data);setResults(prev=>({...prev,[city.cityName]:data}));}
  }catch(e){if(!controller.signal.aborted&&token===generation.current)setAiError(e.message)}
  finally{if(!controller.signal.aborted&&token===generation.current)setAiLoading(false)}
 }
 async function throwDart(event,options=tripOptions){
  event?.preventDefault();
  if(busyRef.current)return;
  const amount=parsedBudget;
  if(mode==='A'&&amount===null){
   setError('예산은 1원부터 1억원까지 입력해주세요. 예: 500만원, 1.5만원, 5,000,000원');return;
  }
  reset(mode);busyRef.current=true;setLoading(true);setRoulettePending(mode==='B');setError('');
  if(mode==='B')document.getElementById('trip-map')?.scrollIntoView({block:'start',behavior:'auto'});
  chosenBudget.current=mode==='A'?amount:0;setStatus(mode==='A'?won(amount)+' 이내의 여행지를 모두 찾고 있어요…':'룰렛을 돌리고 있어요… 새로운 여행지가 기다리고 있어요!');
  const controller=new AbortController();recommendRequest.current=controller;const token=generation.current;
  try{
   if(mode==='A'){
    setPhase('fetch');
    const compared=await compareDestinations({budget:amount,category,...options,...(countryCode?{countryCode}:{})},controller.signal,next=>{
     if(token!==generation.current||controller.signal.aborted)return;
     setPhase(next);setStatus({fetch:selectedCountry?`${selectedCountry.name} 안의 여행지 후보를 조회하고 있어요…`:'국내·해외 여행지 후보를 조회하고 있어요…',compare:'예상 경비를 계산하고 예산 이하인 후보를 모으고 있어요…',sights:'선택한 여행 기간에 필요한 명소를 확인하고 있어요…',names:'여행지의 표시 이름을 확인하고 있어요…'}[next]||'조회 중…');
    });
    if(token!==generation.current||controller.signal.aborted)return;
    setCities(compared.cities);setSelected(null);setPhase('ready');busyRef.current=false;
    setResultTab('destinations');navigate('results');
    setStatus(`명소가 확인된 예산 이하 후보 ${compared.cities.length}곳을 찾았어요. 50만원 구간별 무작위로 최대 3곳씩 목록과 지도에 표시해요.`);
    return;
   }
   const params=new URLSearchParams({category,...(countryCode?{countryCode}:{}),...(mode==='A'?{budget:amount}:{}),...Object.fromEntries(Object.entries(tripOptions).filter(([key,value])=>value!==null&&key!=='themes'&&key!=='theme'))});
   const chosenThemes=selectedThemes(tripOptions);
   if(chosenThemes.length)chosenThemes.forEach(theme=>params.append('themes',theme));else params.set('themes','');
   let {city}=await api(`destinations/random?${params}`,null,controller.signal);
   if(city.namePolicy!==NAME_POLICY){
    const localized=await api('destinations/display-name',{cityName:city.cityName,lat:city.lat,lng:city.lng,countryCode:city.countryCode||'',category:city.category},controller.signal);
    city={...city,...localized};
   }
   if(token!==generation.current||controller.signal.aborted)return;
   if(mode==='B')chosenBudget.current=city.estimatedCost;
   const next={id:token,city};
   flightRef.current=next;setFlight(next);setStatus('룰렛이 멈추고 있어요… 어떤 여행지가 나올까요?');
  }catch(e){
   if(!controller.signal.aborted&&token===generation.current){busyRef.current=false;setPhase('');setError(e.name==='TimeoutError'?'조회 시간이 초과됐어요. 다시 시도해주세요.':e.message||'서버 연결을 확인해주세요.');setStatus('여행지를 가져오지 못했어요. 다시 시도해주세요.');}
  }finally{if(token===generation.current&&!controller.signal.aborted){setLoading(false);setRoulettePending(false)}}
 }
 function land(active){
  if(flightRef.current!==active||active.id!==generation.current)return;
  flightRef.current=null;busyRef.current=false;setFlight(null);setCities([active.city]);setCelebrate(active.id);
  setMapFocus({...active.city,zoom:active.city.destinationType==='region'?10:4});
  setStatus('🎉 '+destinationLabel(active.city)+' 당첨! 경비를 확인하고 AI 일정을 만들어보세요.');
  setSelected(active.city);setResultTab('destinations');navigate('results');
 }
 async function loadNearby(){
  if(!selected)return;
  extrasRequests.current.nearby?.abort();const controller=new AbortController();extrasRequests.current.nearby=controller;
  const token=generation.current;setNearbyLoading(true);setNearbyError('');
  try{const data=await api('nearby-places',{cityName:selected.cityName},controller.signal);if(token===generation.current&&!controller.signal.aborted){setNearby(data);setMapFocus(null)}}
  catch(e){if(token===generation.current&&!controller.signal.aborted)setNearbyError(e.message)}
  finally{if(token===generation.current&&!controller.signal.aborted)setNearbyLoading(false)}
 }
 async function loadDetails(place){
  setMapFocus({...place,zoom:15});
  extrasRequests.current.details?.abort();
  if(place.source==='한국관광공사 TourAPI'||(typeof place.address==='string'&&place.address.trim())){setDetails(place);setDetailsLoading(false);setDetailsError('');return;}
  const controller=new AbortController();extrasRequests.current.details=controller;
  const token=generation.current;setDetailsLoading(true);setDetailsError('');setDetails(null);
  try{const data=await api('place-details',{placeId:place.placeId||null,lat:place.lat,lng:place.lng},controller.signal);if(token===generation.current&&!controller.signal.aborted)setDetails(data)}
  catch(e){if(token===generation.current&&!controller.signal.aborted)setDetailsError(e.message)}
  finally{if(token===generation.current&&!controller.signal.aborted)setDetailsLoading(false)}
 }
 function applyFlightCost(cost,cityName){
  if(!selected||selectedNameRef.current!==cityName)return;
  setFlightCosts(previous=>({...previous,[selected.cityName]:cost}));
  setSelected(previous=>previous?.cityName===cityName?{...previous,estimatedCost:cost.total,costBreakdown:cost}:previous);
  if(mode==='B')chosenBudget.current=cost.total;
  setPlanNotice('항공권 검색가를 반영해 선택한 지역의 총경비를 다시 계산했어요. 다른 여행지의 추천 조건은 유지됩니다.');
 }
 const selectedQuote=selected?.costBreakdown?.flightQuote||selected?.savedFlightQuote;
 const planSettings=selectedQuote?{...settings,departureDate:selectedQuote.departureDate,transportPerPerson:selectedQuote.pricePerPerson}:settings;
 const currentPlan=selected?{version:1,namePolicy:NAME_POLICY,title:destinationLabel(selected),mode,budget,amount:chosenBudget.current,days,settings:planSettings,flightQuote:selectedQuote,category,countryCode,cities:[selected],selectedName:selected.cityName,result,nearby}:null;
 const planSaved=!!currentPlan&&savedPlans.some(plan=>planIdentity(plan)===planIdentity(currentPlan));
 function savePlan(){
  if(!currentPlan)return;
  try{
   const existing=readPlans();
   if(existing.some(plan=>planIdentity(plan)===planIdentity(currentPlan))){
    setSavedPlans(existing);setSaveNotice({id:Date.now(),duplicate:true,message:`${currentPlan.title} · 저장한 여행 계획에서 확인할 수 있어요.`});return;
   }
   const plan={...currentPlan,id:globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(36).slice(2)}`,savedAt:new Date().toISOString()};
   setSavedPlans(writePlans([plan,...existing]));
   setSaveNotice({id:Date.now(),message:`${plan.title} · 이 브라우저에 보관했어요.`});
  }catch{setSaveNotice({id:Date.now(),error:true,message:'브라우저 저장 공간을 사용할 수 없어요. 기존 계획을 삭제하거나 저장 설정을 확인해주세요.'})}
 }
 function deletePlan(id){
  try{setSavedPlans(writePlans(savedPlans.filter(plan=>plan.id!==id)));setPlanNotice('저장한 계획을 삭제했어요.')}
  catch{setPlanNotice('저장한 계획을 삭제하지 못했어요. 브라우저 저장 설정을 확인해주세요.')}
 }
 async function loadPlan(plan){
  reset(plan.mode);setError('');setLoading(true);const controller=new AbortController();recommendRequest.current=controller;const token=generation.current;
  setStatus('저장한 여행지를 복원하고 현재 조건으로 경비를 확인하고 있어요…');
  try{
   const data=await api('destinations/restore',{...plan.settings,departureDate:plan.settings.departureDate||null,days:plan.days,cities:plan.cities},controller.signal);
   if(token!==generation.current||controller.signal.aborted)return;
   const city=data.cities.find(item=>item.cityName===plan.selectedName)||data.cities[0];
   setBudget(plan.budget||'');setDays(plan.days);setSettings({...defaultSettings,...plan.settings,themes:selectedThemes(plan.settings),style:'standard'});setCategory(plan.category);setCountryCode(plan.countryCode||'');setCities(data.cities);setSelected(plan.flightQuote?{...city,savedFlightQuote:plan.flightQuote}:city);
   chosenBudget.current=plan.mode==='A'?plan.amount:city.estimatedCost;setResult(plan.result||null);setResults(plan.result?{[city.cityName]:plan.result}:{});
   setNearby(plan.nearby||null);setResultTab(plan.result?'itinerary':'places');navigate('results');
   setPhase(plan.mode==='A'?'ready':'');setStatus('저장한 여행 계획을 불러왔어요. 경비는 현재 계산 기준으로 갱신했어요.');setPlanNotice(plan.legacyResult?'기존 일정 원문은 보존했으며 ‘계획 백업’으로 저장할 수 있어요. 이전 자동 번역이 섞일 수 있어 AI 일정을 다시 생성해주세요.':'저장한 일정과 지도를 복원했어요.');
  }catch(e){if(token===generation.current&&!controller.signal.aborted)setError(e.message)}
  finally{if(token===generation.current&&!controller.signal.aborted)setLoading(false)}
 }
 return <><header className={'topbar'+(resultsPage?' topbar-results':'')}>
  <a className="brand" href="#search" onClick={e=>{e.preventDefault();backToSearch()}}><span className="brand-icon" aria-hidden="true"><img src="/trip-budget.svg" alt="" width="58" height="44"/></span>Trip<span>Budget</span></a>
  {resultsPage?<button type="button" className="back-to-search" onClick={backToSearch}><span aria-hidden="true">←</span> 조건·지도</button>:<nav className="flex gap-2" aria-label="추천 모드">
   <button className={mode==='A'?'active':'secondary'} aria-pressed={mode==='A'} onClick={()=>reset('A')}>예산 맞춤</button>
   <button className={mode==='B'?'active':'secondary'} aria-pressed={mode==='B'} onClick={()=>reset('B')}>랜덤 룰렛</button>
  </nav>}
  <div className="topbar-actions"><button type="button" className="saved-plans-trigger" onClick={()=>setSavedPlansOpen(true)} aria-haspopup="dialog" aria-label={`저장한 계획 ${savedPlans.length}개`}>저장한 계획 <span>{savedPlans.length}</span></button>
  <button className="reset-button" aria-label="초기화" onClick={()=>{reset();setBudget('');setDays(3);setSettings(defaultSettings);setCategory('all');setCountryCode('');setError('');window.scrollTo({top:0})}}>↺ <span>초기화</span></button></div>
 </header><main id="main-content" className={resultsPage?'showing-results':'showing-search'} tabIndex={-1}>
  {planNotice&&<p className="plan-notice" role="status">{planNotice}</p>}
  <section className="planner-page search-page" aria-label="여행 조건 검색" hidden={resultsPage}>
  <div className="hero"><div><p className="eyebrow"><span className="hero-spark" aria-hidden="true">✦</span> YOUR NEXT CHAPTER</p>
  <h1 id="search-title" tabIndex={-1}>{mode==='A'?<>내 예산에 맞는,<br className="mobile-break"/> 새로운 여행.</>:<>뜻밖의 목적지,<br className="mobile-break"/> 나만의 여행.</>}</h1>
  <p className="hero-description">{mode==='A'?'예산 안의 여행지를 둘러보고, 마음에 드는 곳을 선택하세요.':'어디로 갈지 고민될 때, 룰렛 한 번으로 시작해보세요.'}</p></div>
  <span className="connection-badge">{health?(health.demoMode?'샘플 모드':health.aiConfigured?'AI 플래너 준비 완료':'API 키 설정 필요'):'연결 확인 중'}</span></div>
  <ol className="journey-steps" aria-label="여행 계획 순서"><li className="current"><span>01</span> 여행 조건 설정</li><li className={cities.length?'current':''}><span>02</span> 새로운 목적지 발견</li><li className={result?'current':''}><span>03</span> 나만의 일정 완성</li></ol>


  {cities.length>0&&<button type="button" className="resume-results" onClick={()=>navigate('results')}>추천 결과 다시 보기 <span>{visibleCities.length}곳 ↗</span></button>}
  <div className="planner-layout">
  <section className="panel planner-controls" aria-label="여행 조건 설정">
   <div className="section-heading"><div><span className="eyebrow">여행 설정</span><h2>어떤 여행을 떠날까요?</h2></div><span className="step-mark">01</span></div>
   <fieldset className="mb-5">
    <legend className="font-bold mb-3">여행 지역</legend>
    <div className="category-switch">{categories.map(([value,label])=><button type="button" key={value} className={category===value?'active':'secondary'} aria-pressed={category===value} onClick={()=>{if(category!==value||countryCode){reset(mode);setCategory(value);setCountryCode('');setError('')}}}>{label}</button>)}</div>
   </fieldset>
   <p className="help-text mb-5">국내·해외 모두 여행 지역을 먼저 고릅니다. 명소는 선택한 지역의 AI 일정을 만들 때 넣어요.</p>
   <label htmlFor="travel-days" className="block font-bold mb-3">여행 기간</label>
   <select id="travel-days" className="mb-5" value={days} onChange={e=>{const nextDays=Number(e.target.value);setDays(nextDays);updateSettings(settings,nextDays)}}>
    {Array.from({length:14},(_,i)=>i+1).map(day=><option key={day} value={day}>{day===1?'1일 (당일치기)':`${day}일 (${day-1}박 ${day}일)`}</option>)}
   </select>
   <TripSettings value={settings} onChange={updateSettings}/>
   {mode==='A'?<form onSubmit={throwDart}>
    <label htmlFor="budget" className="block font-bold mb-3">여행 예산 · {settings.people}명 전체 총예산</label>
    <input id="budget" className="budget-input" type="text" placeholder="예: 500만원 또는 5,000,000원" value={budget} maxLength={30} onChange={e=>{setBudget(e.target.value);reset('A');setError('')}} aria-describedby="budget-preview budget-help" aria-invalid={budget.trim()!==''&&parsedBudget===null}/>
    <p id="budget-preview" className={'budget-preview '+(budget.trim()!==''&&parsedBudget===null?'error':'muted')} role="status">{budget.trim()===''?'숫자만 입력하면 원 단위로 인식해요.':parsedBudget!==null?`입력한 예산: ${won(parsedBudget)}`:'1원~1억원으로 입력해주세요. 예: 500만원, 1.5만원'}</p>
    <button className="primary-action" disabled={loading||!!flight}>{loading?'예산에 맞는 곳 찾는 중…':flight?'룰렛이 멈추는 중…':selectedCountry?`${selectedCountry.name}에서 여행지 찾기`:'예산 안에서 여행지 찾기'} <span aria-hidden="true">↗</span></button>
    <p id="budget-help" className="help-text">예상 비용 상한이 예산 이하인 후보에서<br/>50만원 구간별 무작위로 최대 3곳씩 보여드려요.</p>
   </form>:<form onSubmit={throwDart}>
    <button className="primary-action" disabled={loading||!!flight}>{loading?'룰렛 돌리는 중…':flight?'룰렛이 멈추는 중…':selectedCountry?`${selectedCountry.name} 룰렛 돌리기`:'여행 룰렛 돌리기'} <span aria-hidden="true">↗</span></button>
    <p className="help-text">룰렛이 멈추면 별도 결과 화면에서<br/>여행지·지역 명소·AI 일정을 확인할 수 있어요.<br/>예산 제한 없이 뽑고, 경비는 나중에 확인해요.<br/>{selectedCountry?`${selectedCountry.name} 안에서만 무작위로 선택해요.`:'전체 선택 시 국내·해외 각각 50% 확률이에요.'}</p>
   </form>}
   {error&&<div className="error-box" role="alert">{error}{!health&&<button className="secondary mt-3" onClick={()=>setBoot(n=>n+1)}>서버 다시 연결</button>}</div>}
  </section>
  <section className="map-panel" id="trip-map" aria-label="여행지 지도">
   <div className="map-heading"><div><span className="eyebrow">다음 목적지</span><h2>{(roulettePending||flight)?'룰렛이 고르는 다음 여행':cities.length?'이번 여행의 목적지':selectedCountry?`${selectedCountry.name}, 어디로 떠날까요?`:'가능성은 어디에나'}</h2></div><span className="map-pill">{selectedCountry?.name||categories.find(([value])=>value===category)[1]} · {days}일</span></div>
   <CountryPicker countries={countries} selected={selectedCountry} onSelect={selectCountry} loading={!countryData&&!countryError} error={countryError} onRetry={()=>setBoot(value=>value+1)} disabled={!!flight}/>
  <TravelMap visible={!resultsPage} spinning={roulettePending} category={category} cities={visibleCities} selected={selected} focus={mapFocus} flight={flight} onLand={land} celebrate={celebrate} onSelect={selectCity} nearby={nearby?.places||EMPTY_PLACES} onPlaceSelect={loadDetails} countryData={countryData} country={selectedCountry} onCountrySelect={selectCountry}/>
   <SearchProgress phase={phase}/>
   <div className="map-status" role="status"><span className={loading?'status-dot pulse':'status-dot'} aria-hidden="true"/><p>{status}</p></div>

   <div className="trip-preview"><span className="preview-icon" aria-hidden="true">↗</span><div><strong>{cities.length?(selected?'여행의 시작이 정해졌어요':'마음에 드는 여행지를 선택하세요'):'다음 여행은 어디일까요?'}</strong><p>{selected?`선택 지역 · ${destinationRegion(selected)}`:cities.length?'아래 목록에서 여행지를 선택하고, 경비 버튼으로 상세 비용을 확인하세요.':'왼쪽에서 조건을 고르고, 새로운 목적지를 만나보세요.'}</p></div><span className="preview-tag">{days===1?'당일치기':`${days-1}박 ${days}일`} · {settings.people}명</span></div>
  </section>
  </div>
  </section>
  {cities.length>0&&<section className="planner-page results-page" aria-label="여행 추천 결과 화면" hidden={!resultsPage}>
   <header className="results-page-heading"><p className="eyebrow">YOUR TRAVEL PLAN</p><h1 id="results-title" tabIndex={-1}>나의 여행 계획</h1><p>{mode==='B'?'룰렛이 고른 지역의 여행 정보, 명소와 AI 일정을 확인하세요.':'추천 지역을 고르고, 명소와 AI 일정까지 한곳에서 준비하세요.'}</p></header>
   <div className="trip-summary"><span>{selectedCountry?.name||categories.find(([value])=>value===category)[1]}</span><span>{days}일 · {settings.people}명</span>{selectedThemes(settings).map(theme=><span key={theme}>{themeLabel(theme)}</span>)}<span>{mode==='A'?`총예산 ${won(chosenBudget.current)}`:'랜덤 룰렛'}</span></div>
   <div className={'result-selection'+(selected?' has-selection':'')}>
    <div><small>{selected?'선택한 여행 지역':'먼저 여행 지역을 골라주세요'}</small><strong>{selected?destinationLabel(selected):'지역을 선택하면 명소와 AI 일정을 볼 수 있어요.'}</strong></div>
    {selected&&<div className="selection-actions"><button type="button" className="secondary" onClick={()=>mode==='B'?backToSearch():setResultTab('destinations')}>{mode==='B'?'조건 수정·다시 돌리기':'지역 다시 선택'}</button><button type="button" className="save-result" onClick={savePlan} disabled={loading||aiLoading||planSaved} data-saved={planSaved}>{planSaved?'저장 완료 ✓':'계획 저장 ♡'}</button></div>}
   </div>
   {selected&&<DestinationPhoto city={selected}/>}
   {selected&&<FlightQuotePanel key={`${selected.cityName}:${days}:${settings.origin}:${settings.people}:${settings.departureDate}:${settings.hotelPerRoomNight}:${selectedThemes(settings).join(',')}`} city={selected} settings={{...settings,themes:selectedThemes(settings)}} days={days} budget={mode==='A'?chosenBudget.current:0} onApply={applyFlightCost} disabled={loading||aiLoading}/>}
   <div id="results-tabs-start" aria-hidden="true"/>
   <ResultsTabs active={resultTab} onChange={setResultTab} hasSelection={!!selected}/>
   <div className="result-panel" id="result-panel-destinations" role="tabpanel" aria-labelledby="result-tab-destinations" tabIndex={0} hidden={resultTab!=='destinations'}>
    <div className="feature-heading results-heading"><div><h2>{mode==='A'?`금액대별 여행지 ${visibleCities.length}곳`:'이번 여행의 목적지'}</h2><p className="muted text-sm">{mode==='A'?`명소가 확인된 후보 ${cities.length}곳에서 50만원 구간별 최대 3곳씩 골랐어요. 마음에 드는 지역을 선택하세요.`:'선택된 여행지의 명소와 AI 일정을 확인하세요.'}</p></div></div>
    {mode==='A'&&<div className="list-roulette-prompt"><div><strong>마음에 드는 곳을 고르기 어렵다면?</strong><p>현재 목록에 보이는 {visibleCities.length}곳 중에서 룰렛으로 골라보세요.</p></div><button type="button" className="list-roulette-trigger" disabled={visibleCities.length<2||loading||aiLoading||!!flight} onClick={()=>setListRouletteCities([...visibleCities])} aria-haspopup="dialog">추천 목록에서 룰렛 돌리기 <span aria-hidden="true">↻</span></button>{visibleCities.length<2&&<small>추천 여행지가 2곳 이상일 때 돌릴 수 있어요.</small>}</div>}
    <DestinationList onRefresh={mode==='A'?refreshGroup:undefined} refreshDisabled={aiLoading} groups={destinationGroups.map(group=>({...group,cities:group.cities.map(withFlightCost)}))} quoted={Object.keys(flightCosts).length>0} selected={selected} people={settings.people} budget={mode==='A'?chosenBudget.current:0} disabled={loading||!!flight} onSelect={selectCity} onCost={city=>{selectCity(city,{showDetails:false});setCostCity(withFlightCost(city));}}/>
   </div>
   <div className="result-panel" id="result-panel-places" role="tabpanel" aria-labelledby="result-tab-places" tabIndex={0} hidden={resultTab!=='places'}>
    <PlaceExplorer city={selected} nearby={nearby} loading={nearbyLoading} error={nearbyError} onLoad={loadNearby} onDetails={loadDetails} details={details} detailsLoading={detailsLoading} detailsError={detailsError}/>
    {selected&&<button type="button" className="continue-itinerary" onClick={()=>setResultTab('itinerary')}>이 지역의 AI 일정 준비하기 <span aria-hidden="true">→</span></button>}
   </div>
   <div className="result-panel" id="result-panel-itinerary" role="tabpanel" aria-labelledby="result-tab-itinerary" tabIndex={0} hidden={resultTab!=='itinerary'}>
    <Itinerary city={selected} days={days} loading={aiLoading} result={result} error={aiError} onRetry={()=>generate(selected,chosenBudget.current,!!result)} onCancel={()=>{aiRequest.current?.abort();setAiLoading(false);setAiError('');setResult(results[selected.cityName]||null)}}/>
   </div>
   {selected?.nameTranslationNotice&&<p className="translation-notice" role="status">원어 도시명: <strong>{selected.originalName}</strong> · {selected.nameTranslationNotice}</p>}
  </section>}
  {costCity&&<CostDialog city={costCity} budget={mode==='A'?chosenBudget.current:0} onClose={()=>setCostCity(null)}/>}
  <footer><span className="footer-brand"><img src="/trip-budget.svg" alt="" width="34" height="26"/>TripBudget <span>내 예산에 맞는, 새로운 여행.</span></span><p>여행 정보 · 한국관광공사 TourAPI · <a href="https://www.geoapify.com/" target="_blank" rel="noreferrer">Geoapify</a> · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> · <a href="https://www.geonames.org/" target="_blank" rel="noreferrer">GeoNames (CC BY 4.0)</a><br/>AI 일정과 예상 경비는 참고용입니다. 실제 가격과 운영시간은 예약 전 확인해주세요.</p></footer>
 </main>{listRouletteCities&&<ListRouletteDialog cities={listRouletteCities} onClose={()=>setListRouletteCities(null)} onSelect={city=>{setListRouletteCities(null);selectCity(city)}}/>}{savedPlansOpen&&<SavedPlansDialog plans={savedPlans} onClose={()=>setSavedPlansOpen(false)} onLoad={plan=>{setSavedPlansOpen(false);loadPlan(plan)}} onDelete={deletePlan} onImport={text=>setSavedPlans(writePlans(importPlans(text,savedPlans)))} disabled={loading||!!flight||aiLoading}/>}<SaveToast notice={saveNotice} onDismiss={dismissSaveNotice}/></>;
}
