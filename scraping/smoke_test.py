#!/usr/bin/env python3
"""Quick smoke test for the Scraping API"""
import os
import sys
import json
import requests
from pathlib import Path

# Load environment from .env file
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

# Configuration
API_URL = os.getenv('SCRAPING_API_URL', 'https://ml.cloudcix.com/scraping/')
API_KEY = os.getenv('SCRAPING_API_KEY')
DOCUMENT_TYPE = os.getenv('SCRAPING_DOCUMENT_TYPE', 'html')
URLS_FILE = os.getenv('SCRAPING_URLS_FILE', '1000')

if not API_KEY:
    print("❌ Error: SCRAPING_API_KEY not set in .env file")
    sys.exit(1)

# Load URLs
urls_path = Path(__file__).parent / 'scraping_urls' / f'{URLS_FILE}.json'
if not urls_path.exists():
    print(f"❌ Error: URLs file not found: {urls_path}")
    sys.exit(1)

with open(urls_path) as f:
    urls = json.load(f)

print(f"🔥 Scraping API Smoke Test")
print(f"━" * 80)
print(f"API URL: {API_URL}")
print(f"Document Type: {DOCUMENT_TYPE}")
print(f"URLs: {len(urls)} from {URLS_FILE}.json")
print(f"━" * 80)
print()

# Prepare request
payload = {
    'list': urls,
    'document_type': DOCUMENT_TYPE,
    'api_key': API_KEY,
}

print(f"📤 Sending batch request with {len(urls)} URLs...")
print()

try:
    response = requests.post(
        API_URL,
        json=payload,
        timeout=3000,
    )
    
    print(f"📥 Response Status: {response.status_code}")
    print(f"📦 Response Size: {len(response.content)} bytes ({len(response.content) / 1024:.2f} KB)")
    print(f"━" * 80)
    print()
    
    if response.status_code == 200:
        print("✅ Success! Full response:")
        print(f"━" * 80)
        
        # Try to pretty-print JSON and count URLs
        try:
            data = response.json()
            print(json.dumps(data, indent=2))
            print()
            print(f"━" * 80)
            
            # Count URLs in response
            if isinstance(data, dict):
                # Try common response structures
                if 'results' in data:
                    count = len(data['results']) if isinstance(data['results'], list) else 1
                    print(f"✓ URLs processed: {count}")
                elif 'data' in data:
                    count = len(data['data']) if isinstance(data['data'], list) else 1
                    print(f"✓ URLs processed: {count}")
                elif 'items' in data:
                    count = len(data['items']) if isinstance(data['items'], list) else 1
                    print(f"✓ URLs processed: {count}")
                else:
                    # Count all list-like values in response
                    for key, value in data.items():
                        if isinstance(value, list):
                            print(f"✓ {key}: {len(value)} items")
            elif isinstance(data, list):
                print(f"✓ URLs processed: {len(data)}")
        except json.JSONDecodeError:
            print(response.text)
    else:
        print(f"❌ Failed with status {response.status_code}")
        print(f"Response: {response.text}")
        sys.exit(1)
        
except requests.exceptions.Timeout:
    print("❌ Request timed out after 300 seconds")
    sys.exit(1)
except requests.exceptions.RequestException as e:
    print(f"❌ Request failed: {e}")
    sys.exit(1)
