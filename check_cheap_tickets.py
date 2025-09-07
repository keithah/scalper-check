#!/usr/bin/env python3
import asyncio
import aiohttp

async def find_cheap_tickets():
    """Find tickets that might be causing false alerts"""
    
    event_id = "366607"
    api_url = f"https://seatpick.com/api/proxy/4/events/{event_id}/listings"
    
    # Your desired sections (NO GA)
    desired_sections = [
        "Center", "Front Center", "Front Left", "Front Right", 
        "Left", "Reserved Seating", "Right"
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
    
    print("🎫 Looking for tickets under $400 in premium sections:")
    
    cheap_tickets = []
    for ticket in data.get('listings', []):
        if ticket.get('section') not in desired_sections:
            continue
            
        price = ticket.get('price', 0)
        if price <= 400:
            cheap_tickets.append(ticket)
    
    # Sort by price
    cheap_tickets.sort(key=lambda x: x.get('price', 0))
    
    print(f"\n📊 Found {len(cheap_tickets)} premium tickets under $400:")
    print("-" * 80)
    
    for i, ticket in enumerate(cheap_tickets):
        price = ticket.get('price', 0)
        section = ticket.get('section', '')
        seller = ticket.get('seller', '')
        quantity = ticket.get('quantity', 1)
        splits = ticket.get('splits', [])
        
        # Check if can buy 2 together
        can_buy_two = quantity >= 2 and (not splits or 2 in splits or max(splits) >= 2)
        two_status = "✅ 2+ together" if can_buy_two else f"❌ Only {quantity}, splits: {splits}"
        
        print(f"{i+1:2d}. {section:15s} ${price:4.0f} via {seller:12s} {two_status}")
        if ticket.get('deepLink'):
            print(f"    Link: {ticket['deepLink'][:80]}...")
        print()

if __name__ == "__main__":
    asyncio.run(find_cheap_tickets())