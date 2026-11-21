import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createExpression} from '@maplibre/maplibre-gl-style-spec';
import {englishLabel,koreanLabelExpression,koreanMapStyle} from '../src/mapStyle.js';

function render(properties,translations={}){
 const result=createExpression(koreanLabelExpression(translations),'layers[0].layout.text-field');
 assert.equal(result.result,'success',JSON.stringify(result.value));
 return result.value.evaluate({}, {properties});
}

test('text labels prefer Korean and fall back to English or native names, skipping empty fields',()=>{
 const style={version:8,sources:{world:{type:'vector'}},layers:[
  {id:'country',type:'symbol',layout:{'text-field':['get','name:en'],'text-size':18}},
  {id:'roads',type:'symbol',layout:{'text-field':['get','name']}},
  {id:'water',type:'fill',paint:{'fill-color':'blue'}},
  {id:'icons',type:'symbol',layout:{'icon-image':'marker'}},
 ]};
 const before=JSON.stringify(style);
 const result=koreanMapStyle(style);
 for(const layer of result.layers.filter(layer=>layer.layout?.['text-field'])){
  assert.deepEqual(layer.layout['text-field'],koreanLabelExpression());
 }
 assert.equal(result.layers[0].layout['text-size'],18);
 assert.deepEqual(result.layers[2],style.layers[2]);
 assert.deepEqual(result.layers[3],style.layers[3]);
 assert.equal(JSON.stringify(style),before);
 assert.deepEqual(result.sources,style.sources);
});

test('actual MapLibre expressions preserve Korean, apply translations, and retain original names',()=>{
 const translations={Reykjavik:'레이캬비크'};
 assert.equal(render({'name:ko':'현지 한글명','name:en':'Reykjavik'},translations),'현지 한글명');
 assert.equal(render({'name:ko':'',name_ko:'한글명','name:en':'Reykjavik'},translations),'한글명');
 assert.equal(render({'name:ko':'','name:en':'Reykjavik'},translations),'레이캬비크');
 assert.equal(render({name_en:'Reykjavik'},translations),'레이캬비크');
 assert.equal(render({name:'Reykjavik'},translations),'레이캬비크');
 assert.equal(render({'name:en':'Untranslated',name:'原語'},translations),'Untranslated');
 assert.equal(render({'name:en':'',name:'原語'},translations),'原語');
 assert.equal(render({},translations),'');
 assert.equal(render({'name:ko':'','name:en':''}),'');
});

test('English model receives English labels or Latin names, never unsupported native scripts',()=>{
 assert.equal(englishLabel({'name:en':'Kyoto',name:'京都'}),'Kyoto');
 assert.equal(englishLabel({name_en:'Reykjavik'}),'Reykjavik');
 assert.equal(englishLabel({name:'São Paulo'}),'São Paulo');
 assert.equal(englishLabel({name:'京都'}),null);
 assert.equal(englishLabel({name:'123'}),null);
});
