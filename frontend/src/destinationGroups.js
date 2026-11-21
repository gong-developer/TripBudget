const PRICE_STEP=500000;
const MAX_PER_GROUP=3;
const byPrice=(a,b)=>b.estimatedCost-a.estimatedCost||a.cityName.localeCompare(b.cityName,'ko');

function sample(cities,count,random){
 const shuffled=[...cities];
 for(let i=shuffled.length-1;i>0;i--){
  const j=Math.floor(random()*(i+1));
  [shuffled[i],shuffled[j]]=[shuffled[j],shuffled[i]];
 }
 return shuffled.slice(0,count);
}

export function groupDestinations(cities,random=Math.random){
 const groups=new Map();
 const sorted=[...new Map(cities.map(city=>[city.cityName,city])).values()].sort(byPrice);
 for(const city of sorted){
  const lower=Math.floor(city.estimatedCost/PRICE_STEP)*PRICE_STEP;
  if(!groups.has(lower))groups.set(lower,{lower,upper:lower+PRICE_STEP,cities:[],totalCount:0});
  const group=groups.get(lower);
  group.totalCount++;
  group.cities.push(city);
 }
 return [...groups.values()].map(group=>({...group,cities:sample(group.cities,MAX_PER_GROUP,random).sort(byPrice)}));
}

export function refreshDestinationGroup(groups,cities,lower,random=Math.random){
 const group=groups.find(item=>item.lower===lower);
 if(!group)return groups;
 const candidates=[...new Map(cities.filter(city=>city.estimatedCost>=group.lower&&city.estimatedCost<group.upper)
  .map(city=>[city.cityName,city])).values()];
 const current=new Set(group.cities.map(city=>city.cityName));
 const alternatives=candidates.filter(city=>!current.has(city.cityName));
 if(!alternatives.length)return groups;
 // Prefer different destinations; reuse as few current cards as the pool requires.
 const fresh=sample(alternatives,MAX_PER_GROUP,random);
 const retained=sample(candidates.filter(city=>current.has(city.cityName)),MAX_PER_GROUP-fresh.length,random);
 const refreshed={...group,totalCount:candidates.length,cities:[...fresh,...retained].sort(byPrice)};
 return groups.map(item=>item.lower===lower?refreshed:item);
}
