#!/usr/bin/env python3
import asyncio
import aiohttp

async def find_specific_tickets():
    """Find the specific problematic tickets"""
    
    event_id = "366607"
    api_url = f"https://seatpick.com/api/proxy/4/events/{event_id}/listings"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': f'https://seatpick.com/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/{event_id}'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:
            if response.status != 200:
                print(f"❌ Failed to fetch listings: {response.status}")
                return
                
            data = await response.json()
    
    # Look for problematic tickets
    print("🔍 Looking for problematic tickets:")
    
    for ticket in data.get('listings', []):
        price = ticket.get('price', 0)
        seller = ticket.get('seller', '')
        section = ticket.get('section', '')
        
        # Look for the specific tickets mentioned
        if (price == 545 or price == 680) and seller == 'tn':
            print(f"\n📍 Found: {section} ${price} via {seller}")
            print(f"   Row: {ticket.get('row', 'N/A')}")
            print(f"   DeepLink: {ticket.get('deepLink', 'No link')[:100]}...")
            
        elif price == 328 and 'vgg' in seller:
            print(f"\n📍 Found: {section} ${price} via {seller}")
            print(f"   Row: {ticket.get('row', 'N/A')}")
            print(f"   DeepLink: {ticket.get('deepLink', 'No link')[:100]}...")
            
        elif price == 293:
            print(f"\n📍 Found: {section} ${price} via {seller}")
            print(f"   Row: {ticket.get('row', 'N/A')}")
            print(f"   DeepLink: {ticket.get('deepLink', 'No link')[:100]}...")
    
    # Check what 'tn' and 'vgg' sellers are
    sellers = set()
    for ticket in data.get('listings', []):
        sellers.add(ticket.get('seller', ''))
    
    print(f"\n🏪 All sellers found: {sorted(sellers)}")

if __name__ == "__main__":
    asyncio.run(find_specific_tickets())