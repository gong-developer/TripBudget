const tabs=[['destinations','여행지 추천'],['places','지역 명소'],['itinerary','AI 일정']];

export default function ResultsTabs({active,onChange,hasSelection}){
 function keyboard(event,index){
  const enabled=tabs.filter(([id])=>id==='destinations'||hasSelection);
  const current=enabled.findIndex(([id])=>id===tabs[index][0]);
  let next;
  if(event.key==='ArrowRight')next=(current+1)%enabled.length;
  else if(event.key==='ArrowLeft')next=(current-1+enabled.length)%enabled.length;
  else if(event.key==='Home')next=0;
  else if(event.key==='End')next=enabled.length-1;
  else return;
  event.preventDefault();
  onChange(enabled[next][0]);
  document.getElementById(`result-tab-${enabled[next][0]}`)?.focus();
 }
 return <div className="results-tabs" role="tablist" aria-label="여행 추천 결과">
  {tabs.map(([id,label],index)=><button key={id} id={`result-tab-${id}`} role="tab" type="button"
   aria-selected={active===id} aria-controls={`result-panel-${id}`} tabIndex={active===id?0:-1}
   disabled={id!=='destinations'&&!hasSelection} onClick={()=>onChange(id)} onKeyDown={event=>keyboard(event,index)}>
   <span aria-hidden="true">{String(index+1).padStart(2,'0')}</span>{label}
  </button>)}
 </div>;
}
