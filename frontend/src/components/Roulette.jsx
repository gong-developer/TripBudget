import {useEffect,useRef,useState} from 'react';
import {destinationLabel,destinationRegion} from '../destinationLabel';
import {useReducedMotion} from '../useReducedMotion';
import {rouletteAnimation,winningSector,SECTORS,SPIN_DURATION} from '../rouletteAnimation';

export default function Roulette({flight,onLand}){
 const wheel=useRef(null),spin=useRef(null),land=useRef(onLand);
 const [revealed,setRevealed]=useState(false);
 const reduce=useReducedMotion();
 land.current=onLand;
 useEffect(()=>{
  if(reduce||!wheel.current?.animate)return;
  const animation=wheel.current.animate([{transform:'rotate(0deg)'},{transform:'rotate(360deg)'}],{
   duration:SPIN_DURATION,iterations:Infinity,easing:'linear'});
  spin.current=animation;
  return()=>{animation.cancel();spin.current=null};
 },[reduce]);
 useEffect(()=>{
  if(!flight)return;
  let cancelled=false,timer,animation;
  setRevealed(false);
  const reveal=()=>{
   if(cancelled)return;
   setRevealed(true);
   timer=setTimeout(()=>{if(!cancelled)land.current(flight)},1000);
  };
  const start=Number(spin.current?.currentTime||0)/SPIN_DURATION*360;
  spin.current?.cancel();
  if(reduce||!wheel.current?.animate){
   timer=setTimeout(reveal,600);
  }else{
   const {keyframes,options}=rouletteAnimation(start,winningSector(flight.city));
   animation=wheel.current.animate(keyframes,options);
   animation.finished.then(reveal).catch(()=>{});
  }
  return()=>{cancelled=true;clearTimeout(timer);animation?.cancel()};
 },[flight,reduce]);
 const city=revealed?flight?.city:null;
 return <div className={'roulette-overlay'+(revealed?' roulette-revealed':'')} role="status" aria-live="polite" aria-atomic="true">
  <div className="roulette-heading"><span className="eyebrow">TRAVEL ROULETTE</span><h3>{city?'이번 여행의 목적지는!':flight?'두근두근, 어디일까요?':'다음 여행지를 고르는 중'}</h3></div>
  <div className="roulette-stage" aria-hidden="true">
   <span className="roulette-pointer"/>
   <div className="roulette-wheel" ref={wheel}>{Array.from({length:SECTORS},(_,i)=><span className="roulette-sector" key={i} style={{transform:`rotate(${i*360/SECTORS}deg)`}}><b>{revealed&&i===winningSector(flight.city)?'★':'?'}</b></span>)}</div>
   <div className="roulette-hub"><span>{city?'✦':'✈'}</span><strong>{city?'당첨!':'어디로 떠날까요?'}</strong><small>{city?'BON VOYAGE':'NEXT TRIP'}</small></div>
  </div>
  <div className="roulette-result"><strong>{city?destinationLabel(city):reduce?'잠시 후 여행지가 공개돼요':'회전이 멈추면 여행지가 공개돼요'}</strong><p>{city?destinationRegion(city):reduce?'잠시 후 추첨 결과를 알려드릴게요.':'새로운 여행을 만나보세요.'}</p></div>
 </div>;
}
