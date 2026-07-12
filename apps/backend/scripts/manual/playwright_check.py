import os
os.environ['POSTGRES_URL'] = 'sqlite:///./test.db'
os.environ.setdefault('MASTER_KEY', 'dev-key-only-for-local')
os.environ['SECRET_KEY'] = 'testsecret'
os.environ['FRONTEND_URL'] = 'https://vcoo-onboarding.vercel.app'
os.environ['DASHBOARD_URL'] = 'https://vcoo-dashboard.vercel.app'
os.environ['CONTROL_PLANE'] = 'https://vcoo-onboarding.vercel.app'
import sys
sys.path.insert(0, '.')
from main import application
from fastapi.testclient import TestClient
client = TestClient(application)
resp = client.post('/vcoo', json={'name':'test-v2o', modules=['core'] if False else ['core'])
# Actually we need correct dict
# Let's just redo
import json
resp = client.post('/vcoo', json={"name":"test-vcoo","modules":["core"]})
print('Create status:', resp.status_code)
if resp.status_code != 200:
    print('Error:', resp.text); sys.exit(1)
data = resp.json()
token = data.get('token')
if not token:
    resp2 = client.get(f'/vcoo/{data["id"]}/provision-token')
    token = resp2.json().get('token')
print('Token length:', len(token))
url = f'https://vcoo-dashboard.vercel.app/setup/{token}'
print('URL:', url)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, timeout=60000)
    # Wait for network idle
    page.wait_for_load_state('networkidle')
    # Try to find a button with text containing Connect or GitHub
    btn = page.locator('button:has-text("Connect")')
    if btn.count() > 0:
        print('Found Connect button')
        # click? not needed
    else:
        # look for a link with href containing github
        link = page.locator('a[href*="github"]')
        if link.count() > 0:
            print('Found GitHub link')
        else:
            # look for any button
            buttons = page.locator('button')
            if buttons.count() > 0:
                print('Found {} buttons, checking text...'.format(buttons.count()))
                # get first few button texts
                for i in range(min(buttons.count(), 5)):
                    txt = buttons.nth(i).inner_text()
                    print('Button {}: "{}"'.format(i, txt.strip()))
            else:
                print('No buttons found')
    # Screenshot
    page.screenshot(path='/tmp/onboarding_playwright.png')
    print('Screenshot saved')
    browser.close()
