#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import re
from datetime import datetime
from playwright.async_api import async_playwright
import time

class FinalPriceMonitor:
    """Monitor that ONLY reports final prices with all fees included"""
    
    def __init__(self):
        self.event_id = "366607"
        self.base_url = "https://seatpick.com"
        self.api_url = f"https://seatpick.com/api/proxy/4/events/{self.event_id}/listings"
        
        # Your desired sections (NO GA)
        self.desired_sections = [
            "Center",
            "Front Center", 
            "Front Left",
            "Front Right",
            "Left",
            "Reserved Seating",
            "Right"
        ]
        
    async def fetch_and_verify(self, max_price=400):
        """Fetch listings and verify FINAL prices with fees"""
        
        print("="*60)
        print("🎫 ATMOSPHERE MORRISON - RED ROCKS")
        print("📅 September 19, 2025")
        print("="*60)
        
        # Fetch from SeatPick API
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': f'{self.base_url}/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/{self.event_id}'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.api_url, headers=headers) as response:
                if response.status != 200:
                    print("❌ Failed to fetch listings")
                    return []
                    
                data = await response.json()
        
        # Filter for desired sections
        filtered = []
        for listing in data.get('listings', []):
            if listing.get('section') not in self.desired_sections:
                continue
            if listing.get('price', 0) > max_price:
                continue
                
            filtered.append(listing)
        
        print(f"📊 Found {len(filtered)} tickets in premium sections under ${max_price}")
        print("-"*60)
        
        # Verify actual prices
        verified_listings = await self.verify_final_prices(filtered)
        
        return verified_listings
    
    async def verify_final_prices(self, listings):
        """Verify FINAL checkout prices including all fees"""
        
        if not listings:
            return []
        
        print("\n🔍 VERIFYING FINAL PRICES (with all fees)...")
        print("-"*60)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            
            verified = []
            
            for listing in listings[:10]:  # Limit to 10 to avoid rate limiting
                section = listing.get('section', '')
                row = listing.get('row', '')
                seatpick_price = listing.get('price', 0)
                seller = listing.get('seller', '')
                deeplink = listing.get('deepLink', '')
                
                if not deeplink:
                    continue
                
                row_info = f"Row {row}" if row else ""
                print(f"\n📍 {section} {row_info}")
                print(f"   SeatPick shows: ${seatpick_price}")
                print(f"   Seller: {seller}")
                
                try:
                    page = await context.new_page()
                    await page.goto(deeplink, wait_until='domcontentloaded', timeout=20000)
                    await page.wait_for_timeout(5000)
                    
                    # Extract FINAL price with fees
                    final_price = await self.extract_final_price(page, seller)
                    
                    if final_price:
                        price_diff = final_price - seatpick_price
                        pct_diff = (price_diff / seatpick_price * 100) if seatpick_price > 0 else 0
                        
                        if abs(price_diff) <= 10:
                            status = "✅"
                            status_text = "ACCURATE"
                        else:
                            status = "⚠️"
                            status_text = f"MISLEADING (+${price_diff:.0f} / +{pct_diff:.0f}%)"
                        
                        print(f"   Actual price: ${final_price:.2f} {status} {status_text}")
                        
                        verified.append({
                            'section': section,
                            'row': row,
                            'seatpick_price': seatpick_price,
                            'final_price': final_price,
                            'price_diff': price_diff,
                            'pct_diff': pct_diff,
                            'seller': seller,
                            'deeplink': deeplink,
                            'accurate': abs(price_diff) <= 10
                        })
                    else:
                        print(f"   ❓ Could not extract final price")
                    
                    await page.close()
                    
                except Exception as e:
                    print(f"   ❌ Error: {str(e)[:50]}")
                    try:
                        await page.close()
                    except:
                        pass
                
                await asyncio.sleep(2)  # Rate limiting
            
            await browser.close()
        
        return verified
    
    async def extract_final_price(self, page, seller):
        """Extract the FINAL price including all fees from checkout page"""
        
        try:
            content = await page.content()
            
            # VividSeats specific extraction
            if 'vivid' in seller.lower():
                # Look for "Estimated fees included" price
                match = re.search(r'\$(\d+(?:\.\d{2})?)\s*(?:ea|each)?.*?(?:Estimated fees included|est)', content, re.IGNORECASE)
                if match:
                    return float(match.group(1))
                
                # Look for total price patterns
                matches = re.findall(r'\$(\d{3,4}(?:\.\d{2})?)', content)
                if matches:
                    prices = [float(m) for m in matches]
                    # Return highest reasonable price (likely the total with fees)
                    valid_prices = [p for p in prices if 200 <= p <= 1000]
                    if valid_prices:
                        return max(valid_prices)
            
            # Viagogo specific extraction
            elif 'vgg' in seller or 'viagogo' in seller.lower():
                # Look for total price patterns
                matches = re.findall(r'(?:Total|total).*?\$(\d+(?:\.\d{2})?)', content)
                if matches:
                    return float(matches[0])
                    
                # Fallback to highest price
                matches = re.findall(r'\$(\d{3,4}(?:\.\d{2})?)', content)
                if matches:
                    prices = [float(m) for m in matches]
                    valid_prices = [p for p in prices if 200 <= p <= 1000]
                    if valid_prices:
                        return max(valid_prices)
            
            # Generic extraction for other sellers
            else:
                # Look for total/final price keywords
                patterns = [
                    r'(?:Total|Final|Checkout).*?\$(\d+(?:\.\d{2})?)',
                    r'\$(\d+(?:\.\d{2})?)\s*(?:total|Total)',
                    r'(?:fees included|with fees).*?\$(\d+(?:\.\d{2})?)'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        return float(matches[0])
                
                # Fallback: find highest reasonable price
                matches = re.findall(r'\$(\d{3,4}(?:\.\d{2})?)', content)
                if matches:
                    prices = [float(m) for m in matches]
                    valid_prices = [p for p in prices if 200 <= p <= 1000]
                    if valid_prices:
                        return max(valid_prices)
            
        except Exception as e:
            print(f"      Error extracting price: {str(e)[:50]}")
        
        return None
    
    def generate_report(self, verified_listings):
        """Generate final report with accurate pricing"""
        
        if not verified_listings:
            print("\n❌ No verified listings found")
            return
        
        print("\n" + "="*60)
        print("📊 FINAL PRICE REPORT (All Fees Included)")
        print("="*60)
        
        # Group by accuracy
        accurate = [l for l in verified_listings if l['accurate']]
        misleading = [l for l in verified_listings if not l['accurate']]
        
        if accurate:
            print("\n✅ ACCURATELY PRICED TICKETS:")
            print("-"*40)
            for listing in sorted(accurate, key=lambda x: x['final_price']):
                section = listing['section']
                row = f"Row {listing['row']}" if listing['row'] else ""
                final = listing['final_price']
                seller = listing['seller']
                print(f"  {section:20s} {row:10s} ${final:6.2f} via {seller}")
        
        if misleading:
            print("\n⚠️  MISLEADING PRICES (Actual price is higher):")
            print("-"*40)
            for listing in sorted(misleading, key=lambda x: x['price_diff'], reverse=True):
                section = listing['section']
                row = f"Row {listing['row']}" if listing['row'] else ""
                shown = listing['seatpick_price']
                final = listing['final_price']
                diff = listing['price_diff']
                pct = listing['pct_diff']
                seller = listing['seller']
                print(f"  {section:20s} {row:10s}")
                print(f"    SeatPick shows: ${shown}")
                print(f"    Actually costs: ${final:.2f} (+${diff:.0f} / +{pct:.0f}%)")
                print(f"    Seller: {seller}")
                print()
        
        # Summary
        print("="*60)
        print("📈 SUMMARY:")
        print(f"  Total tickets checked: {len(verified_listings)}")
        print(f"  Accurately priced: {len(accurate)}")
        print(f"  Misleading prices: {len(misleading)}")
        
        if misleading:
            avg_increase = sum(l['price_diff'] for l in misleading) / len(misleading)
            avg_pct = sum(l['pct_diff'] for l in misleading) / len(misleading)
            print(f"  Average hidden fees: +${avg_increase:.0f} (+{avg_pct:.0f}%)")
            
            worst = max(misleading, key=lambda x: x['price_diff'])
            print(f"  Worst offender: {worst['seller']} added ${worst['price_diff']:.0f} in fees!")

async def main():
    monitor = FinalPriceMonitor()
    
    # Check tickets under $400 (SeatPick price)
    verified = await monitor.fetch_and_verify(max_price=400)
    
    # Generate report
    monitor.generate_report(verified)
    
    # Return tickets that are ACTUALLY under $400 after fees
    actually_affordable = [
        l for l in verified 
        if l['final_price'] <= 400
    ]
    
    if actually_affordable:
        print("\n" + "="*60)
        print("💰 TICKETS ACTUALLY UNDER $400 (with all fees):")
        print("="*60)
        for listing in sorted(actually_affordable, key=lambda x: x['final_price']):
            section = listing['section']
            row = f"Row {listing['row']}" if listing['row'] else ""
            final = listing['final_price']
            seller = listing['seller']
            print(f"  {section:20s} {row:10s} ${final:6.2f} via {seller}")
    
    return actually_affordable

if __name__ == "__main__":
    asyncio.run(main())