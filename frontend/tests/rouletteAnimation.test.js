import test from 'node:test';
import assert from 'node:assert/strict';
import {rouletteAnimation,winningSector,SECTORS} from '../src/rouletteAnimation.js';

test('roulette continues from its current angle and stops with the winning sector at the pointer',()=>{
 for(const start of [0,17,359,721.5,5943]){
  for(let sector=0;sector<SECTORS;sector++){
   const {keyframes,options}=rouletteAnimation(start,sector);
   const end=Number(keyframes[1].transform.match(/rotate\((.+)deg\)/)[1]);
   assert.equal(keyframes[0].transform,`rotate(${start}deg)`);
   assert.ok(end-start>=360*4);
   assert.ok(Math.abs((end+sector*360/SECTORS)%360)<1e-8);
   assert.ok(options.duration>=2500);
  }
 }
});

test('visual roulette slots are stable without changing the server destination',()=>{
 for(const cityName of ['강릉시 · 강원특별자치도','Paris · France','京都市 · Japan']){
  const city={cityName};
  assert.equal(winningSector(city),winningSector(city));
  assert.ok(winningSector(city)>=0&&winningSector(city)<SECTORS);
  assert.equal(city.cityName,cityName);
 }
});
