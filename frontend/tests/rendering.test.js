import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

async function component(path){
 const result=await build({entryPoints:[path],bundle:true,platform:'node',format:'cjs',jsx:'automatic',write:false,external:['react','react/jsx-runtime']});
 const module={exports:{}};
 Function('require','module','exports',result.outputFiles[0].text)(createRequire(import.meta.url),module,module.exports);
 return module.exports.default;
}

test('AI text is escaped and schedules render without removed route controls',async()=>{
 const Itinerary=await component('src/components/Itinerary.jsx');
 const html=renderToStaticMarkup(createElement(Itinerary,{city:{cityName:'부산 · 대한민국'},days:1,
  result:{source:'gemini',text:'1일차\n오전: <script>alert(1)</script>\n오후: 해변 산책\n저녁: 식사'}}));
 assert.ok(html.includes('1일차'));
 assert.ok(!html.includes('<script>'));
 assert.ok(html.includes('&lt;script&gt;'));
 assert.ok(!html.includes('이 날짜 지도에 표시'));
 assert.ok(!html.includes('지도 이동 수단'));
});

test('saved plans expose backup and import actions without unsafe title HTML',async()=>{
 const SavedPlans=await component('src/components/SavedPlans.jsx');
 const html=renderToStaticMarkup(createElement(SavedPlans,{plans:[{id:'one',title:'<img src=x>',days:3,
  settings:{people:1},savedAt:'2026-11-01T00:00:00Z'}]}));
 assert.ok(html.includes('계획 백업')&&html.includes('백업 불러오기'));
 assert.ok(html.includes('type="file"'));
 assert.ok(!html.includes('<img src=x>'));
});

test('rich itinerary shows practical details and explicit regeneration',async()=>{
 const Itinerary=await component('src/components/Itinerary.jsx');
 const text='1일차 · 바다 산책\n오전: 해운대 · 09:30 · 권장 체류 90분 | 해안 풍경을 충분히 감상하세요. | 추천 이유: 바닷가 분위기를 즐기기 좋아요. | 방문 팁: 날씨를 확인하세요. | 이동: 첫 방문지\n식사: 점심 · 인근 식당 / 저녁 · 현지식\n휴식: 오후 방문 전 카페에서 쉬세요.\n• 실제 운영시간은 확인해주세요.';
 const html=renderToStaticMarkup(createElement(Itinerary,{city:{cityName:'부산 · 대한민국'},days:1,result:{source:'gemini',text}}));
 for(const label of ['09:30','권장 체류 90분','추천 이유','방문 팁','식사 제안','휴식','일정 다시 만들기','실제 운영시간은 확인해주세요.'])assert.ok(html.includes(label),label);
});

test('price groups expose separately labelled refresh actions and explain exhausted pools',async()=>{
 const DestinationList=await component('src/components/DestinationList.jsx');
 const city={cityName:'강릉시',estimatedCost:600000,category:'domestic',costBreakdown:{high:700000}};
 const html=renderToStaticMarkup(createElement(DestinationList,{people:1,onRefresh:()=>{},groups:[
  {lower:500000,upper:1000000,totalCount:6,cities:[city]},
  {lower:1000000,upper:1500000,totalCount:1,cities:[{...city,cityName:'제주시',estimatedCost:1100000}]},
 ]}));
 assert.ok(html.includes('50만원 이상 100만원 미만 여행지 새로고침'));
 assert.ok(html.includes('100만원 이상 150만원 미만 여행지 새로고침'));
 assert.equal((html.match(/class="destination-refresh"/g)||[]).length,2);
 assert.equal((html.match(/disabled=""/g)||[]).length,1);
 assert.ok(html.includes('다른 후보 없음'));
});

test('result tabs require a destination before opening sights or an itinerary',async()=>{
 const ResultsTabs=await component('src/components/ResultsTabs.jsx');
 const initial=renderToStaticMarkup(createElement(ResultsTabs,{active:'destinations',hasSelection:false,onChange:()=>{}}));
 assert.equal((initial.match(/role="tab"/g)||[]).length,3);
 assert.equal((initial.match(/disabled=""/g)||[]).length,2);
 assert.ok(initial.includes('aria-controls="result-panel-destinations"'));
 const selected=renderToStaticMarkup(createElement(ResultsTabs,{active:'itinerary',hasSelection:true,onChange:()=>{}}));
 assert.ok(!selected.includes('disabled=""'));
 assert.ok(selected.includes('id="result-tab-itinerary" role="tab" type="button" aria-selected="true"'));
});

test('travel categories are seven toggle buttons instead of spending-style dropdown',async()=>{
 const TripSettings=await component('src/components/TripSettings.jsx');
 const html=renderToStaticMarkup(createElement(TripSettings,{value:{origin:'seoul',people:1,style:'standard',themes:['food','shopping'],departureDate:''},onChange:()=>{}}));
 for(const label of ['휴양','관광','맛집','액티비티','쇼핑','자연/트레킹','감성사진'])assert.ok(html.includes(label));
 assert.equal((html.match(/aria-pressed=/g)||[]).length,7);
 assert.equal((html.match(/aria-pressed="true"/g)||[]).length,2);
 for(const removed of ['알뜰한 여행','보통의 여행','여유로운 여행'])assert.ok(!html.includes(removed));
});
