"""Check the built website and local APIs without calling external providers."""
import json
import re
import sys
import urllib.request

base = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000').rstrip('/')
with urllib.request.urlopen(base + '/', timeout=10) as response:
    html = response.read().decode('utf-8-sig')
    assert response.status == 200 and response.headers['X-Content-Type-Options'] == 'nosniff'
    assert '/src/main.jsx' not in html
    print('Production web: HTTP 200, built assets, security headers OK')
asset = re.search(r'src="(/assets/[^"]+)"', html).group(1)
with urllib.request.urlopen(base + asset, timeout=10) as response:
    assert 'immutable' in response.headers['Cache-Control']
    print('Asset cache: immutable OK')
with urllib.request.urlopen(base + '/api/health', timeout=10) as response:
    assert json.load(response)['status'] == 'ok'
    print('Health: OK')
request = urllib.request.Request(base + '/api/estimate',
    data=json.dumps({'cityName': '부산 · 대한민국', 'days': 3, 'people': 1}).encode(),
    headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(request, timeout=10) as response:
    result = json.load(response)
    assert result['low'] <= result['total'] <= result['high']
    assert 'no-store' in response.headers['Cache-Control']
    print('Estimate API: valid range, no-store OK')
