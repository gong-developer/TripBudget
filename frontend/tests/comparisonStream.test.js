import test from 'node:test';
import assert from 'node:assert/strict';
import {compareDestinations} from '../src/api.js';

test('reads incremental progress and final candidates even across UTF-8 chunk boundaries',async()=>{
 const original=globalThis.fetch, stages=[];
 const text='{"type":"progress","phase":"fetch"}\n{"type":"progress","phase":"compare"}\n{"type":"progress","phase":"names"}\n{"type":"result","cities":[{"cityName":"부산"}]}';
 const bytes=new TextEncoder().encode(text);
 globalThis.fetch=async()=>new Response(new ReadableStream({start(controller){
  for(let i=0;i<bytes.length;i+=7)controller.enqueue(bytes.slice(i,i+7));controller.close();
 }}));
 try{
  const result=await compareDestinations({budget:1000000},undefined,phase=>stages.push(phase));
  assert.deepEqual(stages,['fetch','compare','names']);assert.equal(result.cities[0].cityName,'부산');
 }finally{globalThis.fetch=original;}
});

test('streamed provider errors remain errors instead of empty successful results',async()=>{
 const original=globalThis.fetch;
 globalThis.fetch=async()=>new Response('{"type":"error","message":"사용 한도 초과","status":429}\n');
 try{await assert.rejects(compareDestinations({budget:1000000},undefined,()=>{}),/사용 한도 초과/);}
 finally{globalThis.fetch=original;}
});
