import json


def quality_response(days):
    return json.dumps({'days':[{
        'title':f'지역의 매력을 살펴보는 {day+1}일차',
        'visits':[{'place':day*2+index,'start':start,'minutes':90,
                   'activity':f'{day*2+index+1}번째 방문에서 주변 풍경과 볼거리를 차분히 살펴보세요.',
                   'reason':'이 구역의 분위기를 경험하기 좋은 장소입니다.',
                   'tip':'운영 여부와 방문 조건을 미리 확인하세요.'}
                  for index,start in enumerate(('09:30','14:00'))],
        'lunch':'오전 방문지 주변에서 가벼운 현지식으로 점심을 드세요.',
        'dinner':'마지막 방문지 부근에서 저녁을 먹고 숙소로 돌아가세요.',
        'rest':'오후 방문 전 가까운 실내 공간에서 잠시 쉬어가세요.',
    } for day in range(days)]},ensure_ascii=False)


async def grounded_context(data):
    return {**data,'places':[{'name':f'검증 명소 {index}','originalName':f'검증 명소 {index}',
                             'lat':35+index*.001,'lng':129,'source':'test'} for index in range(42)],
            'contextNotes':['운영시간은 방문 전에 확인해주세요.']}
