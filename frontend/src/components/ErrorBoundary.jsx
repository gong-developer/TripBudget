import {Component} from 'react';

export default class ErrorBoundary extends Component {
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true};}
 render(){
  if(this.state.failed)return <main className="recovery-page"><section className="panel" role="alert"><h1>화면을 불러오지 못했어요</h1><p>새로고침해서 다시 시작해주세요. 이 브라우저에 저장한 여행 계획은 유지돼요.</p><button className="primary-action" onClick={()=>window.location.reload()}>다시 불러오기</button></section></main>;
  return this.props.children;
 }
}
