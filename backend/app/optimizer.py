def recommend(cities: list[dict], budget: int, limit: int = 3) -> list[dict]:
    """Sparse 0/1 knapsack with cardinality. No currency rounding.
    Prefer exactly limit cities if feasible; otherwise largest feasible count.
    Maximize satisfaction within that count, then prefer lower total cost.
    """
    states = {(0, 0): (0, ())}
    for index, city in enumerate(cities):
        updates = dict(states)
        for (count, cost), (score, selected) in states.items():
            new_cost = cost + city["estimatedCost"]
            if count >= limit or new_cost > budget:
                continue
            key = (count + 1, new_cost)
            candidate = (score + city["satisfaction"], selected + (index,))
            if key not in updates or candidate[0] > updates[key][0]:
                updates[key] = candidate
        states = updates
    best = max(states, key=lambda key: (key[0], states[key][0], -key[1]))
    return [cities[i] for i in states[best][1]]
