#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re

url = "https://seatpick.com/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/366607?quantity=2"

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

print("Testing ticket scraping...")
try:
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    print(f"Successfully fetched page, status: {response.status_code}")
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Let's analyze the HTML structure
    print("\n=== Analyzing HTML structure ===")
    
    # Look for any elements containing price patterns
    price_elements = soup.find_all(text=re.compile(r'\$\d+'))
    print(f"Found {len(price_elements)} elements with price patterns:")
    for i, elem in enumerate(price_elements[:10]):  # Show first 10
        parent = elem.parent if elem.parent else "No parent"
        print(f"  {i+1}. '{elem.strip()}' (parent: {parent.name if hasattr(parent, 'name') else 'text'})")
    
    # Look for common ticket listing patterns
    potential_sections = []
    
    # Try various selectors that might contain ticket info
    selectors_to_try = [
        '.listing',
        '.ticket-listing', 
        '.price',
        '[class*="listing"]',
        '[class*="ticket"]',
        '[class*="price"]',
        'div:contains("$")'
    ]
    
    for selector in selectors_to_try:
        try:
            elements = soup.select(selector)
            if elements:
                print(f"\nFound {len(elements)} elements with selector '{selector}':")
                for i, elem in enumerate(elements[:3]):  # Show first 3
                    print(f"  {i+1}. {elem.get_text(strip=True)[:100]}...")
                    if '$' in elem.get_text():
                        potential_sections.append({
                            'selector': selector,
                            'text': elem.get_text(strip=True),
                            'element': elem
                        })
        except Exception as e:
            print(f"Error with selector '{selector}': {e}")
    
    # Try to find sections/rows information
    print(f"\n=== Potential ticket sections found: {len(potential_sections)} ===")
    for i, section in enumerate(potential_sections[:5]):  # Show first 5
        text = section['text']
        price_match = re.search(r'\$(\d+)', text)
        price = int(price_match.group(1)) if price_match else None
        
        print(f"{i+1}. Price: ${price} | Text: {text[:150]}...")
        print(f"   Selector: {section['selector']}")
        
        # Check if it looks like GA
        is_ga = any(term in text.lower() for term in ['general admission', 'floor ga', 'section ga', 'ga'])
        print(f"   Is GA: {is_ga}")
        print()
    
    print("\n=== Raw HTML sample (first 2000 chars) ===")
    print(response.text[:2000])
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()