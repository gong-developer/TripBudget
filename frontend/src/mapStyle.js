// Prefer Korean labels, retaining a readable name when Korean is unavailable.
import {REJECTED_NAMES} from './destinationLabel.js';
const labelField = key=>{
 const value=['to-string',['coalesce',['get',key],'']];
 return ['case',['in',value,['literal',REJECTED_NAMES]],'',value];
};
const firstLabel = values=>['case',...values.flatMap(value=>[['!=',value,''],value]),''];
export function englishLabel(properties){
 const english=properties['name:en']||properties.name_en;
 if(typeof english==='string'&&english.trim())return english.trim();
 const native=properties.name;
 return typeof native==='string'&&/^[\p{Script=Latin}\p{Number}\p{Punctuation}\s]+$/u.test(native)&&/[\p{Script=Latin}]/u.test(native)?native.trim():null;
}
export function koreanLabelExpression(translations={}){
 const entries=Object.entries(translations);
 const translated=entries.length?['match',firstLabel(['name:en','name_en','name'].map(labelField)),
  ...entries.flatMap(([name,label])=>[name,label]),'']:'';
 return firstLabel([labelField('name:ko'),labelField('name_ko'),translated,
  ...['name:en','name_en','name'].map(labelField)]);
}
export function koreanMapStyle(style,translations={}){
 return {...style,layers:style.layers.map(layer=>{
  if(layer.type!=='symbol'||!layer.layout?.['text-field'])return layer;
  return {...layer,layout:{...layer.layout,'text-field':koreanLabelExpression(translations)}};
 })};
}
