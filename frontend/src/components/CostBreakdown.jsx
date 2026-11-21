import CostChart from './CostChart';

const won=n=>n.toLocaleString('ko-KR')+'원';
export default function CostBreakdown({city,budget}){
 const cost=city?.costBreakdown;
 if(!cost)return null;
 return <section className="panel mt-6" aria-label="여행 경비 상세">
  <h2 className="text-2xl font-black">여행 경비 상세 · {cost.people}명 전체 합계</h2>
  <p className="muted mt-2">{cost.origin} 출발 · {cost.nights}박 {cost.days}일 · {cost.rooms}실 · {cost.profile} 단가 기준</p>
  <p className="price mt-4 font-black">예상 합계 {won(cost.total)}</p>
  <p className="muted">예상 범위 {won(cost.low)} ~ {won(cost.high)} · 1인 약 {won(cost.perPerson)}</p>
  {budget>0&&<p className={'mt-3 '+(budget<cost.total?'error':'')}>입력 예산 {won(budget)} · {budget<cost.total?`예상 비용 대비 ${won(cost.total-budget)} 부족`:`예상 비용 대비 ${won(budget-cost.total)} 여유`}</p>}
  {budget>0&&<p className={'text-sm mt-2 '+(cost.high>budget?'error':'muted')}>{cost.high>budget?'예상 범위의 상한이 예산을 초과합니다. 조건을 조정하거나 다시 추천받아주세요.':`예산 활용률 ${(Math.floor(cost.high/budget*1000)/10).toLocaleString('ko-KR')}% · 예상 상한 기준 ${won(budget-cost.high)} 여유`}</p>}
  {cost.themeBudget?.themes?.length>0&&<div className="cost-theme-budget"><strong>{cost.themeBudget.themes.join(' · ')}</strong><p>{cost.themeBudget.additional>0?`카테고리 추가 예산 ${won(cost.themeBudget.additional)} · 예비비 제외`:'관광·입장료는 기본 경비에 포함돼요.'}</p><small>테마별 계획용 배정액입니다. 항목별 금액과 계산 근거를 아래에서 확인하세요.</small></div>}
  {cost.airfareEstimate&&<div className="cost-theme-budget airfare-assumption"><strong>1인 왕복 항공 예산 · {cost.airfareEstimate.region}</strong><p>{won(cost.airfareEstimate.pricePerPerson)} · 계획 범위 {won(cost.airfareEstimate.lowPerPerson)}~{won(cost.airfareEstimate.highPerPerson)}</p><small>앱에서 정한 기준이며 평균 운임이나 예약 가능 가격이 아닙니다. 항공권 가격 확인 후 예산을 다시 확인해주세요.</small><details><summary>항공 예산 기준 보기</summary><p>기본 {won(cost.airfareEstimate.basePerPerson)}</p>{cost.airfareEstimate.adjustments.map((text,index)=><p key={index}>{text}</p>)}</details></div>}
  <CostChart key={city.cityName} items={cost.items}/>
  <details className="cost-notes cost-calculation"><summary>항목별 계산 근거 보기</summary><div className="overflow-x-auto mt-5"><table className="cost-table"><caption className="sr-only">항목별 예상 비용과 계산 근거</caption><thead><tr><th>항목</th><th>예상 금액</th><th>계산 근거</th></tr></thead><tbody>{cost.items.map(item=><tr key={item.key}><th scope="row">{item.label}<small className="block muted">{item.source}</small></th><td>{won(item.amount)}</td><td className="muted">{item.basis}</td></tr>)}</tbody></table></div></details>
  <details className="cost-notes"><summary>계산 기준과 참고사항</summary><p className="muted text-sm mt-4">{cost.basis}</p>
  <ul className="muted text-sm mt-3 list-disc pl-5">{cost.warnings.map(message=><li key={message}>{message}</li>)}</ul></details>
 </section>;
}
