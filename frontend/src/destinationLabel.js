const cities={London:'런던',Paris:'파리',Tehran:'테헤란','تهران':'테헤란',Lima:'리마',Tokyo:'도쿄',Bangkok:'방콕'};
const countries={Iran:'이란','ایران':'이란',Peru:'페루',Russia:'러시아',Japan:'일본',Thailand:'태국',UK:'영국',France:'프랑스'};
export const NAME_POLICY='registered-v1';
export const REJECTED_NAMES=['전체메뉴','전체 메뉴','주 메뉴','메뉴','스낵 바','스낵바','숙박 약관','채용정보','팟캐스트','카테고리','인기 카테고리','프로모션','이름 미제공','명소 이름 재조회 필요','여행지 이름 재조회 필요'];
export function safePlaceName(place){
 const trusted=place.namePolicy===NAME_POLICY&&!place.nameTranslated&&typeof place.name==='string'&&!!place.name.trim()&&!REJECTED_NAMES.includes(place.name);
 let original=(typeof place.originalName==='string'&&place.originalName)||(!place.nameTranslated&&typeof place.name==='string'?place.name:'')||'명소 이름 재조회 필요';
 if(REJECTED_NAMES.includes(original))original=typeof place.englishName==='string'&&place.englishName?place.englishName:'명소 이름 재조회 필요';
 return {...place,name:trusted?place.name:original,originalName:original,nameTranslated:false,namePolicy:NAME_POLICY};
}
export function isKoreanLabel(text){
 return typeof text==='string'&&!/번역 미확인|도시명 확인 중|한글 변환 중/u.test(text)&&/[가-힣]/u.test(text)&&![...text].some(char=>/\p{L}/u.test(char)&&!/[가-힣]/u.test(char));
}
export function destinationLabel(city){
 if(city.namePolicy===NAME_POLICY&&typeof city.displayName==='string'&&!REJECTED_NAMES.includes(city.displayName.split(' · ')[0]))return city.displayName;
 if(isKoreanLabel(city.cityName)&&!REJECTED_NAMES.includes(city.cityName.split(' · ')[0])&&(!city.originalName||isKoreanLabel(city.originalName)))return city.cityName;
 const parts=city.cityName.split(' · '),source=city.originalName||parts[0],name=cities[source]||source;
 let country=countries[parts[1]]||parts[1];
 if(city.countryCode){try{country=new Intl.DisplayNames(['ko'],{type:'region'}).of(city.countryCode.toUpperCase())}catch{}}
 const label=[name,country].filter(Boolean).join(' · ');
 return REJECTED_NAMES.includes(name)?'여행지 이름 재조회 필요':label||'여행지 이름 재조회 필요';
}

export function destinationRegion(city){
 const parts=city.cityName.split(' · ');
 let region=typeof city.regionName==='string'?city.regionName.trim():'';
 if(city.category==='domestic'){
  if(!region){
   const address=parts.slice(1).join(' ').trim().split(/\s+/u);
   region=[address[0],address[1]&&/[시군구]$/u.test(address[1])?address[1]:''].filter(Boolean).join(' · ');
  }
  return region||'세부 지역 정보 없음';
 }
 let country=destinationLabel(city).split(' · ').slice(1).join(' · ');
 if(city.countryCode){
  try{country=new Intl.DisplayNames(['ko'],{type:'region'}).of(city.countryCode.toUpperCase())||country}catch{}
 }
 return [...new Set([country,region||'세부 지역 정보 없음'].filter(Boolean))].join(' · ');
}
