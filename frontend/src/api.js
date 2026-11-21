const base = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/$/, '');
function errorMessage(data,fallback){
 if(typeof data?.detail==='string')return data.detail;
 if(Array.isArray(data?.detail)){
  const labels={budget:'예산',days:'여행 기간',people:'여행 인원',theme:'여행 카테고리',themes:'여행 카테고리',origin:'출발 지역',departureDate:'출발일',countryCode:'국가',cityName:'여행지',transportPerPerson:'왕복 교통비',hotelPerRoomNight:'숙박비',names:'지명 목록',departureAirport:'출발 공항',arrivalAirport:'도착 공항'};
  const fields=[...new Set(data.detail.map(error=>{
   const parts=Array.isArray(error?.loc)?error.loc:[];
   const key=parts.find(part=>typeof part==='string'&&Object.hasOwn(labels,part));
   return key?labels[key]:null;
  }).filter(Boolean))];
  return fields.length?`${fields.join('·')} 입력을 확인해주세요.`:'입력한 여행 조건을 확인해주세요.';
 }
 return fallback;
}
export async function compareDestinations(body, signal, onProgress) {
  try { return await comparisonStream(body, signal, onProgress); }
  catch(error) {
    if(error.name==='AbortError')throw error;
    if(error.name==='TimeoutError')throw new Error('여행지 조회 시간이 초과됐어요. 다시 시도해주세요.');
    if(error instanceof TypeError)throw new Error('서버에 연결할 수 없어요. 인터넷 연결을 확인하고 잠시 후 다시 시도해주세요.');
    if(error instanceof SyntaxError)throw new Error('조회 진행 정보를 읽지 못했어요. 다시 시도해주세요.');
    throw error;
  }
}
async function comparisonStream(body, signal, onProgress) {
  const response = await fetch(base + '/api/destinations/compare', {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body),
    signal:AbortSignal.any([signal, AbortSignal.timeout(65000)].filter(Boolean)),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(errorMessage(data,'여행지 비교 요청을 처리하지 못했어요.'));
  }
  if (!response.body) throw new Error('조회 결과를 읽을 수 없어요. 다시 시도해주세요.');
  const reader = response.body.getReader(), decoder = new TextDecoder();
  let buffer = '', result = null;
  const consume = line => {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.type === 'error') throw new Error(event.message || '여행지 조회에 실패했어요.');
    if (event.type === 'progress') onProgress(event.phase);
    if (event.type === 'result') result = event;
  };
  try {
    while (true) {
      const {value, done} = await reader.read();
      buffer += decoder.decode(value, {stream:!done});
      const lines = buffer.split('\n'); buffer = lines.pop();
      lines.forEach(consume);
      if (done) { consume(buffer); break; }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
  if (!result?.cities?.length) throw new Error('비교할 여행지를 받지 못했어요. 다시 시도해주세요.');
  return result;
}

export async function api(path, body, signal) {
  let response;
  try {
    response = await fetch(base + '/api/' + path, { method: body ? 'POST' : 'GET',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.any([signal, AbortSignal.timeout(105000)].filter(Boolean)) });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error(error.name === 'TimeoutError' ? '응답 시간이 초과됐어요. 다시 시도해주세요.' : '서버에 연결할 수 없어요. 인터넷 연결을 확인하고 잠시 후 다시 시도해주세요.');
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorMessage(data,'요청을 처리하지 못했어요. 잠시 후 다시 시도해주세요.'));
  if(data===null||typeof data!=='object')throw new Error('서버 응답을 읽지 못했어요. 잠시 후 다시 시도해주세요.');
  return data;
}
