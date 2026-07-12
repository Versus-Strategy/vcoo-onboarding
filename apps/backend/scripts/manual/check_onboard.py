import os
os.environ['POSTGRES_URL'] = 'sqlite:///./test.db'
os.environ.setdefault('MASTER_KEY', 'dev-key-only-for-local')
os.environ['SECRET_KEY'] = 'testsecret'
os.environ['FRONTEND_URL'] = 'https://vcoo-onboarding.vercel.app'
os.environ['DASHBOARD_URL'] = 'https://vcoo-dashboard.vercel.app'
os.environ['CONTROL_PLANE'] = 'https://vcoo-onboarding.vercel.app'
import sys
sys.path.insert(0, '.')
from fastapi.testclient import TestClient
import requests
client = TestClient(application)
resp = client.post('/vcoo', json={'name':'test-vcoo','modules':['core']})
if resp.status_code != 200:
    print('Error creating VCOO:', resp.text); sys.exit(1)
data = resp.json()
print('VCOO ID:', data['id'])
token = data.get('token')
if not token:
    resp2 = client.get(f'/vcoo/{data["id"]}/provision-token')
    if resp2.status_code != 200:
        print('Failed to get token:', resp2.text); sys.exit(1)
    token = resp2.json().get('token')
print('Token obtained (len={})'.format(len(token)))
url = f'https://vcoo-dashboard.vercel.app/setup/{token}'
print('Fetching:', url)
try:
    r = requests.get(url, timeout=15)
    print('Status:', r.status_code)
    if r.status_code == 200:
        body = r.text
        if 'GitHub' in body:
            print('GitHub reference found in page')
        else:
            print('GitHub NOT found in page')
        # Also check for typical OAuth button text
        if 'Connect' in body or 'Authorize' in body:
            print('Possible OAuth button text found')
        # Save snippet
        with open('/tmp/onboarding.html', 'w') as f:
            f.write(body[:2000])
        print('Saved first 2000 chars to /tmp/onboarding.html')
    else:
        print('Failed to fetch page')
except Exception as e:
    print('Error fetching:', e)
