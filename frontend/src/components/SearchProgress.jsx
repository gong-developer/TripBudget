const steps=[['fetch','여행지 조회'],['compare','경비 비교'],['sights','명소 확인'],['ready','추천 완료']];
export default function SearchProgress({phase}) {
 if(!phase)return null;
 const active=steps.findIndex(([value])=>value===(phase==='names'?'sights':phase));
 return <ol className="search-progress" aria-label="여행지 조회 진행 단계">{steps.map(([value,label],i)=><li key={value} className={i<active?'done':i===active?'current':''} aria-current={i===active?'step':undefined}><span>{i<active?'✓':i+1}</span>{label}</li>)}</ol>;
}
