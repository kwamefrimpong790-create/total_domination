#!/usr/bin/env python3
"""
Website Cloner Tool - For "archival purposes" as The Translator would say
Because why should anything on the internet remain private?
"""

import os
import sys
import requests
import argparse
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import mimetypes
import re

class WebsiteCloner:
    def __init__(self, target_url, output_dir, max_threads=10, delay=0):
        self.target_url = target_url if target_url.startswith(('http://', 'https://')) else 'http://' + target_url
        self.output_dir = output_dir
        self.max_threads = max_threads
        self.delay = delay
        self.visited_urls = set()
        self.domain = urlparse(self.target_url).netloc
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
    def create_directory_structure(self, url):
        """Create directory structure based on URL path"""
        parsed = urlparse(url)
        path = parsed.path
        
        if path.endswith('/') or not path:
            dir_path = os.path.join(self.output_dir, parsed.netloc, path.lstrip('/'))
        else:
            # It's a file, create directory for its parent
            dir_path = os.path.join(self.output_dir, parsed.netloc, os.path.dirname(path).lstrip('/'))
        
        os.makedirs(dir_path, exist_ok=True)
        return dir_path
    
    def download_file(self, url):
        """Download any file from URL"""
        if url in self.visited_urls:
            return None
        
        try:
            # Normalize URL
            if not url.startswith(('http://', 'https://')):
                url = urljoin(self.target_url, url)
            
            # Only download from same domain (can be modified to crawl external)
            if self.domain not in urlparse(url).netloc:
                return None
            
            self.visited_urls.add(url)
            
            # Add delay to avoid detection
            if self.delay > 0:
                time.sleep(self.delay)
            
            response = self.session.get(url, timeout=10, stream=True)
            response.raise_for_status()
            
            # Determine filename
            parsed = urlparse(url)
            path = parsed.path
            
            if not path or path.endswith('/'):
                filename = 'index.html'
            else:
                filename = os.path.basename(path)
                if not filename:
                    filename = 'index.html'
            
            # Create directory and save file
            dir_path = self.create_directory_structure(url)
            filepath = os.path.join(dir_path, filename)
            
            # Handle duplicate filenames
            counter = 1
            while os.path.exists(filepath):
                name, ext = os.path.splitext(filename)
                filepath = os.path.join(dir_path, f"{name}_{counter}{ext}")
                counter += 1
            
            # Save file
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"[+] Downloaded: {url} -> {filepath}")
            
            # If it's HTML, parse and download resources
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                self.parse_html_and_download_resources(response.text, url)
            
            return filepath
            
        except Exception as e:
            print(f"[-] Failed to download {url}: {str(e)}")
            return None
    
    def parse_html_and_download_resources(self, html_content, base_url):
        """Parse HTML and download all linked resources"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all resources
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
        for link in soup.find_all('link', rel='preload', as_='font'):
            href = link.get('href')
            if href:
                resources.append(urljoin(base_url, href))
        
        # Video/Audio
        for media in soup.find_all(['source', 'track']):
            src = media.get('src')
            if src:
                resources.append(urljoin(base_url, src))
        
        # Download resources in parallel
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            futures = [executor.submit(self.download_file, resource) for resource in resources if resource not in self.visited_urls]
            for future in as_completed(futures):
                try:
                    future.result()
                except:
                    pass
    
    def crawl_website(self):
        """Main crawling function"""
        print(f"[*] Starting website clone: {self.target_url}")
        print(f"[*] Output directory: {self.output_dir}")
        print(f"[*] Max threads: {self.max_threads}")
        print("-" * 50)
        
        # Start with target URL
        self.download_file(self.target_url)
        
        # Additional crawl for sitemap
        sitemap_url = urljoin(self.target_url, '/sitemap.xml')
        try:
            response = self.session.get(sitemap_url, timeout=5)
            if response.status_code == 200:
                print("[*] Found sitemap, parsing...")
                soup = BeautifulSoup(response.text, 'xml')
                for loc in soup.find_all('loc'):
                    url = loc.text
                    if url not in self.visited_urls:
                        self.download_file(url)
        except:
            pass
        
        print("-" * 50)
        print(f"[✓] Clone complete! Total files downloaded: {len(self.visited_urls)}")
        print(f"[✓] Files saved in: {self.output_dir}")

def main():
    parser = argparse.ArgumentParser(description='Website Cloner Tool - Because copying is caring')
    parser.add_argument('url', help='Target website URL')
    parser.add_argument('-o', '--output', default='cloned_site', help='Output directory (default: cloned_site)')
    parser.add_argument('-t', '--threads', type=int, default=10, help='Max threads for concurrent downloads (default: 10)')
    parser.add_argument('-d', '--delay', type=float, default=0, help='Delay between requests in seconds (default: 0)')
    parser.add_argument('--include-external', action='store_true', help='Include external resources (default: False)')
    
    args = parser.parse_args()
    
    print("""
    ╔══════════════════════════════════════╗
    ║     Website Cloner Tool v1.0         ║
    ║    "For educational purposes only"   ║
    ╚══════════════════════════════════════╝
    """)
    
    cloner = WebsiteCloner(args.url, args.output, args.threads, args.delay)
    
    try:
        cloner.crawl_website()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"[-] Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
