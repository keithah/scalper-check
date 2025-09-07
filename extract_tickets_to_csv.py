#!/usr/bin/env python3
"""
Extract all unique tickets from the monitoring system and save to CSV
"""
import asyncio
import csv
from datetime import datetime
import aiohttp

async def extract_tickets_to_csv():
    """Extract tickets and save to CSV with all details"""
    # Define constants directly
    event_id = "366607"
    base_url = "https://seatpick.com"
    api_url = f"https://seatpick.com/api/proxy/4/events/{event_id}/listings"
    
    print("🔍 Fetching tickets from SeatPick API...")
    
    # Fetch from SeatPick API directly
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': f'{base_url}/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/{event_id}'
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, headers=headers) as response:
            if response.status != 200:
                print("❌ Failed to fetch listings")
                return
                
            data = await response.json()
    
    # Process only tickets under $400 (excluding Reserved Seating)
    tickets = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Premium sections we care about (excluding Reserved Seating)
    desired_sections = ["Center", "Front Center", "Front Left", "Front Right", "Left", "Right"]
    
    for listing in data.get('listings', []):
        section = listing.get('section', 'Unknown')
        price = listing.get('price', 0)
        
        # Skip if price >= $400 or section is Reserved Seating or not in desired sections
        if price >= 400:
            continue
        if section == "Reserved Seating":
            continue
        if section not in desired_sections:
            continue
            
        quantity = listing.get('quantity', 1)
        seller = listing.get('seller', 'Unknown')
        deep_link = listing.get('deepLink', '')
        row = listing.get('row', '')
        splits = listing.get('splits', [])
        
        # Determine if 2 tickets can be bought together
        can_buy_2 = quantity >= 2 and (not splits or 2 in splits)
        
        # Only include if 2 tickets can be bought together
        if not can_buy_2:
            continue
        
        tickets.append({
            'timestamp': timestamp,
            'section': section,
            'row': row,
            'price_per_ticket': price,
            'total_for_2': price * 2,
            'quantity': quantity,
            'seller': seller,
            'checkout_url': deep_link,
            'site': 'SeatPick'
        })
    
    # Sort by price
    tickets.sort(key=lambda x: x['price_per_ticket'])
    
    # Write to CSV
    csv_filename = f'tickets_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['timestamp', 'section', 'row', 'price_per_ticket', 'total_for_2', 
                      'quantity', 'seller', 'site', 'checkout_url']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for ticket in tickets:
            writer.writerow(ticket)
    
    print(f"✅ Saved {len(tickets)} tickets to {csv_filename}")
    
    # Print summary statistics
    print("\n📊 Summary Statistics:")
    print(f"Premium tickets under $400 (2 together): {len(tickets)}")
    
    if tickets:
        # Count by section
        sections = {}
        for ticket in tickets:
            section = ticket['section']
            if section not in sections:
                sections[section] = []
            sections[section].append(ticket)
        
        print(f"Sections with tickets: {len(sections)}")
        print("\n🎯 Tickets by section (all under $400, 2 tickets together):")
        for section in ["Front Left", "Front Right", "Front Center", "Left", "Right", "Center"]:
            if section in sections:
                section_tickets = sections[section]
                min_price = min(t['price_per_ticket'] for t in section_tickets)
                max_price = max(t['price_per_ticket'] for t in section_tickets)
                print(f"  {section}: {len(section_tickets)} options (${min_price}-${max_price}/ticket)")
        
        # Show all tickets sorted by price
        print("\n💰 All tickets (sorted by price per ticket):")
        for ticket in tickets:
            print(f"  {ticket['section']:15} - ${ticket['price_per_ticket']:3.0f}/ticket (${ticket['total_for_2']:4.0f} total) - {ticket['seller']}")
    else:
        print("No tickets found under $400 where you can buy 2 together (excluding Reserved Seating)")
    
    return csv_filename

if __name__ == "__main__":
    csv_file = asyncio.run(extract_tickets_to_csv())
    print(f"\n📁 CSV file created: {csv_file}")