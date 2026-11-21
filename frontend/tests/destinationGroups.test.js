import test from 'node:test';
import assert from 'node:assert/strict';
import {groupDestinations,refreshDestinationGroup} from '../src/destinationGroups.js';

const city=(cityName,estimatedCost)=>({cityName,estimatedCost});

test('50만원 boundaries belong to one group, including exact boundaries',()=>{
 const groups=groupDestinations([city('zero',0),city('below',499999),city('exact',500000),city('next',1000000)]);
 assert.deepEqual(groups.map(group=>[group.lower,group.upper,group.cities.map(item=>item.cityName)]),[
  [1000000,1500000,['next']],[500000,1000000,['exact']],[0,500000,['below','zero']]
 ]);
});

test('each nonempty group shows at most three, descending, without mutating candidates',()=>{
 const cities=[city('a',600000),city('b',900000),city('c',700000),city('d',800000),city('e',2000000)];
 const original=[...cities];
 const groups=groupDestinations(cities,()=>0.999999);
 assert.equal(groups.length,2);
 assert.deepEqual(groups[1].cities.map(item=>item.estimatedCost),[900000,800000,700000]);
 assert.equal(groups[1].totalCount,4);
 assert.deepEqual(cities,original);
 assert.deepEqual(groupDestinations([]),[]);
});

test('random sampling can select cheaper candidates and never repeats a candidate',()=>{
 const cities=[city('a',600000),city('b',900000),city('c',700000),city('d',800000)];
 const first=groupDestinations(cities,()=>0)[0];
 const second=groupDestinations(cities,()=>0.999999)[0];
 assert.deepEqual(first.cities.map(item=>item.estimatedCost),[800000,700000,600000]);
 assert.notDeepEqual(first.cities,second.cities);
 assert.equal(new Set(first.cities.map(item=>item.cityName)).size,3);
 assert.equal(new Set([...first.cities,...second.cities].map(item=>item.cityName)).size,4);
 assert.equal(first.totalCount,4);
});

test('refresh changes only its price group and prefers entirely different destinations',()=>{
 const cities=[...Array.from({length:6},(_,i)=>city(`a${i}`,600000+i*10000)),city('other group',1200000)];
 const groups=groupDestinations(cities,()=>.999999);
 const before=JSON.stringify({cities,groups});
 const refreshed=refreshDestinationGroup(groups,cities,500000,()=>.999999);
 assert.equal(refreshed[0],groups[0]);
 assert.equal(refreshed[1].totalCount,6);
 assert.equal(refreshed[1].cities.length,3);
 assert.ok(refreshed[1].cities.every(next=>!groups[1].cities.some(previous=>previous.cityName===next.cityName)));
 assert.ok(refreshed[1].cities.every(item=>item.estimatedCost>=500000&&item.estimatedCost<1000000));
 assert.equal(JSON.stringify({cities,groups}),before);
});

test('small pools replace all available alternatives and never duplicate cards',()=>{
 for(const count of [4,5]){
  const cities=Array.from({length:count},(_,i)=>city(String(i),600000+i*10000));
  const groups=groupDestinations(cities,()=>.999999);
  const refreshed=refreshDestinationGroup(groups,cities,500000,()=>.999999)[0];
  assert.equal(refreshed.cities.length,3);
  assert.equal(new Set(refreshed.cities.map(item=>item.cityName)).size,3);
  assert.equal(refreshed.cities.filter(item=>!groups[0].cities.includes(item)).length,count-3);
  assert.deepEqual(refreshed.cities.map(item=>item.estimatedCost),refreshed.cities.map(item=>item.estimatedCost).sort((a,b)=>b-a));
 }
});

test('refresh leaves unavailable groups unchanged and candidate counts ignore duplicates',()=>{
 const cities=[city('a',500000),city('b',999999),city('a',500000)];
 const groups=groupDestinations(cities);
 assert.equal(groups[0].totalCount,2);
 assert.equal(refreshDestinationGroup(groups,cities,500000),groups);
 assert.equal(refreshDestinationGroup(groups,cities,1000000),groups);
});
