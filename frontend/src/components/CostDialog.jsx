import {useEffect,useRef} from 'react';
import CostBreakdown from './CostBreakdown';
import {destinationLabel} from '../destinationLabel';

export default function CostDialog({city,budget,onClose}){
 const dialog=useRef(null);
 useEffect(()=>{
  const element=dialog.current;
  element.showModal();
  const previous=document.body.style.overflow;
  document.body.style.overflow='hidden';
  return()=>{element.close();document.body.style.overflow=previous;};
 },[]);
 return <dialog ref={dialog} className="cost-dialog" aria-labelledby="cost-dialog-title" onCancel={onClose} onClick={event=>{if(event.target===dialog.current)onClose();}}>
  <div className="cost-dialog-content">
   <header className="cost-dialog-heading"><h2 id="cost-dialog-title">{destinationLabel(city)}</h2><button type="button" className="secondary" onClick={onClose} autoFocus aria-label="경비 상세 닫기">닫기 ✕</button></header>
   <CostBreakdown city={city} budget={budget}/>
  </div>
 </dialog>;
}
