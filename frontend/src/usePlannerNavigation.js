import {useCallback,useEffect,useRef,useState} from 'react';

const pageFromLocation=()=>window.location.hash==='#results'?'results':['','#search'].includes(window.location.hash)?'search':null;

export function usePlannerNavigation(){
 const [page,setPage]=useState(()=>pageFromLocation()||'search');
 const current=useRef(page);current.current=page;
 useEffect(()=>{
  const update=()=>{const next=pageFromLocation();if(next)setPage(next)};
  window.addEventListener('popstate',update);
  window.addEventListener('hashchange',update);
  return()=>{window.removeEventListener('popstate',update);window.removeEventListener('hashchange',update)};
 },[]);
 const navigate=useCallback((next,{replace=false}={})=>{
  const hash=next==='results'?'#results':'#search';
  if(window.location.hash!==hash){
   const previous=current.current;
   window.history[replace?'replaceState':'pushState']({tripbudgetPage:next,tripbudgetPrevious:previous},'',hash);
  }
  setPage(next);
 },[]);
 const backToSearch=useCallback(()=>{
  if(window.history.state?.tripbudgetPage==='results'&&window.history.state.tripbudgetPrevious==='search')window.history.back();
  else navigate('search',{replace:true});
 },[navigate]);
 return {page,navigate,backToSearch};
}
