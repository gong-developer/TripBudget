import {useState} from 'react';

const colors={transport:'#4169d8',access:'#7498ee',lodging:'#8a63ce',food:'#e3943c',local:'#28a397',sights:'#d96880',insurance:'#6d8e5a',data:'#8d789a',buffer:'#8796ad',shopping:'#c65db3',activities:'#e17650',trekking:'#538d52',leisure:'#4d9db9'};
const won=value=>value.toLocaleString('ko-KR')+'원';
const percent=value=>`${(value*100).toLocaleString('ko-KR',{maximumFractionDigits:1})}%`;

export default function CostChart({items}){
 const [activeKey,setActiveKey]=useState(null);
 const total=items.reduce((sum,item)=>sum+item.amount,0);
 let offset=0;
 const slices=items.filter(item=>item.amount>0).map(item=>{
  const share=item.amount/total;
  const slice={...item,share,offset,color:colors[item.key]||'#648b9e'};
  offset+=share*100;
  return slice;
 });
 const active=slices.find(item=>item.key===activeKey);
 return <figure className="cost-chart" aria-label="항목별 예상 경비 비중">
  <figcaption><strong>어디에 얼마나 쓰나요?</strong><span>항목을 누르면 그래프에서 비중을 확인할 수 있어요.</span></figcaption>
  <div className="cost-chart-layout">
   <div className="cost-donut">
    <svg viewBox="0 0 240 240" role="img" aria-label={total>0?`예상 경비 ${won(total)}의 항목별 비중. ${slices.map(item=>`${item.label} ${percent(item.share)}`).join(', ')}`:'예상 경비 0원'}>
     <circle cx="120" cy="120" r="94" fill="none" stroke="#edf1f7" strokeWidth="26"/>
     {slices.map(item=><circle key={item.key} cx="120" cy="120" r="94" fill="none" stroke={item.color} strokeWidth={activeKey===item.key?32:26} pathLength="100" strokeDasharray={`${item.share*100} ${100-item.share*100}`} strokeDashoffset={-item.offset} transform="rotate(-90 120 120)" opacity={active&&active.key!==item.key?0.3:1}>
      <title>{item.label}: {won(item.amount)} ({percent(item.share)})</title>
     </circle>)}
    </svg>
    <div className="cost-donut-center" aria-live="polite"><span>{active?.label||'전체 예상 경비'}</span><strong>{won(active?.amount??total)}</strong><small>{active?`전체의 ${percent(active.share)}`:'항목별 비용 비중'}</small></div>
   </div>
   <ul className="cost-chart-legend">{items.map(item=>{
    const share=total>0?item.amount/total:0;
    const color=colors[item.key]||'#648b9e';
    return <li key={item.key}><button type="button" aria-pressed={activeKey===item.key} disabled={item.amount===0} onClick={()=>setActiveKey(activeKey===item.key?null:item.key)}>
     <span className="cost-chart-dot" style={{backgroundColor:color}} aria-hidden="true"/>
     <span className="cost-chart-item"><span>{item.label}</span><span className="cost-chart-track" aria-hidden="true"><i style={{width:`${share*100}%`,backgroundColor:color}}/></span></span>
     <strong>{won(item.amount)}</strong><small>{percent(share)}</small>
    </button></li>;
   })}</ul>
  </div>
 </figure>;
}
