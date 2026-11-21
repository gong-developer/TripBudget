import {useEffect,useRef,useState} from 'react';
import Roulette from './Roulette';

export default function ListRouletteDialog({cities,onSelect,onClose}){
 const dialog=useRef(null);
 const [flight,setFlight]=useState(()=>({id:0,city:cities[Math.floor(Math.random()*cities.length)]}));
 const [winner,setWinner]=useState(null);
 useEffect(()=>{
  const element=dialog.current,previousFocus=document.activeElement;
  element.showModal();
  const previous=document.body.style.overflow;
  document.body.style.overflow='hidden';
  return()=>{element.close();document.body.style.overflow=previous;if(previousFocus?.isConnected)previousFocus.focus({preventScroll:true})};
 },[]);
 function spinAgain(){
  setWinner(null);
  setFlight(previous=>({id:previous.id+1,city:cities[Math.floor(Math.random()*cities.length)]}));
 }
 return <dialog ref={dialog} className="list-roulette-dialog" aria-labelledby="list-roulette-title" onCancel={onClose} onClick={event=>{if(event.target===dialog.current)onClose()}}>
  <header className="list-roulette-heading"><h2 id="list-roulette-title">추천 목록에서 룰렛</h2><button type="button" className="secondary" onClick={onClose} autoFocus aria-label="추천 목록 룰렛 닫기">닫기 ✕</button></header>
  <p className="list-roulette-scope">현재 목록에 보이는 {cities.length}곳 중에서 뽑아요. 입력한 예산과 여행 조건을 유지해요.</p>
  <div className="list-roulette-stage"><Roulette key={flight.id} flight={flight} onLand={active=>setWinner(active.city)}/></div>
  <div className="list-roulette-actions">
   <button type="button" className="primary-action" disabled={!winner} onClick={()=>onSelect(winner)}>{winner?'이 지역으로 여행 계획하기':'여행지를 고르고 있어요…'}</button>
   <button type="button" className="secondary" disabled={!winner} onClick={spinAgain}>다시 돌리기 ↻</button>
  </div>
 </dialog>;
}
