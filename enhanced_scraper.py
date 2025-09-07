#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re
import json

def try_api_endpoints(event_id="366607", quantity=2):
    """Try to find API endpoints that might return ticket data"""
    
    # Common API patterns for ticket sites
    api_patterns = [
        f"https://api.seatpick.com/events/{event_id}/tickets?quantity={quantity}",
        f"https://seatpick.com/api/events/{event_id}/tickets",
        f"https://seatpick.com/api/events/{event_id}/listings",
        f"https://seatpick.com/_next/data/*/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/{event_id}.json",
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json',
        'Referer': f'https://seatpick.com/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/{event_id}?quantity={quantity}'
    }
    
    for api_url in api_patterns:
        try:
            print(f"Trying API endpoint: {api_url}")
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"✓ Got JSON response from {api_url}")
                    print(f"Keys in response: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    
                    # Look for ticket data
                    if 'tickets' in str(data).lower() or 'listings' in str(data).lower():
                        return data
                        
                except json.JSONDecodeError:
                    print(f"Response not JSON: {response.text[:200]}...")
            else:
                print(f"Status {response.status_code}")
                
        except Exception as e:
            print(f"Error with {api_url}: {e}")
    
    return None

def extract_next_data(html_content):
    """Extract Next.js data from HTML"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for Next.js data in script tags
        scripts = soup.find_all('script')
        
        for script in scripts:
            if script.string and '__NEXT_DATA__' in script.string:
                # Extract JSON from Next.js script
                json_match = re.search(r'__NEXT_DATA__\s*=\s*({.*?})\s*(?:;|\n|$)', script.string, re.DOTALL)
                if json_match:
                    try:
                        next_data = json.loads(json_match.group(1))
                        print("Found __NEXT_DATA__")
                        return next_data
                    except json.JSONDecodeError as e:
                        print(f"Error parsing __NEXT_DATA__: {e}")
            
            elif script.string and 'self.__next_f.push' in script.string:
                # Extract data from Next.js chunks
                print("Found Next.js chunks in script")
                chunks = re.findall(r'self\.__next_f\.push\(\[.*?\]\)', script.string)
                for chunk in chunks[:3]:  # Check first few chunks
                    print(f"Chunk: {chunk[:200]}...")
        
        return None
        
    except Exception as e:
        print(f"Error extracting Next.js data: {e}")
        return None

def enhanced_scrape():
    """Enhanced scraping with multiple approaches"""
    url = "https://seatpick.com/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/366607?quantity=2"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    print("=== Enhanced Scraping Test ===")
    
    # Try API endpoints first
    print("\n1. Trying API endpoints...")
    api_data = try_api_endpoints()
    if api_data:
        print("Found API data!")
        return api_data
    
    # Fallback to HTML scraping
    print("\n2. Scraping HTML...")
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Try to extract Next.js data
        next_data = extract_next_data(response.text)
        if next_data:
            print("Extracted Next.js data structure")
            # Navigate the data structure to find tickets
            return analyze_next_data(next_data)
        
        # Fallback to basic HTML parsing
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for any structured data (JSON-LD, etc.)
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                structured_data = json.loads(script.string)
                print(f"Found structured data: {structured_data}")
            except:
                pass
        
        # Look for ticket information in meta tags or data attributes
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            if meta.get('property') and 'price' in meta.get('property', '').lower():
                print(f"Found price meta: {meta}")
        
        print("No structured ticket data found in HTML")
        return None
        
    except Exception as e:
        print(f"Error in enhanced scraping: {e}")
        return None

def analyze_next_data(data):
    """Analyze Next.js data structure for ticket information"""
    def search_for_tickets(obj, path=""):
        """Recursively search for ticket-like data"""
        tickets = []
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                
                # Look for ticket-related keys
                if any(term in key.lower() for term in ['ticket', 'listing', 'price', 'seat', 'section']):
                    print(f"Found potential ticket data at {new_path}: {str(value)[:100]}")
                    
                tickets.extend(search_for_tickets(value, new_path))
                
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_path = f"{path}[{i}]"
                tickets.extend(search_for_tickets(item, new_path))
                
        elif isinstance(obj, str) and ('$' in obj or 'price' in obj.lower()):
            print(f"Found price-like string at {path}: {obj}")
            
        return tickets
    
    return search_for_tickets(data)

if __name__ == "__main__":
    result = enhanced_scrape()
    if result:
        print(f"\nFinal result: {result}")
    else:
        print("\nNo ticket data found")