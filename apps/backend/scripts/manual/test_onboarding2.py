import os
os.environ['POSTGRES_URL'] = 'sqlite:///./test.db'
os.environ.setdefault('MASTER_KEY', 'dev-key-only-for-local')
# Ensure other vars if needed
os.environ['SECRET_KEY'] = 'testsecret'
os.environ['FRONTEND_URL'] = 'https://vcoo-onboarding.vercel.app'
os.environ['DASHBOARD_URL'] = 'https://vcoo-dashboard.vercel.app'
os.environ['CONTROL_PLANE'] = 'https://vcoo-onboarding.vercel.app'

import sys
sys.path.insert(0, '.')

from fastapi.testclient import TestClient
from main import application

client = TestClient(application)
# Create VCOO
resp = client.post('/vcoo', json={'name':'test-vcoo','modules':['core']})
print('Create VCOO status:', resp.status_code)
if resp.status_code != 20:

<tool_call>
<function=terminal>
<parameter=command:
    print('Response:', resp.text)
    sys.exit(1)
data = resp.json()
print('VCOO ID:', data['id'])
token = data.get('token')
if not token:
    # maybe token is in another endpoint
    resp2 = client.get(f"/vcoo/{data['id']}/provision-token")
    print('Get token status:', resp2.status_code)
    if resp2.status_code == 200:
        token = resp2.json().get('token')
    else:
        print('Failed to get token:', resp2.text)
        sys.exit(1)
print('Token:', token[:20] + '...')
# Build onboarding URL
onboarding_url = f"https://vcoo-dashboard.vercel.app/setup/{token}"
print('Navigating to:', onboarding_url)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(onboarding_url, timeout=60000)
    # Wait for page to load
    page.wait_for_timeout(5000)
    # Screenshot
    page.screenshot(path='/tmp/onboarding.png')
    print('Screenshot saved to /tmp/onboarding.png')
    # Check for GitHub
    content = page.content()
    if 'GitHub' in content:
        print('Found GitHub reference in page')
    else:
        print('GitHub not found in page')
    # Look for button with Connect or Authorize
    buttons = page.locator('button:has-text(\"Connect\")')
    if buttons.count() > 0:
        print('Found Connect button')
    else:
        links = page.locator('a:has-text(\"GitHub\")')
        if links.count() > 0:
            print('Found GitHub link')
        else:
            print('No obvious GitHub button/link')
    browser.close()
