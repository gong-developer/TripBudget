import {selectedThemes,isTravelTheme} from './travelThemes.js';
import {NAME_POLICY,destinationLabel,safePlaceName} from './destinationLabel.js';
export const STORAGE_KEY = 'tripbudget.plans.v1';
export const MAX_PLANS = 20;
export const MAX_BACKUP_BYTES=2*1024*1024;
const origins=new Set('seoul incheon gyeonggi gangwon busan daegu daejeon gwangju ulsan sejong chungbuk chungnam jeonbuk jeonnam gyeongbuk gyeongnam jeju'.split(' '));
const optionalPrice=(value,max)=>value==null||(Number.isSafeInteger(value)&&value>=0&&value<=max);
const validDate=value=>value==null||value===''||(/^\d{4}-\d{2}-\d{2}$/.test(value)&&value<='2100-12-31'&&Number.isFinite(Date.parse(value))&&new Date(value).toISOString().slice(0,10)===value);
const validPoint = point => point && typeof point.name === 'string' &&
  Number.isFinite(point.lat) && Math.abs(point.lat) <= 90 &&
  Number.isFinite(point.lng) && Math.abs(point.lng) <= 180;

export function validPlan(plan) {
  return plan && plan.version === 1 && typeof plan.id === 'string' &&
    typeof plan.savedAt === 'string' && Number.isFinite(Date.parse(plan.savedAt)) &&
    Number.isSafeInteger(plan.amount) && plan.amount > 0 && plan.amount <= 1000000000 &&
    typeof plan.title === 'string' && ['A','B'].includes(plan.mode) &&
    ['all','domestic','international'].includes(plan.category) &&
    (plan.countryCode==null||plan.countryCode===''||/^[a-z]{2}$/.test(plan.countryCode)) &&
    Number.isInteger(plan.days) && plan.days >= 1 && plan.days <= 14 &&
    plan.settings && origins.has(plan.settings.origin) &&
    validDate(plan.settings.departureDate) &&
    optionalPrice(plan.settings.transportPerPerson,20000000) && optionalPrice(plan.settings.hotelPerRoomNight,5000000) &&
    Number.isInteger(plan.settings.people) && plan.settings.people >= 1 && plan.settings.people <= 10 &&
    ['budget','standard','comfort'].includes(plan.settings.style) &&
    (plan.settings.theme==null||isTravelTheme(plan.settings.theme)) &&
    (plan.settings.themes==null||(Array.isArray(plan.settings.themes)&&plan.settings.themes.length<=7&&plan.settings.themes.every(isTravelTheme))) &&
    Array.isArray(plan.cities) && plan.cities.length >= 1 && plan.cities.length <= 3 &&
    plan.cities.every(city => city && typeof city.cityName === 'string' &&
      Number.isFinite(city.lat) && city.lat >= -90 && city.lat <= 90 &&
      Number.isFinite(city.lng) && city.lng >= -180 && city.lng <= 180 &&
      ['domestic','international'].includes(city.category) &&
      Number.isSafeInteger(city.estimatedCost) && city.estimatedCost > 0) &&
    plan.cities.some(city => city.cityName === plan.selectedName) &&
    (plan.flightQuote == null || (Number.isSafeInteger(plan.flightQuote.pricePerPerson)&&plan.flightQuote.pricePerPerson>0&&plan.flightQuote.pricePerPerson<=20000000&&validDate(plan.flightQuote.departureDate)&&typeof plan.flightQuote.departureDate==='string'&&plan.flightQuote.departureDate.length===10)) &&
    (plan.result == null || (typeof plan.result.text === 'string' && ['gemini','demo'].includes(plan.result.source))) &&
    (plan.nearby == null || (Array.isArray(plan.nearby.places) && plan.nearby.places.every(validPoint))) &&
    (plan.route == null || (['walk','drive'].includes(plan.route.mode) &&
      Number.isInteger(plan.route.day) && plan.route.day >= 1 && plan.route.day <= plan.days &&
      Number.isFinite(plan.route.distance) && plan.route.distance >= 0 &&
      Number.isFinite(plan.route.duration) && plan.route.duration >= 0 &&
      Array.isArray(plan.route.waypoints) && plan.route.waypoints.every(validPoint) &&
      Array.isArray(plan.route.lines) && plan.route.lines.length > 0 &&
      plan.route.lines.every(line => Array.isArray(line) && line.length >= 2 &&
        line.every(point => Array.isArray(point) && Number.isFinite(point[0]) && Math.abs(point[0]) <= 90 &&
          Number.isFinite(point[1]) && Math.abs(point[1]) <= 180))));
}

// Only user choices define a duplicate; refreshed photos, prices and nearby results do not.
export function planIdentity(plan){
 const city=plan.cities?.find(city=>city.cityName===plan.selectedName);
 const settings=plan.settings||{};
 return JSON.stringify({
  destination:[plan.selectedName,city?.lat,city?.lng],amount:plan.amount,days:plan.days,
  origin:settings.origin,people:settings.people,style:settings.style||'standard',
  themes:selectedThemes(settings),departureDate:settings.departureDate||null,
  transport:settings.transportPerPerson??null,hotel:settings.hotelPerRoomNight??null,
  itinerary:(plan.result||plan.legacyResult)?.text||null,route:plan.route||null,
 });
}

export function uniquePlans(plans){
 const seen=new Set();
 return plans.filter(validPlan).map(normalizePlan).filter(plan=>{
  const key=planIdentity(plan);
  if(seen.has(key))return false;
  seen.add(key);return true;
 }).slice(0,MAX_PLANS);
}

export function readPlans(storage) {
  try {
    storage ||= globalThis.localStorage;
    const plans = JSON.parse(storage.getItem(STORAGE_KEY) || '[]');
    return Array.isArray(plans) ? uniquePlans(plans) : [];
  } catch {
    return [];
  }
}

export function writePlans(plans, storage) {
  storage ||= globalThis.localStorage;
  const clean = uniquePlans(plans);
  storage.setItem(STORAGE_KEY, JSON.stringify(clean));
  return clean;
}

export function exportPlans(plans){
 return JSON.stringify({format:'TripBudget',version:1,plans:uniquePlans(plans)},null,2);
}

export function importPlans(text,existing=[]){
 if(new TextEncoder().encode(text).byteLength>MAX_BACKUP_BYTES)throw new Error('백업 파일은 2MB 이하만 불러올 수 있어요.');
 let data;
 try{data=JSON.parse(text);}catch{throw new Error('올바른 JSON 백업 파일이 아니에요.');}
 if(data?.format!=='TripBudget'||data.version!==1||!Array.isArray(data.plans)||!data.plans.length||data.plans.length>MAX_PLANS||!data.plans.every(validPlan))throw new Error('지원하지 않거나 손상된 여행 계획 백업이에요.');
 const combined=new Map(existing.filter(validPlan).map(normalizePlan).map(plan=>[plan.id,plan]));
 for(const plan of data.plans.map(normalizePlan))combined.set(plan.id,plan);
 return uniquePlans([...combined.values()].sort((a,b)=>Date.parse(b.savedAt)-Date.parse(a.savedAt)));
}

function normalizePlan(plan){
 if(plan.namePolicy===NAME_POLICY)return plan;
 const cities=plan.cities.map(city=>{
  const clean={...city};
  if(clean.namePolicy!==NAME_POLICY){delete clean.displayName;delete clean.nameLocalized;delete clean.nameTranslationNotice;}
  return clean;
 });
 const selected=cities.find(city=>city.cityName===plan.selectedName);
 return {...plan,namePolicy:NAME_POLICY,cities,title:destinationLabel(selected),
  nearby:plan.nearby?{...plan.nearby,places:plan.nearby.places.map(safePlaceName)}:plan.nearby,
  ...(plan.result?{legacyResult:plan.result,result:null}:{}),
 };
}
