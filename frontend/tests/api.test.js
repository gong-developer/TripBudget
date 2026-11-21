import test from 'node:test';
import assert from 'node:assert/strict';
import {api} from '../src/api.js';

test('validation errors identify the field in Korean',async t=>{
 t.mock.method(globalThis,'fetch',async()=>new Response(JSON.stringify({detail:[{loc:['body','budget'],msg:'Input should be greater than 0'}]}),{status:422}));
 await assert.rejects(api('estimate',{}),/예산 입력을 확인/);
});

test('quota messages survive and invalid successful responses do not reach the UI',async t=>{
 t.mock.method(globalThis,'fetch',async()=>new Response(JSON.stringify({detail:'요청 한도에 도달했어요.'}),{status:429}));
 await assert.rejects(api('estimate',{}),/요청 한도/);
 globalThis.fetch=async()=>new Response('<html>proxy error</html>');
 await assert.rejects(api('health'),/서버 응답을 읽지 못했어요/);
});
