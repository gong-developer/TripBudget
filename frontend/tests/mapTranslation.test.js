import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createExpression} from '@maplibre/maplibre-gl-style-spec';
import {attachMapTranslation} from '../src/mapTranslation.js';

test('unregistered labels do not trigger a full map text layout update',async t=>{
 t.mock.timers.enable({apis:['setTimeout','Date']});
 let requests=0,updates=0;
 const events={};
 const map={
  isStyleLoaded:()=>true,
  getStyle:()=>({layers:[{id:'places',type:'symbol',layout:{'text-field':'name'}}]}),
  queryRenderedFeatures:()=>[{properties:{'name:en':'Unregistered Place'}}],
  setLayoutProperty:()=>updates++,
  on:(name,handler)=>{events[name]=handler;},
  off:name=>{delete events[name];},
 };
 t.mock.method(globalThis,'fetch',async()=>{
  requests++;
  return new Response(JSON.stringify({translations:{},available:true}));
 });
 const controller=new AbortController();
 const stop=attachMapTranslation(map,controller.signal,()=>{});
 t.after(()=>{stop();controller.abort();});
 t.mock.timers.tick(500);await new Promise(setImmediate);
 events.idle();t.mock.timers.tick(500);await new Promise(setImmediate);
 assert.equal(requests,1);
 assert.equal(updates,0);
});

test('visible missing labels reach the translation endpoint and update the map without repeating requests',async t=>{
 t.mock.timers.enable({apis:['setTimeout','Date']});
 const requests=[],updates=[],events={},statuses=[];
 const properties=[{'name:ko':'도쿄','name:en':'Tokyo'},{'name:en':'Reykjavik'},{'name:en':'Reykjavik'},{name:'京都'}];
 const map={
  isStyleLoaded:()=>true,
  getStyle:()=>({layers:[{id:'places',type:'symbol',layout:{'text-field':'name'}}]}),
  queryRenderedFeatures:()=>properties.map(properties=>({properties})),
  setLayoutProperty:(...args)=>updates.push(args),
  on:(name,handler)=>{events[name]=handler;},
  off:name=>{delete events[name];},
 };
 t.mock.method(globalThis,'fetch',async (url,options)=>{
  requests.push({url,body:JSON.parse(options.body)});
  return new Response(JSON.stringify({translations:{Reykjavik:'레이캬비크'},available:true}));
 });
 const controller=new AbortController();
 const stop=attachMapTranslation(map,controller.signal,status=>statuses.push(status));
 t.after(()=>{stop();controller.abort();});
 t.mock.timers.tick(500);
 await new Promise(setImmediate);
 assert.deepEqual(requests,[{url:'/api/map/translate',body:{names:['Reykjavik']}}]);
 assert.deepEqual(statuses,['translating','ready']);
 assert.equal(updates[0][0],'places');
 const expression=createExpression(updates[0][2],'layers[0].layout.text-field');
 assert.equal(expression.result,'success');
 assert.equal(expression.value.evaluate({}, {properties:properties[1]}),'레이캬비크');
 events.idle();t.mock.timers.tick(500);
 await new Promise(setImmediate);
 assert.equal(requests.length,1);
 stop();
 assert.equal(events.idle,undefined);
});
