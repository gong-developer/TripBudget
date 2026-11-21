import {useEffect} from 'react';

export default function SaveToast({notice,onDismiss}){
 useEffect(()=>{
  if(!notice)return;
  const timer=setTimeout(onDismiss,5500);
  return()=>clearTimeout(timer);
 },[notice,onDismiss]);
 return <div className="save-toast-region" role="status" aria-live="polite" aria-atomic="true">
  {notice&&<div key={notice.id} className={'save-toast'+(notice.error?' save-toast-error':'')}>
   <span className="save-toast-icon" aria-hidden="true">{notice.error?'!':'✓'}</span>
   <div><strong>{notice.error?'저장하지 못했어요':notice.duplicate?'이미 저장한 계획이에요':'여행 계획을 저장했어요'}</strong><p>{notice.message}</p></div>
   <button type="button" onClick={onDismiss} aria-label="저장 알림 닫기">×</button>
  </div>}
 </div>;
}
