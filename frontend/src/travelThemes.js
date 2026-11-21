export const travelThemes=[
 ['relaxation','휴양','🏖️'],['sightseeing','관광','🏛️'],['food','맛집','🍜'],
 ['activity','액티비티','🎯'],['shopping','쇼핑','🛍️'],['nature','자연/트레킹','🌿'],['photography','감성사진','📷'],
];
export const defaultTheme='sightseeing';
export const themeLabel=theme=>travelThemes.find(([id])=>id===theme)?.[1]||'관광';
export const isTravelTheme=theme=>travelThemes.some(([id])=>id===theme);

export function selectedThemes(settings){
 const chosen=Array.isArray(settings?.themes)?settings.themes:[settings?.theme||defaultTheme];
 return travelThemes.map(([id])=>id).filter(id=>chosen.includes(id));
}
