import DestinationPhoto from './DestinationPhoto';
import {destinationLabel,destinationRegion} from '../destinationLabel';

const won=value=>value.toLocaleString('ko-KR')+'원';

export default function DestinationList({groups,selected,people,budget,disabled,onSelect,onCost,onRefresh,refreshDisabled=false,quoted=false}){
 const count=groups.reduce((sum,group)=>sum+group.cities.length,0);
 if(!count)return null;
 return <section className="destination-list" aria-label="여행지 목록">
  <div className="destination-list-heading"><strong>{groups.length}개 금액대 · {count}곳</strong><span>50만원 단위 · 구간별 랜덤 최대 3곳 · {people}명 전체</span></div>
  <div className="destination-list-scroll" role="region" aria-label="여행지 목록 스크롤" tabIndex={0}>
   {groups.map(group=><section key={group.lower} aria-label={`${group.lower/10000}만원 이상 ${group.upper/10000}만원 미만`}>
   <div className="destination-group-heading"><h3>{quoted?'추천 당시 · ':''}{(group.lower/10000).toLocaleString('ko-KR')}만원 이상 ~ {(group.upper/10000).toLocaleString('ko-KR')}만원 미만</h3><div className="destination-group-actions"><span>{group.totalCount}곳 중 {group.cities.length}곳</span>{onRefresh&&<button type="button" className="destination-refresh" disabled={disabled||refreshDisabled||group.totalCount<=group.cities.length} title={group.totalCount>group.cities.length?'같은 금액대의 다른 후보를 우선 추천해요.':'이 금액대의 다른 후보가 없어요.'} aria-label={`${group.lower/10000}만원 이상 ${group.upper/10000}만원 미만 여행지 새로고침`} onClick={()=>onRefresh(group.lower)}><span aria-hidden="true">↻</span> 새로고침</button>}{onRefresh&&group.totalCount<=group.cities.length&&<small>다른 후보 없음</small>}</div></div>
   <ul>{group.cities.map((city,i)=><li key={city.cityName} className={selected?.cityName===city.cityName?'selected':''}>
    <DestinationPhoto city={city} compact/>
    <button type="button" className="destination-select" disabled={disabled} aria-pressed={selected?.cityName===city.cityName} onClick={()=>onSelect(city)}>
     <strong>{destinationLabel(city)}</strong><small>{selected?.cityName===city.cityName?'선택됨 · ':''}{city.category==='domestic'?(city.destinationType==='region'?'국내 지역':'국내'):(city.destinationType==='region'?'해외 지역':'해외')}{city.nameTranslationNotice?` · ${city.originalName}`:''}</small>
     <small>지역 · {destinationRegion(city)}</small>{city.sightsVerified&&<small>관광명소 {city.sightCount}곳 확인</small>}
    </button>
    <div className="destination-row-cost"><strong>{won(city.estimatedCost)}</strong><small className={budget>0&&city.costBreakdown.high>budget?'error':''}>예상 상한 {won(city.costBreakdown.high)}</small></div>
    <button type="button" className="secondary destination-cost-button" disabled={disabled} aria-label={`${destinationLabel(city)} 경비 확인`} onClick={()=>onCost(city)}>경비 <span aria-hidden="true">↗</span></button>
   </li>)}</ul></section>)}
  </div>
  <p className="destination-list-help">{quoted&&'금액대는 추천 당시 기준이며, 항공료를 확인한 지역은 조회가를 반영한 경비로 표시해요. '}{onRefresh?'금액대별 새로고침을 누르면 같은 금액대의 다른 후보를 우선 보여드려요. 후보가 적으면 일부 여행지가 유지될 수 있어요.':'구간마다 최대 3곳을 무작위로 뽑아 높은 금액대부터 표시해요.'} 경비를 누르면 상세 내역이 열려요.</p>
 </section>;
}
