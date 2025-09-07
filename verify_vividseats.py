#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright
import re

async def verify_vividseats_prices():
    """Verify the actual prices on VividSeats for the specific tickets"""
    
    tickets_to_check = [
        {
            "section": "Right Row 6",
            "seatpick_price": 314,
            "url": "https://vivid-seats.pxf.io/c/3289547/952533/12730?u=https://www.vividseats.com/r/production/5644998?showDetails=VB13466001947&qty=2"
        },
        {
            "section": "Left Row 7", 
            "seatpick_price": 323,
            "url": "https://vivid-seats.pxf.io/c/3289547/952533/12730?u=https://www.vividseats.com/r/production/5644998?showDetails=VB13473905591&qty=2"
        }
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        
        for ticket in tickets_to_check:
            print(f"\n🔍 Checking {ticket['section']} - Listed at ${ticket['seatpick_price']} on SeatPick")
            print(f"   URL: {ticket['url'][:80]}...")
            
            try:
                page = await context.new_page()
                
                print("   Loading VividSeats page...")
                await page.goto(ticket['url'], wait_until='domcontentloaded', timeout=20000)
                await page.wait_for_timeout(5000)  # Let page fully load
                
                # Get page content for price extraction
                content = await page.content()
                
                # Find all prices on page
                price_matches = re.findall(r'\$(\d{1,4}(?:[,\.]\d{2})?)', content)
                
                if price_matches:
                    prices = []
                    for match in price_matches:
                        try:
                            # Convert to integer
                            price_int = int(re.sub(r'[,\.]', '', match.split('.')[0]))
                            if 200 <= price_int <= 500:  # Filter to reasonable range
                                prices.append(price_int)
                        except:
                            continue
                    
                    if prices:
                        # Remove duplicates and sort
                        unique_prices = sorted(set(prices))
                        print(f"   Found prices on VividSeats: {unique_prices}")
                        
                        # Find closest to SeatPick price
                        closest = min(unique_prices, key=lambda x: abs(x - ticket['seatpick_price']))
                        
                        if closest == ticket['seatpick_price']:
                            print(f"   ✅ PRICE MATCH: VividSeats shows ${closest} (same as SeatPick)")
                        else:
                            diff = closest - ticket['seatpick_price']
                            print(f"   ⚠️  PRICE MISMATCH: SeatPick shows ${ticket['seatpick_price']}, VividSeats shows ${closest} (${diff:+d} difference)")
                        
                        # Look for "per ticket" prices if quantity is 2
                        double_prices = [p//2 for p in unique_prices if p > 500 and p < 1000]
                        if double_prices:
                            print(f"   Note: Possible total prices for 2 tickets: ${double_prices}")
                    else:
                        print("   ❓ No prices found in expected range")
                else:
                    print("   ❓ Could not extract prices from page")
                
                # Take screenshot for debugging
                await page.screenshot(path=f"vividseats_{ticket['section'].replace(' ', '_')}.png")
                print(f"   📸 Screenshot saved as vividseats_{ticket['section'].replace(' ', '_')}.png")
                
                await page.close()
                
            except Exception as e:
                print(f"   ❌ Error: {str(e)[:100]}")
                try:
                    await page.close()
                except:
                    pass
            
            await asyncio.sleep(2)  # Rate limiting
        
        await browser.close()
        
        print("\n" + "="*60)
        print("VERIFICATION COMPLETE")
        print("Check the screenshots to see the actual VividSeats checkout pages")

if __name__ == "__main__":
    asyncio.run(verify_vividseats_prices())