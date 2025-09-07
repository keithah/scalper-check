#!/usr/bin/env python3
import asyncio
import aiohttp
import json

async def debug_api():
    """Debug what we're actually getting from SeatPick API"""
    
    event_id = "366607"
    api_url = f"https://seatpick.com/api/proxy/4/events/{event_id}/listings"
    
    # Your desired sections (NO GA)
    desired_sections = [
        "Center",
        "Front Center", 
        "Front Left",
        "Front Right",
        "Left",
        "Reserved Seating",
        "Right"
    ]
    
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
    
    print(f"📊 Total listings: {len(data.get('listings', []))}")
    
    # Filter for desired sections
    filtered = []
    for listing in data.get('listings', []):
        if listing.get('section') in desired_sections:
            filtered.append(listing)
    
    print(f"📊 Filtered to desired sections: {len(filtered)}")
    
    # Show first few tickets with their actual prices
    print("\n🎫 Sample tickets:")
    for i, ticket in enumerate(filtered[:5]):
        print(f"{i+1}. Section: {ticket.get('section')}")
        print(f"   Row: {ticket.get('row', 'N/A')}")
        print(f"   Price: ${ticket.get('price', 0)}")
        print(f"   Seller: {ticket.get('seller')}")
        print(f"   Has deepLink: {bool(ticket.get('deepLink'))}")
        print()
    
    # Check price ranges
    prices = [t.get('price', 0) for t in filtered]
    if prices:
        print(f"💰 Price range: ${min(prices)} - ${max(prices)}")
        under_400 = [p for p in prices if p < 400]
        under_300 = [p for p in prices if p < 300]
        print(f"📊 Under $400: {len(under_400)} tickets")
        print(f"🚨 Under $300: {len(under_300)} tickets")
        
        if under_300:
            print(f"🔥 Cheapest tickets: {sorted(under_300)[:5]}")

if __name__ == "__main__":
    asyncio.run(debug_api())