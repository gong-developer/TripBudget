import {useEffect,useRef} from 'react';
import SavedPlans from './SavedPlans';

export default function SavedPlansDialog({onClose,...props}){
 const dialog=useRef(null);
 useEffect(()=>{
  const element=dialog.current;
  const previousFocus=document.activeElement;
  element.showModal();
  const previous=document.body.style.overflow;
  document.body.style.overflow='hidden';
  return()=>{element.close();document.body.style.overflow=previous;if(previousFocus?.isConnected)previousFocus.focus({preventScroll:true})};
 },[]);
 return <dialog ref={dialog} className="saved-plans-dialog" aria-labelledby="saved-plans-title" onCancel={onClose} onClick={event=>{if(event.target===dialog.current)onClose()}}>
  <header className="saved-plans-heading"><h2 id="saved-plans-title">저장한 여행 계획</h2><button type="button" className="secondary" onClick={onClose} autoFocus aria-label="저장 목록 닫기">닫기 ✕</button></header>
  <SavedPlans {...props}/>
 </dialog>;
}
