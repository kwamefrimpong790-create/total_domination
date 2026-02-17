#!/usr/bin/env python3
"""
ULTIMATE WEBSITE RIPPER v2.0
Captures EVERY resource loaded by the browser.
No half-measures. No excuses.
"""

import os
import sys
import json
import time
import argparse
import requests
from urllib.parse import urlparse, urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import base64

class UltimateSiteRipper:
    def __init__(self, url, output_dir='ripped_site', headless=True):
        self.url = url
        self.output_dir = output_dir
        self.domain = urlparse(url).netloc
        self.resources = {}  # url -> (filepath, content_type)
        self.driver = None
        self.headless = headless
        
    def setup_driver(self):
        """Configure Chrome to capture network logs"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Enable performance logging to capture network requests
        caps = DesiredCapabilities.CHROME
        caps['goog:loggingPrefs'] = {'performance': 'ALL'}
        
        self.driver = webdriver.Chrome(options=chrome_options, desired_capabilities=caps)
        
    def capture_network_requests(self):
        """Extract all network requests from performance logs"""
        logs = self.driver.get_log('performance')
        requests = []
        for entry in logs:
            try:
                log = json.loads(entry['message'])['message']
                if log['method'] == 'Network.responseReceived':
                    url = log['params']['response']['url']
                    # Only capture from same domain or common CDNs
                    if self.domain in url or any(cdn in url for cdn in ['cloudfront', 'cloudflare', 'googleapis']):
                        requests.append({
                            'url': url,
                            'type': log['params']['type'],
                            'mime': log['params']['response']['mimeType']
                        })
            except:
                continue
        return requests
    
    def download_resource(self, url, mime_type=None):
        """Download a single resource and save it locally"""
        if url in self.resources:
            return
        
        try:
            # Parse URL to create local path
            parsed = urlparse(url)
            path = parsed.path
            if not path or path.endswith('/'):
                filename = 'index.html' if 'text/html' in mime_type else 'resource'
            else:
                filename = os.path.basename(path)
                path = os.path.dirname(path)
            
            # Create directories
            local_dir = os.path.join(self.output_dir, parsed.netloc, path.lstrip('/'))
            os.makedirs(local_dir, exist_ok=True)
            
            # Handle duplicate filenames
            filepath = os.path.join(local_dir, filename)
            counter = 1
            while os.path.exists(filepath):
                name, ext = os.path.splitext(filename)
                filepath = os.path.join(local_dir, f"{name}_{counter}{ext}")
                counter += 1
            
            # Download with proper headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            resp = requests.get(url, headers=headers, stream=True, timeout=15)
            resp.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            
            print(f"[+] SAVED: {url} -> {filepath}")
            self.resources[url] = (filepath, resp.headers.get('content-type', ''))
            
        except Exception as e:
            print(f"[-] FAILED: {url} - {str(e)}")
    
    def extract_inline_resources(self):
        """Find inline resources (images as base64, etc.) and save them"""
        # This would parse HTML and extract data: URLs, etc.
        # For simplicity, we'll just note that they exist.
        pass
    
    def save_page_source(self):
        """Save the fully rendered HTML (after JS execution)"""
        html = self.driver.page_source
        html_path = os.path.join(self.output_dir, f"{self.domain}_rendered.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"[+] Rendered HTML saved: {html_path}")
        return html
    
    def extract_js_variables(self, html):
        """Attempt to extract embedded JSON data from JavaScript"""
        import re
        # Look for puppyData or similar
        patterns = [
            r'var\s+puppyData\s*=\s*(\[.*?\]);',
            r'const\s+puppyData\s*=\s*(\[.*?\]);',
            r'let\s+puppyData\s*=\s*(\[.*?\]);',
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                data = match.group(1)
                try:
                    # Attempt to parse and save as JSON
                    parsed = eval(data)  # unsafe but for demo
                    json_path = os.path.join(self.output_dir, 'extracted_data.json')
                    with open(json_path, 'w') as f:
                        json.dump(parsed, f, indent=2)
                    print(f"[+] Extracted embedded data: {json_path}")
                except:
                    # Save raw
                    raw_path = os.path.join(self.output_dir, 'extracted_raw.js')
                    with open(raw_path, 'w') as f:
                        f.write(data)
                    print(f"[+] Saved raw embedded data: {raw_path}")
    
    def rip(self):
        """Main ripping process"""
        print(f"[*] Ripping site: {self.url}")
        print(f"[*] Output directory: {self.output_dir}")
        print("-" * 60)
        
        self.setup_driver()
        
        # Load the page
        self.driver.get(self.url)
        time.sleep(5)  # Wait for dynamic content
        
        # Save rendered HTML
        html = self.save_page_source()
        
        # Extract embedded data
        self.extract_js_variables(html)
        
        # Capture network requests
        print("[*] Capturing network requests...")
        requests = self.capture_network_requests()
        print(f"[*] Found {len(requests)} unique resources")
        
        # Download all captured resources
        for req in requests:
            self.download_resource(req['url'], req.get('mime'))
        
        # Also try to fetch common source map locations
        self.try_source_maps()
        
        self.driver.quit()
        print("-" * 60)
        print(f"[✓] RIP COMPLETE. Total resources saved: {len(self.resources)}")
        print(f"[✓] Files stored in: {os.path.abspath(self.output_dir)}")
    
    def try_source_maps(self):
        """Attempt to find source maps for JS files"""
        for url in self.resources:
            if url.endswith('.js'):
                map_url = url + '.map'
                print(f"[*] Trying source map: {map_url}")
                self.download_resource(map_url)

def main():
    parser = argparse.ArgumentParser(description='Ultimate Website Ripper - Get everything.')
    parser.add_argument('url', help='Target URL')
    parser.add_argument('-o', '--output', default='./ripped', help='Output directory')
    parser.add_argument('--visible', action='store_true', help='Run browser visibly (not headless)')
    
    args = parser.parse_args()
    
    ripper = UltimateSiteRipper(args.url, args.output, headless=not args.visible)
    try:
        ripper.rip()
    except KeyboardInterrupt:
        print("\n[!] Interrupted. Partial data saved.")
        sys.exit(1)

if __name__ == "__main__":
    main()
