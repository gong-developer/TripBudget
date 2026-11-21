import {travelThemes,defaultTheme,selectedThemes} from '../travelThemes';
const regions=[['seoul','서울'],['incheon','인천'],['gyeonggi','경기'],['gangwon','강원'],['busan','부산'],['daegu','대구'],['daejeon','대전'],['gwangju','광주'],['ulsan','울산'],['sejong','세종'],['chungbuk','충북'],['chungnam','충남'],['jeonbuk','전북'],['jeonnam','전남'],['gyeongbuk','경북'],['gyeongnam','경남'],['jeju','제주']];
export const defaultSettings={origin:'seoul',people:1,style:'standard',themes:[defaultTheme],departureDate:'',transportPerPerson:null,hotelPerRoomNight:null};
export default function TripSettings({value,onChange}){
 const chosen=selectedThemes(value);
 const toggle=id=>set('themes',chosen.includes(id)?chosen.filter(theme=>theme!==id):[...chosen,id]);
 const set=(key,next)=>onChange({...value,style:'standard',[key]:next});
 const price=(key,event,max)=>set(key,event.target.value===''?null:Math.max(0,Math.min(max,Math.trunc(Number(event.target.value)||0))));
 return <div className="trip-settings">
  <div className="settings-grid">
   <label className="block font-bold">출발 지역<select className="block mt-2" value={value.origin} onChange={e=>set('origin',e.target.value)}>{regions.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
   <label className="block font-bold">여행 인원<select className="block mt-2" value={value.people} onChange={e=>set('people',Number(e.target.value))}>{Array.from({length:10},(_,i)=><option key={i} value={i+1}>{i+1}명</option>)}</select></label>
  </div>
  <fieldset className="travel-theme-picker"><legend className="font-bold">여행 카테고리</legend>
   <p id="travel-theme-help">여러 개 선택할 수 있어요. 다시 누르면 선택이 해제돼요.</p>
   <div className="travel-theme-grid" aria-describedby="travel-theme-help">{travelThemes.map(([id,label,icon])=><button type="button" key={id} className={'travel-theme-button'+(chosen.includes(id)?' selected':'')} aria-pressed={chosen.includes(id)} onClick={()=>toggle(id)}><span aria-hidden="true">{icon}</span>{label}</button>)}</div>
   <p className="theme-budget-help">선택한 테마에 따라 식비·쇼핑·체험 등 예상 예산이 달라져요. 세부 금액은 여행지의 경비에서 확인하세요.</p>
  </fieldset>
  <details className="extra-settings"><summary>날짜·예상 경비 설정 <span>{value.departureDate?'날짜 지정':'선택'}</span></summary>
   <div className="extra-content">
   <label className="block font-bold">출발일 <span className="optional">선택</span><input className="trip-date block mt-2" type="date" max="2100-12-31" value={value.departureDate} onChange={e=>set('departureDate',e.target.value)}/></label>
   <div className="quote-heading">확인한 가격이 있나요?<p>입력한 가격을 경비 계산에 반영해요. 빈칸은 자동 추정, 0원은 무료입니다.</p></div>
   <div className="settings-grid">
    <label>왕복 교통비 <span className="optional">1인 / 원</span><input className="quote-input block mt-2" type="number" min="0" max="20000000" step="10000" value={value.transportPerPerson??''} placeholder="자동 추정" onChange={e=>price('transportPerPerson',e,20000000)}/></label>
    <label>숙박비 <span className="optional">1실 1박 / 원</span><input className="quote-input block mt-2" type="number" min="0" max="5000000" step="10000" value={value.hotelPerRoomNight??''} placeholder="자동 추정" onChange={e=>price('hotelPerRoomNight',e,5000000)}/></label>
   </div>
   </div>
  </details>
 </div>;
}
