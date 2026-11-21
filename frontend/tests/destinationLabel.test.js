import {test} from 'node:test';
import assert from 'node:assert/strict';
import {destinationLabel,destinationRegion,isKoreanLabel,safePlaceName} from '../src/destinationLabel.js';
test('recommendation card uses Korean display name and keeps original identity',()=>{
 const city={cityName:'یزد · Iran',displayName:'야즈드 · 이란',namePolicy:'registered-v1'};
 assert.equal(destinationLabel(city),'야즈드 · 이란');
 assert.equal(city.cityName,'یزد · Iran');
});

test('legacy machine names and malformed original fields cannot reach place cards',()=>{
 assert.equal(safePlaceName({name:'전체메뉴',originalName:'Seomyeon Shopping District',nameTranslated:true}).name,'Seomyeon Shopping District');
 assert.equal(safePlaceName({name:'전체메뉴',originalName:{bad:true},nameTranslated:true}).name,'명소 이름 재조회 필요');
 assert.equal(safePlaceName({name:'센트럴 파크',originalName:'Central Park',namePolicy:'registered-v1'}).name,'센트럴 파크');
});
test('legacy known labels are converted without a server restart',()=>{
 assert.equal(destinationLabel({cityName:'Tehran · Iran',countryCode:'ir'}),'테헤란 · 이란');
 assert.equal(destinationLabel({cityName:'London · UK'}),'런던 · 영국');
});
test('unknown names retain original spelling instead of inventing Korean labels',()=>{
 assert.equal(destinationLabel({cityName:'شیراز · Iran'}),'شیراز · 이란');
 assert.equal(destinationLabel({cityName:'Valdosta · US',originalName:'Valdosta',displayName:'스낵 바 · 미국',countryCode:'us'}),'Valdosta · 미국');
 assert.equal(isKoreanLabel('테헤란 · 이란'),true);
 assert.equal(isKoreanLabel('테헤란 Tehran · 이란'),false);
 assert.equal(isKoreanLabel('تهران'),false);
});

test('administrative regions include the country and preserve provider spellings',()=>{
 assert.equal(destinationRegion({cityName:'Sapporo · Japan',countryCode:'jp',category:'international',regionName:'北海道'}),'일본 · 北海道');
 assert.equal(destinationRegion({cityName:'경포해변 · 강원특별자치도 강릉시 창해로 514',category:'domestic',regionName:'강원특별자치도 · 강릉시'}),'강원특별자치도 · 강릉시');
});
test('older destinations recover domestic administrative areas without displaying street addresses',()=>{
 assert.equal(destinationRegion({cityName:'경포해변 · 강원특별자치도 강릉시 창해로 514',category:'domestic'}),'강원특별자치도 · 강릉시');
 assert.equal(destinationRegion({cityName:'세종호수공원 · 세종특별자치시 호수공원길 155',category:'domestic'}),'세종특별자치시');
 assert.equal(destinationRegion({cityName:'Tokyo · Japan',countryCode:'jp',category:'international'}),'일본 · 세부 지역 정보 없음');
 assert.equal(destinationRegion({cityName:'부산',category:'domestic'}),'세부 지역 정보 없음');
});
