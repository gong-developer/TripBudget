import test from 'node:test';
import assert from 'node:assert/strict';
import {readPlans,writePlans,STORAGE_KEY,exportPlans,importPlans,planIdentity} from '../src/savedPlans.js';

const plan=()=>({version:1,namePolicy:'registered-v1',id:'one',title:'부산',mode:'A',budget:'100만원',amount:1000000,
 category:'domestic',days:3,settings:{origin:'seoul',people:1,style:'standard'},
 savedAt:'2026-11-01T00:00:00Z',cities:[{cityName:'부산',lat:35,lng:129,category:'domestic',estimatedCost:500000}],
 selectedName:'부산',result:{text:'1일차\n오전: 방문',source:'gemini'}});
function storage(){const values={};return {getItem:key=>values[key]||null,setItem:(key,value)=>{values[key]=value}};}

test('persists schedules across reads and keeps at most 20 plans',()=>{
 const store=storage();writePlans([plan()],store);
 assert.deepEqual(readPlans(store),[plan()]);
 writePlans(Array.from({length:25},(_,i)=>({...plan(),id:String(i),amount:1000000+i})),store);
 assert.equal(readPlans(store).length,20);
});

test('invalid or damaged saved state cannot crash map rendering',()=>{
 const store=storage();store.setItem(STORAGE_KEY,'broken');assert.deepEqual(readPlans(store),[]);
 writePlans([{...plan(),route:{lines:'broken'}},{...plan(),cities:[{lat:999}]},plan()],store);
 assert.equal(readPlans(store).length,1);
 assert.throws(()=>writePlans([plan()],{setItem(){throw new Error('quota')}}),/quota/);
});

test('country selection persists without breaking previously saved plans',()=>{
 const store=storage();
 writePlans([{...plan(),countryCode:'jp',amount:2000000},plan()],store);
 assert.equal(readPlans(store)[0].countryCode,'jp');
 assert.equal(readPlans(store).length,2);
 writePlans([{...plan(),countryCode:'Japan'}],store);
 assert.equal(readPlans(store).length,0);
});

test('backups round-trip, merge by identity and reject broken settings',()=>{
 const original=plan(),other={...plan(),id:'two',amount:2000000,savedAt:'2026-11-02T00:00:00Z'};
 assert.deepEqual(importPlans(exportPlans([original])),[original]);
 assert.deepEqual(importPlans(exportPlans([original]),[other,original]),[other,original]);
 assert.throws(()=>importPlans('broken'),/JSON/);
 const backup=JSON.parse(exportPlans([original]));
 backup.plans[0].settings.origin='not-a-region';
 assert.throws(()=>importPlans(JSON.stringify(backup)),/손상/);
 backup.plans[0].settings={...original.settings,departureDate:'2026-02-31'};
 assert.throws(()=>importPlans(JSON.stringify(backup)),/손상/);
 backup.plans[0].settings={...original.settings,transportPerPerson:-1};
 assert.throws(()=>importPlans(JSON.stringify(backup)),/손상/);
});

test('legacy translations are hidden while original plans remain in backups',()=>{
 const legacy={...plan(),namePolicy:undefined,nearby:{places:[{name:'전체메뉴',originalName:'Seomyeon Shopping District',nameTranslated:true,lat:35,lng:129}]}};
 const store=storage();store.setItem(STORAGE_KEY,JSON.stringify([legacy]));
 const restored=readPlans(store)[0];
 assert.equal(restored.nearby.places[0].name,'Seomyeon Shopping District');
 assert.equal(restored.result,null);
 assert.deepEqual(restored.legacyResult,legacy.result);
 assert.deepEqual(JSON.parse(exportPlans([restored])).plans[0].legacyResult,legacy.result);
});

test('travel category round-trips and invalid categories cannot enter saved plans',()=>{
 const themed={...plan(),settings:{...plan().settings,theme:'photography'}};
 assert.deepEqual(importPlans(exportPlans([themed])),[themed]);
 const store=storage();writePlans([themed],store);
 assert.equal(readPlans(store)[0].settings.theme,'photography');
 writePlans([{...themed,settings:{...themed.settings,theme:'unknown'}}],store);
 assert.deepEqual(readPlans(store),[]);
});


test('multiple and empty travel categories persist across saves and backups',()=>{
 for(const themes of [['food','shopping'],[]]){
  const themed={...plan(),settings:{...plan().settings,themes}};
  const store=storage();writePlans([themed],store);
  assert.deepEqual(readPlans(store)[0].settings.themes,themes);
  assert.deepEqual(importPlans(exportPlans([themed]))[0].settings.themes,themes);
 }
 const store=storage();
 writePlans([{...plan(),settings:{...plan().settings,themes:['unknown']}}],store);
 assert.deepEqual(readPlans(store),[]);
});


test('same destination and choices deduplicate across saving, reload and imported backups',()=>{
 const original=plan(),duplicate={...plan(),id:'different-id',savedAt:'2026-11-03T00:00:00Z',
  nearby:{places:[{name:'새 명소',lat:35,lng:129}]},cities:[{...plan().cities[0],estimatedCost:600000}]};
 const store=storage();
 assert.equal(writePlans([duplicate,original],store).length,1);
 store.setItem(STORAGE_KEY,JSON.stringify([original,duplicate]));
 assert.equal(readPlans(store).length,1);
 const backup=JSON.stringify({format:'TripBudget',version:1,plans:[duplicate]});
 assert.equal(importPlans(backup,[original]).length,1);
 assert.equal(planIdentity(original),planIdentity(duplicate));
});

test('theme order and optional empty values do not create duplicates',()=>{
 const first={...plan(),settings:{...plan().settings,themes:['food','shopping']}};
 const second={...plan(),settings:{...plan().settings,themes:['shopping','food'],departureDate:'',transportPerPerson:null}};
 assert.equal(planIdentity(first),planIdentity(second));
 assert.equal(planIdentity(plan()),planIdentity({...plan(),settings:{...plan().settings,themes:['sightseeing']}}));
});

test('new schedules and changed travel choices can be saved separately',()=>{
 const original=plan();
 const variants=[{...original,days:4},{...original,amount:2000000},
  {...original,settings:{...original.settings,people:2}},
  {...original,settings:{...original.settings,themes:['shopping']}},
  {...original,settings:{...original.settings,departureDate:'2026-12-01'}},
  {...original,settings:{...original.settings,hotelPerRoomNight:100000}},
  {...original,result:{...original.result,text:'새로운 AI 일정'}}];
 for(const variant of variants)assert.notEqual(planIdentity(original),planIdentity(variant));
 assert.equal(writePlans([original,...variants],storage()).length,variants.length+1);
});
