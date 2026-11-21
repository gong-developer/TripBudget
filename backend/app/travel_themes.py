"""Trip interests are independent of the legacy spending tiers."""
from typing import Literal

TravelTheme = Literal['relaxation','sightseeing','food','activity','shopping','nature','photography']
THEMES = {
    'relaxation':('휴양','쉬어가는 방문과 휴식 시간을 우선하고 여유 있게 동선을 구성하라.'),
    'sightseeing':('관광','확인된 주요 볼거리와 지역 문화를 다양하게 경험하도록 구성하라.'),
    'food':('맛집','점심·저녁의 현지 음식 탐방과 주변 식사 구역 선택을 구체적으로 제안하라. 확인되지 않은 식당명이나 영업정보를 만들지 마라.'),
    'activity':('액티비티','확인된 명소에서 가능한 체험과 활동을 우선하라. 활동 가능 여부·예약 조건은 확인하도록 안내하라.'),
    'shopping':('쇼핑','자료에서 확인되는 시장·상점가를 우선하고 구매·구경할 방향과 여유 시간을 제안하라.'),
    'nature':('자연/트레킹','확인된 공원·자연 경관과 걷기 좋은 공간을 우선하라. 확인되지 않은 등산로·난이도·개방 여부를 단정하지 마라.'),
    'photography':('감성사진','확인된 명소의 풍경과 분위기를 촬영하는 방향으로 구성하라. 공개 관람 구역에서의 촬영을 제안하고 일출·일몰 시각은 단정하지 마라.'),
}


def theme_instruction(themes):
    if isinstance(themes,str):
        themes=[themes]
    selected=[THEMES[key] for key in (themes or []) if key in THEMES]
    if not selected:
        return ' 선택한 여행 카테고리가 없으므로 확인된 명소를 균형 있게 방문하는 일반 일정을 구성하라.'
    labels=' · '.join(label for label,_ in selected)
    directions=' '.join(direction for _,direction in selected)
    return f' 선택한 여행 카테고리는 {labels}이다. 선택한 카테고리들을 일정 전반에 균형 있게 반영하라. {directions} 제공된 장소·좌표 범위 안에서 선호를 반영하고, 해당 테마에 맞는 자료가 부족하면 없는 명소나 시설을 만들어내지 마라.'
