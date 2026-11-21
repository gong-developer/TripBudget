export function filterCountries(countries, query) {
  const search=query.trim().toLocaleLowerCase();
  if(!search)return [];
  const aliases={kr:['한국','남한'],kp:['북한'],tw:['대만','타이완'],us:['USA','미국'],gb:['UK','영국']};
  return countries.filter(country=>[country.name,country.englishName,country.code,...(aliases[country.code]||[])]
    .some(value=>String(value||'').toLocaleLowerCase().includes(search))).slice(0,8);
}

export function countryStyle(code, selectedCode) {
  const selected=code===selectedCode;
  return {color:selected?'#315ee8':'#8298b5',weight:selected?2:.5,
    opacity:selected?.9:.45,fillColor:'#315ee8',fillOpacity:selected?.17:.015};
}
