#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import re
from datetime import datetime
from playwright.async_api import async_playwright
import time

class VerifiedSeatPickScraper:
    def __init__(self):
        self.event_id = "366607"
        self.base_url = "https://seatpick.com"
        self.api_url = f"https://seatpick.com/api/proxy/4/events/{self.event_id}/listings"
        
        # Your desired sections (from the filter screenshot)
        self.desired_sections = [
            "Center",
            "Front Center", 
            "Front Left",
            "Front Right",
            "Left",
            "Reserved Seating",
            "Right"
        ]
        
        # Vendor verification configs
        self.vendor_configs = {
            "vividseats": {
                "name": "VividSeats",
                "price_selector": '[data-testid="listing-price"], .price, .listing-price, [class*="price"]',
                "verify": True
            },
            "vgg": {
                "name": "Viagogo",
                "price_selector": '.price, .listing-price, [data-testid*="price"]',
                "verify": True
            },
            "te": {
                "name": "Events365",
                "price_selector": '.price, .total-price',
                "verify": True
            },
            "tn": {
                "name": "TicketNetwork",
                "price_selector": '.price, .ticket-price',
                "verify": True
            }
        }
        
    async def fetch_listings(self):
        """Fetch listings from SeatPick API"""
        print(f"🔍 Fetching listings from SeatPick API...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': f'{self.base_url}/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/{self.event_id}'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.api_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Got {len(data.get('listings', []))} total listings")
                    return data
                else:
                    print(f"❌ API request failed: {response.status}")
                    return None
    
    def filter_listings(self, data, max_price=400):
        """Filter listings for desired sections and price range"""
        if not data or 'listings' not in data:
            return []
        
        filtered = []
        for listing in data['listings']:
            # Check if section is in desired list
            section = listing.get('section', '')
            if section not in self.desired_sections:
                continue
            
            # Check price range
            price = listing.get('price', 0)
            if price > max_price or price < 50:  # Skip suspiciously cheap tickets
                continue
            
            # Get vendor info
            seller_id = listing.get('seller', '')
            vendor_info = self.vendor_configs.get(seller_id, {})
            
            filtered.append({
                'id': listing.get('id'),
                'section': section,
                'row': listing.get('row', ''),
                'price': price,
                'quantity': listing.get('quantity', 1),
                'seller_id': seller_id,
                'seller_name': vendor_info.get('name', seller_id.upper()),
                'deeplink': listing.get('deepLink', ''),
                'notes': listing.get('notes', ''),
                'verified': False,
                'actual_price': None,
                'price_match': None
            })
        
        print(f"📊 Filtered to {len(filtered)} tickets in desired sections under ${max_price}")
        return filtered
    
    def categorize_section(self, section):
        """Categorize section as Left/Center/Right"""
        section_lower = section.lower()
        
        if 'center' in section_lower or 'centre' in section_lower:
            return "Center"
        elif 'left' in section_lower:
            return "Left"
        elif 'right' in section_lower:
            return "Right"
        elif section == "Reserved Seating":
            return "Reserved"
        else:
            return "Other"
    
    async def verify_prices(self, listings):
        """Verify prices by following checkout links"""
        print(f"🔍 Verifying prices for {len(listings)} tickets...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            
            for i, listing in enumerate(listings):
                if not listing['deeplink']:
                    print(f"  ⏭️  Skipping {listing['section']} - no checkout link")
                    continue
                
                print(f"  [{i+1}/{len(listings)}] Verifying {listing['section']} ${listing['price']} from {listing['seller_name']}...")
                
                try:
                    page = await context.new_page()
                    
                    # Navigate to checkout page
                    await page.goto(listing['deeplink'], wait_until='domcontentloaded', timeout=15000)
                    await page.wait_for_timeout(3000)  # Let page fully load
                    
                    # Try to find price on checkout page
                    vendor_config = self.vendor_configs.get(listing['seller_id'], {})
                    price_found = False
                    
                    # Extract all text containing dollar signs
                    page_text = await page.content()
                    price_matches = re.findall(r'\$(\d{1,4}(?:[,\.]\d{2})?)', page_text)
                    
                    if price_matches:
                        # Convert to integers and find closest to listed price
                        prices = []
                        for match in price_matches:
                            try:
                                # Remove commas and convert to int
                                price_int = int(re.sub(r'[,\.]', '', match.split('.')[0]))
                                if 50 <= price_int <= 5000:  # Reasonable price range
                                    prices.append(price_int)
                            except:
                                continue
                        
                        if prices:
                            # Find price closest to listed price
                            listed_price = listing['price']
                            closest_price = min(prices, key=lambda x: abs(x - listed_price))
                            
                            # Also look for prices that might be per-ticket when quantity > 1
                            if listing['quantity'] > 1:
                                total_prices = [p for p in prices if abs(p - listed_price * listing['quantity']) < 100]
                                if total_prices:
                                    closest_price = min(total_prices) // listing['quantity']
                            
                            listing['verified'] = True
                            listing['actual_price'] = closest_price
                            listing['price_match'] = abs(closest_price - listed_price) <= 10  # Within $10
                            
                            if listing['price_match']:
                                print(f"    ✅ Price verified: ${closest_price} (matches listed ${listed_price})")
                            else:
                                price_diff = closest_price - listed_price
                                print(f"    ⚠️  PRICE MISMATCH: Listed ${listed_price}, actual ${closest_price} (${price_diff:+d} difference)")
                            
                            price_found = True
                    
                    if not price_found:
                        print(f"    ❓ Could not extract price from {listing['seller_name']} checkout page")
                        listing['verified'] = False
                    
                    await page.close()
                    
                except Exception as e:
                    print(f"    ❌ Error verifying {listing['seller_name']}: {str(e)[:100]}")
                    listing['verified'] = False
                    try:
                        await page.close()
                    except:
                        pass
                
                # Rate limiting to avoid being blocked
                await asyncio.sleep(2)
            
            await browser.close()
        
        return listings
    
    def generate_report(self, listings):
        """Generate a summary report of findings"""
        print("\n" + "="*60)
        print("📊 VERIFICATION REPORT")
        print("="*60)
        
        # Group by location
        by_location = {}
        for listing in listings:
            location = self.categorize_section(listing['section'])
            if location not in by_location:
                by_location[location] = []
            by_location[location].append(listing)
        
        # Report by location
        for location in ["Left", "Center", "Right", "Reserved", "Other"]:
            if location not in by_location:
                continue
            
            location_listings = by_location[location]
            print(f"\n🎯 {location.upper()} SECTIONS ({len(location_listings)} tickets)")
            print("-" * 40)
            
            # Sort by price
            for listing in sorted(location_listings, key=lambda x: x['price']):
                section = listing['section']
                price = listing['price']
                seller = listing['seller_name']
                
                if listing['verified']:
                    if listing['price_match']:
                        status = "✅"
                        price_text = f"${price}"
                    else:
                        status = "⚠️"
                        actual = listing['actual_price']
                        diff = actual - price
                        price_text = f"${price} → ${actual} ({diff:+d})"
                else:
                    status = "❓"
                    price_text = f"${price}"
                
                print(f"  {status} {section:20s} {price_text:15s} via {seller}")
        
        # Summary statistics
        print("\n" + "="*60)
        print("📈 SUMMARY")
        print("-" * 40)
        
        total = len(listings)
        verified = len([l for l in listings if l['verified']])
        matched = len([l for l in listings if l['price_match']])
        mismatched = len([l for l in listings if l['verified'] and not l['price_match']])
        
        print(f"Total tickets found: {total}")
        print(f"Successfully verified: {verified}/{total} ({verified*100//total if total else 0}%)")
        print(f"Price matches: {matched}")
        print(f"PRICE MISMATCHES: {mismatched}")
        
        if mismatched > 0:
            print("\n⚠️  WARNING: Price mismatches found!")
            for listing in listings:
                if listing['verified'] and not listing['price_match']:
                    diff = listing['actual_price'] - listing['price']
                    print(f"  - {listing['section']} via {listing['seller_name']}: ${listing['price']} → ${listing['actual_price']} ({diff:+d})")
        
        return by_location

async def main():
    scraper = VerifiedSeatPickScraper()
    
    # Fetch listings from API
    data = await scraper.fetch_listings()
    if not data:
        print("Failed to fetch listings")
        return
    
    # Filter for desired sections and price range
    filtered = scraper.filter_listings(data, max_price=400)
    
    if not filtered:
        print("No tickets found matching criteria")
        return
    
    # Verify prices by following checkout links
    verified = await scraper.verify_prices(filtered)
    
    # Generate report
    report = scraper.generate_report(verified)
    
    # Return data for use in monitor
    return verified

if __name__ == "__main__":
    asyncio.run(main())