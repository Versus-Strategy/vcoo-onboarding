import os
os.environ['POSTGRES_URL'] = 'sqlite:///./test.db'
os.environ['MASTER_KEY'] = 'vcoo-test-master-key-supersecret-2026'
os.environ['SECRET_KEY'] = 'testsecret'
os.environ['FRONTEND_URL'] = 'https://vcoo-onboarding.vercel.app'
os.environ['DASHBOARD_URL'] = 'https://vcoo-dashboard.vercel.app'
os.environ['CONTROL_PLANE'] = 'https://vcoo-onboarding.vercel.app'
import sys
sys.path.insert(0, '.')
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
# Create VCOO
resp = client.post('/vcoo', json={"name":"test-vcoo","modules":["core"]})
print('Create VCOO status:', resp.status_code)
if resp.status_code != 200:
    print('Response:', resp.text)
    sys.exit(1)
data = resp.json()
print('VCOO ID:', data['id'])
token = data.get('token')
if not token:
    resp2 = client.get(f'/vcoo/{data["id"]}/provision-token')
    print('Get token status:', resp2.status_code)
    if resp2.status_code != 200:
        print('Failed to get token:', resp2.text)
        sys.exit(1)
    token = resp2.json().get('token')
print('Token (first 20 chars):', token[:20] + '...')
url = f'https://vcoo-dashboard.vercel.app/setup/{token}'
print('Onboarding URL:', url)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, timeout=60000)
    page.wait_for_load_state('networkidle')
    # Look for a button with text containing Connect or GitHub
    btn = page.locator('button:has-text("Connect")')
    if btn.count() > 0:
        print('Found Connect button')
    else:
        # Look for any button and print first few texts
        buttons = page.locator('button')
        cnt = buttons.count()
        print(f'Found {cnt} buttons')
        for i in range(min(cnt, 5)):
            txt = buttons.nth(i).inner_text().strip()
            if txt:
                print(f'  Button {i}: "{txt}"')
        # Look for links with github in href
        links = page.locator('a[href*="github"]')
        if links.count() > 0:
            print('Found GitHub link')
        else:
            print('No GitHub link found')
    # Screenshot
    page.screenshot(path='/tmp/onboarding_final.png')
    print('Screenshot saved to /tmp/onboarding_final.png')
    browser.close()
