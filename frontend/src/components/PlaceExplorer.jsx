import {useEffect,useRef,useState} from 'react';
import {safePlaceName} from '../destinationLabel';
export default function PlaceExplorer({city,nearby,loading,error,onLoad,onDetails,details:rawDetails,detailsLoading,detailsError}) {
 const detailSection=useRef(null),scrollPending=useRef(false);
 const [detailRequest,setDetailRequest]=useState(0);
 useEffect(()=>{
  if(!scrollPending.current||!detailSection.current)return;
  const frame=requestAnimationFrame(()=>{
   const section=detailSection.current;
   if(!section?.getClientRects().length)return;
   section.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
   if(!detailsLoading)scrollPending.current=false;
  });
  return()=>cancelAnimationFrame(frame);
 },[detailRequest,rawDetails,detailsLoading,detailsError]);
 function selectPlace(place){
  scrollPending.current=true;setDetailRequest(value=>value+1);onDetails(place);
 }
 const regional=city?.destinationType==='region';
 const details=rawDetails?safePlaceName(rawDetails):null;
 const mapQuery=details?.name||'';
 const places=(nearby?.places||[]).map(safePlaceName);
 if(!city)return null;
 return <section className="panel place-explorer" aria-busy={loading}><div className="feature-heading"><div><p className="eyebrow">AROUND YOUR DESTINATION</p><h2>{regional?'선택 지역의 명소 둘러보기':'주변 명소 둘러보기'}</h2></div>{(nearby||error)&&<button type="button" className="secondary" disabled={loading} onClick={onLoad}>{loading?'명소 조회 중…':error?'명소 다시 시도':'명소 새로 확인'}</button>}</div>
 <p className="muted text-sm mt-2">{regional?'선택한 지역의 명소를 지도에서 확인하세요. AI 일정에도 이 지역의 명소를 사용해요.':'여행지 주변 15km의 명소를 지도에서 확인하세요.'} 제공된 한국어 이름을 우선 쓰며, 확인되지 않은 이름은 원어 그대로 표시해요.</p>
 {loading&&<p className="muted mt-4" role="status">선택한 지역의 명소를 불러오고 있어요…</p>}
 {error&&<p className="error mt-3" role="alert">{error}</p>}
 {nearby&&<><div className="places-grid">{places.map((place,i)=><button className={'place-card '+(details?.placeId&&details.placeId===place.placeId?'selected':'')} key={place.placeId||`${place.lat}-${place.lng}-${i}`} onClick={()=>selectPlace(place)}><span className="place-number">{i+1}</span><span><strong>{place.name}</strong>{place.originalName&&place.originalName!==place.name&&<small>{place.originalName}</small>}<small>{place.address||'주소 미제공'}</small></span><span aria-hidden="true">↗</span></button>)}</div>{!places.length&&<p className="muted mt-4">이 주변에서 제공되는 명소 정보가 없어요.</p>}</>}
 <div ref={detailSection} className="place-detail-section">
 {detailsLoading&&<p role="status" className="muted mt-4">장소 상세 정보를 불러오고 있어요…</p>}
 {detailsError&&<p className="error mt-4" role="alert">{detailsError}</p>}
 {details&&!detailsLoading&&<article className="place-detail"><p className="eyebrow">장소 상세</p><h3>{details.name}</h3>{details.originalName&&details.originalName!==details.name&&<p className="muted">원어 이름 · {details.originalName}</p>}<p>주소 · {details.address||'주소 정보 미제공'}</p><a className="secondary place-map-button" href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(mapQuery)}`} target="_blank" rel="noopener noreferrer" aria-label={`${details.name} 구글맵에서 보기 (새 탭)`}>구글맵에서 보기 ↗</a><small>{details.source||'Geoapify · OpenStreetMap'} 제공 · 한국어 이름이 없으면 원어를 표시하며 주소도 원문을 유지해요.</small></article>}
 </div>
 </section>;
}
