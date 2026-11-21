import test from 'node:test';
import assert from 'node:assert/strict';
import {filterCountries,countryStyle} from '../src/countries.js';

const countries=[{code:'jp',name:'일본',englishName:'Japan'},{code:'sg',name:'싱가포르',englishName:'Singapore'},{code:'kr',name:'대한민국',englishName:'South Korea'}];
test('country search accepts Korean, English and country codes',()=>{
 assert.equal(filterCountries(countries,' 일본 ')[0].code,'jp');
 assert.equal(filterCountries(countries,'SINGA')[0].code,'sg');
 assert.equal(filterCountries(countries,'kr')[0].name,'대한민국');
 assert.equal(filterCountries(countries,'한국')[0].code,'kr');
 assert.deepEqual(filterCountries(countries,''),[]);
 assert.deepEqual(filterCountries(countries,'없는나라'),[]);
});
test('only selected country receives a highlighted border and fill',()=>{
 assert.ok(countryStyle('jp','jp').fillOpacity>countryStyle('sg','jp').fillOpacity);
 assert.ok(countryStyle('jp','jp').weight>countryStyle('sg','jp').weight);
 assert.equal(countryStyle('jp','').fillOpacity,countryStyle('sg','').fillOpacity);
});
