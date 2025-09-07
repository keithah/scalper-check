#!/usr/bin/env python3
import asyncio
import aiohttp
import json

async def check_quantity_info():
    """Check if tickets have quantity information"""
    
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
    
    # Look at first few tickets to see structure
    print("🎫 Sample ticket data structure:")
    for i, ticket in enumerate(data.get('listings', [])[:3]):
        print(f"\nTicket {i+1}:")
        for key, value in ticket.items():
            if len(str(value)) < 200:  # Don't print super long URLs
                print(f"  {key}: {value}")
            else:
                print(f"  {key}: {str(value)[:100]}...")
    
    # Check if there's quantity info
    quantity_fields = []
    for ticket in data.get('listings', []):
        for key in ticket.keys():
            if 'quantity' in key.lower() or 'qty' in key.lower() or 'count' in key.lower():
                if key not in quantity_fields:
                    quantity_fields.append(key)
    
    if quantity_fields:
        print(f"\n🔢 Found quantity-related fields: {quantity_fields}")
    else:
        print("\n❌ No quantity fields found in API response")

if __name__ == "__main__":
    asyncio.run(check_quantity_info())