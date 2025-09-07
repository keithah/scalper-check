#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright
import re
import json

async def verify_current_seatpick_prices():
    """Verify current prices shown on SeatPick website with filters applied"""
    
    url = "https://seatpick.com/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/366607?quantity=2"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Show browser for debugging
        page = await browser.new_page()
        
        print("🔍 Loading SeatPick page...")
        await page.goto(url, wait_until='networkidle')
        await page.wait_for_timeout(3000)
        
        # Click on Sections filter
        print("📋 Applying section filters...")
        try:
            # Click the Sections button
            sections_button = page.locator('button:has-text("Sections")')
            if await sections_button.count() > 0:
                await sections_button.click()
                await page.wait_for_timeout(1000)
                
                # Select desired sections
                sections_to_select = [
                    "Center",
                    "Front Center",
                    "Front Left", 
                    "Front Right",
                    "Left",
                    "Reserved Seating",
                    "Right"
                ]
                
                for section in sections_to_select:
                    checkbox = page.locator(f'label:has-text("{section}") input[type="checkbox"]')
                    if await checkbox.count() > 0:
                        if not await checkbox.is_checked():
                            await checkbox.click()
                            print(f"  ✓ Selected {section}")
                            await page.wait_for_timeout(500)
                
                # Click View Listings
                view_button = page.locator('button:has-text("View Listings")')
                if await view_button.count() > 0:
                    await view_button.click()
                    print("  ✓ Applied filters")
                    await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"Error applying filters: {e}")
        
        # Extract visible listings
        print("\n📊 Current listings on page:")
        print("-" * 60)
        
        # Try to find listing elements
        listings = await page.locator('[data-testid*="listing"], .listing-item, [class*="listing"]').all()
        
        found_listings = []
        for i, listing in enumerate(listings[:20]):  # Check first 20
            try:
                text = await listing.inner_text()
                
                # Extract price
                price_match = re.search(r'\$(\d+)', text)
                if not price_match:
                    continue
                    
                price = int(price_match.group(1))
                
                # Extract section info
                section_info = "Unknown"
                if "Reserved Seating" in text:
                    section_info = "Reserved Seating"
                elif "Right" in text:
                    section_info = "Right"
                elif "Left" in text:
                    section_info = "Left"
                elif "Front Right" in text:
                    section_info = "Front Right"
                elif "Front Left" in text:
                    section_info = "Front Left"
                elif "Front Center" in text:
                    section_info = "Front Center"
                elif "Center" in text:
                    section_info = "Center"
                
                # Extract vendor
                vendor = "Unknown"
                vendor_patterns = {
                    "viagogo": ["viagogo", "vgg"],
                    "vividseats": ["vividseats", "vivid seats"],
                    "ticketnetwork": ["ticketnetwork", "ticket network"],
                    "events365": ["events365"]
                }
                
                text_lower = text.lower()
                for vendor_name, patterns in vendor_patterns.items():
                    if any(p in text_lower for p in patterns):
                        vendor = vendor_name
                        break
                
                # Look for vendor in image alt text or logos
                vendor_imgs = await listing.locator('img[alt*="logo"], img[alt*="seller"]').all()
                for img in vendor_imgs:
                    alt = await img.get_attribute('alt')
                    if alt:
                        for vendor_name, patterns in vendor_patterns.items():
                            if any(p in alt.lower() for p in patterns):
                                vendor = vendor_name
                                break
                
                found_listings.append({
                    'section': section_info,
                    'price': price,
                    'vendor': vendor,
                    'text': text[:200]
                })
                
                print(f"{i+1}. {section_info:20s} ${price:4d}  via {vendor}")
                
            except Exception as e:
                continue
        
        print("-" * 60)
        print(f"Total found: {len(found_listings)} listings")
        
        # Check for specific prices mentioned
        print("\n🔍 Looking for specific tickets:")
        if any(l['section'] == 'Right' and l['price'] == 314 for l in found_listings):
            print("  ✓ Found Right $314 (VividSeats)")
        else:
            print("  ✗ Right $314 not found on current page")
            
        if any(l['section'] == 'Left' and l['price'] == 323 for l in found_listings):
            print("  ✓ Found Left $323 (VividSeats)")
        else:
            print("  ✗ Left $323 not found on current page")
        
        # Take screenshot
        await page.screenshot(path='seatpick_current.png')
        print("\n📸 Screenshot saved as seatpick_current.png")
        
        input("\n⏸️  Press Enter to close browser...")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify_current_seatpick_prices())