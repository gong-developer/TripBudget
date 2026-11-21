export const SECTORS=8;
export const SPIN_DURATION=900;

export function rouletteAnimation(startAngle,sector){
 const target=((SECTORS-sector)%SECTORS)*(360/SECTORS);
 const end=startAngle+360*4+((target-startAngle%360+360)%360);
 return {keyframes:[{transform:`rotate(${startAngle}deg)`},{transform:`rotate(${end}deg)`}],
  options:{duration:3200,easing:'cubic-bezier(.12,.72,.08,1)',fill:'forwards'}};
}

export function winningSector(city){
 // Stable visual slot for the destination already selected by the server.
 return [...city.cityName].reduce((hash,letter)=>(hash*31+letter.codePointAt(0))>>>0,0)%SECTORS;
}
