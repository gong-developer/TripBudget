import {useState,useRef} from 'react';
import {filterCountries} from '../countries';

export default function CountryPicker({countries,selected,onSelect,loading,error,onRetry,disabled}) {
 const [query,setQuery]=useState('');
 const first=useRef(null),matches=filterCountries(countries,query);
 return <div className="country-picker"><div className="country-search-row"><label htmlFor="country-search">가고 싶은 나라</label><div className="country-search-box"><input id="country-search" type="search" placeholder={loading?'국가 목록 불러오는 중…':'지도에서 클릭하거나 국가명 검색'} value={query} disabled={disabled||loading||!!error} autoComplete="off" aria-describedby="country-selection-help" aria-controls="country-search-results" onChange={event=>setQuery(event.target.value)} onKeyDown={event=>{if(event.key==='ArrowDown'&&matches.length){event.preventDefault();first.current?.focus()}if(event.key==='Escape')setQuery('')}}/>
 {query.trim()&&<div id="country-search-results" className="country-search-results" aria-label="국가 검색 결과">{matches.length?matches.map((country,index)=><button key={country.code} ref={index===0?first:null} type="button" onClick={()=>{onSelect(country.code);setQuery('')}}><strong>{country.name}</strong><span>{country.englishName}</span></button>):<p role="status">일치하는 국가가 없어요. 한글·영문 이름으로 검색해주세요.</p>}</div>}</div></div>
 {error?<p className="country-help error" role="alert">{error} <button className="reset-button" onClick={onRetry}>다시 불러오기</button></p>:<p id="country-selection-help" className="country-help">북한과 국가 전역 여행금지 대상은 추천에서 제외해요. 지도에서 나라를 클릭해 선택하세요.</p>}
 {selected&&<div className="selected-country" role="status"><span className="country-pin" aria-hidden="true">◎</span><div><strong>{selected.name}</strong><small>이 국가 안에서만 여행지를 찾아요.</small></div><button type="button" disabled={disabled} onClick={()=>{onSelect('');setQuery('')}}>국가 선택 해제 ×</button></div>}
 </div>;
}
