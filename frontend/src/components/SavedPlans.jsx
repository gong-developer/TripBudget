import {useRef,useState} from 'react';
import {exportPlans,MAX_BACKUP_BYTES} from '../savedPlans';

export default function SavedPlans({plans,onLoad,onDelete,onImport,disabled}) {
 const input=useRef(null),[notice,setNotice]=useState(''),[importing,setImporting]=useState(false);
 function download(){
  try{
   const url=URL.createObjectURL(new Blob([exportPlans(plans)],{type:'application/json'}));
   const link=document.createElement('a');link.href=url;link.download=`TripBudget-${new Date().toISOString().slice(0,10)}.json`;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
   setNotice('여행 계획을 백업 파일로 저장했어요. 다른 브라우저에서 불러올 수 있어요.');
  }catch{setNotice('백업 파일을 저장하지 못했어요. 브라우저의 다운로드 설정을 확인해주세요.');}
 }
 async function upload(event){
  const file=event.target.files?.[0];event.target.value='';if(!file)return;
  setImporting(true);setNotice('');
  try{if(file.size>MAX_BACKUP_BYTES)throw new Error('백업 파일은 2MB 이하만 불러올 수 있어요.');await onImport(await file.text());setNotice('백업을 불러왔어요. 기존 계획과 합쳐 최근 20개를 보관해요.');}
  catch(error){setNotice(error.message||'백업을 불러오지 못했어요.');}
  finally{setImporting(false);}
 }
 return <section className="saved-plans"><p className="saved-plans-count">총 <b>{plans.length}</b>개 · 이 브라우저에 최근 20개 보관</p>
  <div className="backup-actions"><button className="secondary" disabled={disabled||importing||!plans.length} onClick={download}>계획 백업</button><button className="secondary" disabled={disabled||importing} onClick={()=>input.current?.click()}>{importing?'불러오는 중…':'백업 불러오기'}</button><input ref={input} type="file" accept=".json,application/json" aria-label="여행 계획 백업 파일" hidden onChange={upload}/></div>
  {notice&&<p className="muted mt-3" role="status">{notice}</p>}
  {!plans.length?<p className="muted mt-4">마음에 드는 여행지를 선택한 뒤 ‘계획 저장’을 누르면 일정과 지도도 함께 보관해요.</p>:<div className="saved-grid">{plans.map(plan=><article className="saved-card" key={plan.id}><strong>{plan.title}</strong><p>{plan.days}일 · {plan.settings.people}명 · {new Date(plan.savedAt).toLocaleDateString('ko-KR')}</p><div><button className="secondary" disabled={disabled} onClick={()=>onLoad(plan)}>불러오기</button><button className="reset-button" disabled={disabled} onClick={()=>onDelete(plan.id)} aria-label={`${plan.title} 삭제`}>삭제</button></div></article>)}</div>}
 </section>;
}
