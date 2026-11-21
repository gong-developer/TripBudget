"""Prefer upper estimates close to the budget, with variety among close matches."""
import random
from fastapi import HTTPException
from .costs import priced_city
from .travel_policy import allowed_destination


def choose_budget_destination(candidates, options, budget, category):
    unique = {city['cityName']: city for city in candidates
              if allowed_destination(city) and (category == 'all' or city['category'] == category)}
    affordable = []
    for city in unique.values():
        priced = priced_city(city, options)
        if priced['costBreakdown']['high'] <= budget:
            affordable.append((city, priced))
    if not affordable:
        raise HTTPException(404, '조회한 후보 중 예상 비용 상한이 예산 이내인 여행지가 없어요. 기간·인원·교통·숙박비·예산을 조정해주세요.')
    best = max(priced['costBreakdown']['high'] for _, priced in affordable)
    # Within five percentage points of the best utilization; never exceed budget.
    close = [(city, priced) for city, priced in affordable
             if (best - priced['costBreakdown']['high']) * 100 <= budget * 5]
    return random.choice(close)


def choose_budget_destinations(candidates, options, budget, category):
    """Return every distinct affordable candidate, ordered by upper cost."""
    unique = {city['cityName']: city for city in candidates
              if allowed_destination(city) and (category == 'all' or city['category'] == category)}
    affordable = []
    for city in unique.values():
        priced = priced_city(city, options)
        if priced['costBreakdown']['high'] <= budget:
            affordable.append((city, priced))
    if not affordable:
        raise HTTPException(404, '조회한 후보 중 예상 비용 상한이 예산 이내인 여행지가 없어요. 기간·인원·교통·숙박비·예산을 조정해주세요.')
    return sorted(affordable, key=lambda item: (item[1]['costBreakdown']['high'], item[0]['cityName']))
