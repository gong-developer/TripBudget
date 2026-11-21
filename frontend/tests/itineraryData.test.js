import test from 'node:test';
import assert from 'node:assert/strict';
import {itineraryDays,routePlaceNames} from '../src/itineraryData.js';

test('groups schedule by day and extracts only explicit place names for routing',()=>{
 const days=itineraryDays('예상 경비 100,000원\n\n1일차\n오전: 경복궁 · 산책 (이동: 도보)\n오후: 북촌 · 방문 (이동: 버스)\n저녁: 북촌 · 식사 (이동: 도보)\n\n2일차\n오전: 남산 · 전망대 방문 (이동: 버스)\n\n방문 전에 확인하세요.');
 assert.equal(days.length,2);assert.equal(days[0].slots.length,3);
 assert.deepEqual(routePlaceNames(days[0]),['경복궁','북촌']);
 assert.equal(days[1].slots[0].period,'오전');
});

test('legacy demo headings render without pretending generic text is a routable place',()=>{
 const days=itineraryDays('DAY 1 · 해운대\n오전: 주변 산책\n오후: 지역 문화 체험\n저녁: 현지 식사');
 assert.equal(days[0].day,1);assert.equal(days[0].title,'해운대');
 assert.deepEqual(routePlaceNames(days[0]),[]);
 assert.deepEqual(itineraryDays(''),[]);
});

test('rich visits retain time, stay, reason, meals and rest',()=>{
 const days=itineraryDays('1일차 · 바닷가 둘러보기\n오전: 해운대 · 09:30 · 권장 체류 90분 | 바다 풍경을 천천히 즐겨보세요. | 추천 이유: 해안의 분위기를 느끼기 좋아요. | 방문 팁: 날씨를 미리 확인하세요. | 이동: 첫 방문지\n식사: 점심 · 주변 식당에서 식사 / 저녁 · 현지식\n휴식: 오후 방문 전 쉬기');
 assert.equal(days[0].slots[0].start,'09:30');
 assert.equal(days[0].slots[0].reason,'해안의 분위기를 느끼기 좋아요.');
 assert.equal(days[0].slots[0].tip,'날씨를 미리 확인하세요.');
 assert.ok(days[0].meals.includes('점심'));
 assert.ok(days[0].rest.includes('쉬기'));
});
