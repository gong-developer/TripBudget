"""Administrative areas supplied by the travel data providers."""


def overseas_region(row):
    parts = []
    name = str(row.get('name') or row.get('city') or '').strip()
    for field in ('state', 'county', 'city', 'district'):
        value = row.get(field)
        if isinstance(value, str):
            value = value.strip()
            if value and value != name and value not in parts:
                parts.append(value)
    return ' · '.join(parts)[:200]


def domestic_region(address):
    if not isinstance(address, str):
        return ''
    # TourAPI addresses start with a province/metropolitan city, then a city/county/district.
    parts = address.split()
    if not parts:
        return ''
    region = [parts[0]]
    if len(parts) > 1 and parts[1].endswith(('시', '군', '구')):
        region.append(parts[1])
    return ' · '.join(region)[:200]
