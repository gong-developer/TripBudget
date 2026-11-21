// Existing server text remains compatible; no extra AI request is needed for cards.
export function itineraryDays(text = '') {
  const days = [];
  let active = null;
  for (const raw of text.replace(/\bDAY\s*(\d+)\b/gi, '$1일차').split('\n')) {
    const line = raw.trim();
    const heading = line.match(/^(\d+)일차(?:\s*[·:：-]\s*(.*))?$/);
    if (heading) {
      active = { day: Number(heading[1]), title: heading[2] || '', slots: [], meals:'', rest:'' };
      days.push(active);
      continue;
    }
    const slot = line.match(/^(오전|오후|저녁)\s*[:：]\s*(.+)$/);
    if (active && slot) {
      const content = slot[2].trim();
      const split = content.indexOf(' · ');
      const sections=content.split(' | ');
      const headingParts=sections[0].split(' · ');
      const rich=sections.length>=4&&/^\d{2}:\d{2}$/.test(headingParts[1]||'');
      active.slots.push({ period: slot[1], text: content,
        place: (split >= 0 ? content.slice(0, split) : '').trim(),
        ...(rich?{start:headingParts[1],stay:headingParts[2],activity:sections[1],
          reason:sections.find(value=>value.startsWith('추천 이유: '))?.slice(7),
          tip:sections.find(value=>value.startsWith('방문 팁: '))?.slice(6),
          transfer:sections.find(value=>value.startsWith('이동: '))?.slice(4)}:{}) });
      continue;
    }
    if(active&&line.startsWith('식사: '))active.meals=line.slice(4);
    if(active&&line.startsWith('휴식: '))active.rest=line.slice(4);
  }
  return days;
}

export function routePlaceNames(day) {
  return [...new Set((day?.slots || []).map(slot => slot.place).filter(Boolean))].slice(0, 3);
}
