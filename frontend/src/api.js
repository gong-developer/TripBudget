const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
export async function api(path, body, signal) {
  let response;
  try {
    response = await fetch(base + '/api/' + path, { method: body ? 'POST' : 'GET',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.any([signal, AbortSignal.timeout(105000)].filter(Boolean)) });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error(error.name === 'TimeoutError' ? '응답 시간이 초과됐어요. 다시 시도해주세요.' : '서버에 연결할 수 없어요. 백엔드 실행 상태를 확인해주세요.');
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : '요청을 처리하지 못했어요. 입력값을 확인해주세요.');
  return data;
}
