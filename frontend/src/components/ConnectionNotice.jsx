import {useEffect,useState} from 'react';

export default function ConnectionNotice(){
 const [online,setOnline]=useState(()=>navigator.onLine);
 useEffect(()=>{
  const update=()=>setOnline(navigator.onLine);
  window.addEventListener('online',update);window.addEventListener('offline',update);
  return()=>{window.removeEventListener('online',update);window.removeEventListener('offline',update);};
 },[]);
 return online?null:<p className="connection-notice" role="status">인터넷 연결이 끊겼어요. 연결 후 다시 시도해주세요. 저장한 계획은 유지돼요.</p>;
}
