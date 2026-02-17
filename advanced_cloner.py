#!/usr/bin/env python3
"""
Advanced Website Cloner with JavaScript Rendering
For when basic HTTP requests just won't cut it
"""

import os
import sys
import time
import requests
import argparse
from urllib.parse import urlparse, urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import concurrent.futures
import mimetypes

class AdvancedWebsiteCloner:
    def __init__(self, target_url, output_dir, use_selenium=True, max_threads=10):
        self.target_url = target_url
        self.output_dir = output_dir
        self.use_selenium = use_selenium
        self.max_threads = max_threads
        self.downloaded_urls = set()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if use_selenium:
            self.setup_selenium()
    
    def setup_selenium(self):
        """Setup headless Chrome for JavaScript rendering"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920x1080')
        
        # For Termux, you'll need to install chromedriver separately
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except:
            print("[!] ChromeDriver not found. Falling back to basic HTTP.")
            self.use_selenium = False
    
    def get_page_content(self, url):
        """Get page content either via Selenium or requests"""
        if self.use_selenium and self.driver:
            try:
                self.driver.get(url)
                time.sleep(3)  # Wait for JavaScript to render
                return self.driver.page_source
            except Exception as e:
                print(f"[-] Selenium failed for {url}: {e}")
                return None
        else:
            try:
                response = self.session.get(url, timeout=10)
                return response.text
            except Exception as e:
                print(f"[-] HTTP failed for {url}: {e}")
                return None
    
    def extract_all_resources(self, html, base_url):
        """Extract all possible resources from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        resources = []
        
        # CSS files
        for link in soup.find_all('link', rel='stylesheet'):
            href = link.get('href')
            if href:
                resources.append(urljoin(base_url, href))
        
        # JavaScript files
        for script in soup.find_all('script', src=True):
            src = script.get('src')
            if src:
                resources.append(urljoin(base_url, src))
        
        # Images
        for img in soup.find_all('img', src=True):
            src = img.get('src')
            if src:
                resources.append(urljoin(base_url, src))
        
        # Fonts
        for link in soup.find_all('link', as_='font'):
            href = link.get('href')
            if href:
                resources.append(urljoin(base_url, href))
        
        # Video/Audio
        for source in soup.find_all(['source', 'track']):
            src = source.get('src')
            if src:
                resources.append(urljoin(base_url, src))
        
        # Iframe sources (for your preview page)
        for iframe in soup.find_all('iframe', src=True):
            src = iframe.get('src')
            if src:
                resources.append(urljoin(base_url, src))
        
        return resources
    
    def download_resource(self, url):
        """Download a single resource"""
        if url in self.downloaded_urls:
            return
        
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                url = urljoin(self.target_url, url)
                parsed = urlparse(url)
            
            # Create directory structure
            path_parts = parsed.path.strip('/').split('/')
            if path_parts and path_parts[-1]:
                filename = path_parts[-1]
                dir_parts = path_parts[:-1]
            else:
                filename = 'index.html'
                dir_parts = path_parts
            
            save_dir = os.path.join(self.output_dir, parsed.netloc, *dir_parts)
            os.makedirs(save_dir, exist_ok=True)
            
            filepath = os.path.join(save_dir, filename)
            
            # Download file
            response = self.session.get(url, stream=True, timeout=10)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"[+] Downloaded: {url}")
            self.downloaded_urls.add(url)
            
            # If it's HTML, recursively download its resources
            content_type = response.headers.get('content-type', '')
            if 'text/html' in content_type:
                time.sleep(1)  # Be nice
                html_content = self.get_page_content(url)
                if html_content:
                    resources = self.extract_all_resources(html_content, url)
                    for resource in resources:
                        self.download_resource(resource)
            
        except Exception as e:
            print(f"[-] Failed: {url} - {str(e)}")
    
    def clone_website(self):
        """Main cloning function"""
        print(f"[*] Advanced cloning started: {self.target_url}")
        print(f"[*] Using Selenium: {self.use_selenium}")
        print("-" * 50)
        
        # Get main page content
        html_content = self.get_page_content(self.target_url)
        if not html_content:
            print("[!] Failed to get main page content")
            return
        
        # Save main HTML
        parsed = urlparse(self.target_url)
        main_dir = os.path.join(self.output_dir, parsed.netloc)
        os.makedirs(main_dir, exist_ok=True)
        
        main_file = os.path.join(main_dir, 'index.html')
        with open(main_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[+] Saved main page: {main_file}")
        
        # Extract and download all resources
        resources = self.extract_all_resources(html_content, self.target_url)
        print(f"[*] Found {len(resources)} resources to download")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = [executor.submit(self.download_resource, url) for url in resources]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"[-] Thread error: {e}")
        
        if self.use_selenium and hasattr(self, 'driver'):
            self.driver.quit()
        
        print("-" * 50)
        print(f"[✓] Clone complete! Files saved in: {self.output_dir}")

def main():
    parser = argparse.ArgumentParser(description='Advanced Website Cloner with JavaScript Support')
    parser.add_argument('url', help='Target website URL')
    parser.add_argument('-o', '--output', default='cloned_site', help='Output directory')
    parser.add_argument('--no-selenium', action='store_true', help='Disable Selenium (no JavaScript)')
    parser.add_argument('-t', '--threads', type=int, default=5, help='Max threads')
    
    args = parser.parse_args()
    
    cloner = AdvancedWebsiteCloner(
        args.url, 
        args.output, 
        use_selenium=not args.no_selenium,
        max_threads=args.threads
    )
    
    cloner.clone_website()

if __name__ == "__main__":
    main()
