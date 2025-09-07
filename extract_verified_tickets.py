#!/usr/bin/env python3
"""
Extract ONLY VERIFIED tickets with FINAL checkout prices under $400
"""
import asyncio
import csv
from datetime import datetime
from premium_monitor import PremiumSeatPickMonitor

async def extract_verified_tickets_to_csv():
    """Extract only verified tickets with final prices to CSV"""
    monitor = PremiumSeatPickMonitor()
    
    print("🔍 Fetching and verifying tickets from premium sections...")
    print("⏳ This will take a moment as we verify actual checkout prices...\n")
    
    # Get tickets with verification
    tickets = await monitor.scrape_tickets_detailed()
    
    if not tickets:
        print("No tickets found")
        return None
    
    # Filter for ONLY verified tickets under $400 (excluding Reserved Seating)
    verified_tickets = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    for ticket in tickets:
        # Skip Reserved Seating
        if ticket.get('section') == 'Reserved Seating':
            continue
            
        # Only include if verified
        if not ticket.get('verified'):
            print(f"   ❌ Skipping unverified: {ticket['section']} ${ticket['price']} via {ticket['seller']}")
            continue
        
        # Use the FINAL verified price (what you actually pay)
        final_price = ticket.get('final_price') or ticket.get('price')
        
        # Skip if final price is >= $400
        if final_price >= 400:
            print(f"   ❌ Too expensive: {ticket['section']} final=${final_price} via {ticket['seller']}")
            continue
            
        # Check quantity - must be able to buy 2 together
        quantity = ticket.get('quantity', 1)
        if quantity < 2:
            print(f"   ❌ Single ticket only: {ticket['section']} via {ticket['seller']}")
            continue
        
        verified_tickets.append({
            'timestamp': timestamp,
            'section': ticket['section'],
            'row': ticket.get('row', ''),
            'seatpick_price': ticket.get('seatpick_price', ticket['price']),
            'final_price_per_ticket': final_price,
            'total_for_2': final_price * 2,
            'price_accurate': 'Yes' if ticket.get('accurate') else 'No',
            'seller': ticket['seller'],
            'checkout_url': ticket.get('checkout_link', ''),
            'site': 'SeatPick'
        })
        
        print(f"   ✅ Verified: {ticket['section']} final=${final_price}/ticket via {ticket['seller']}")
    
    if not verified_tickets:
        print("\n❌ No verified tickets found under $400 where you can buy 2 together")
        return None
    
    # Sort by final price
    verified_tickets.sort(key=lambda x: x['final_price_per_ticket'])
    
    # Write to CSV
    csv_filename = f'verified_tickets_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['timestamp', 'section', 'row', 'seatpick_price', 
                      'final_price_per_ticket', 'total_for_2', 'price_accurate',
                      'seller', 'site', 'checkout_url']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for ticket in verified_tickets:
            writer.writerow(ticket)
    
    print(f"\n✅ Saved {len(verified_tickets)} VERIFIED tickets to {csv_filename}")
    
    # Print summary
    print("\n📊 Summary of VERIFIED tickets under $400:")
    print("=" * 70)
    
    for ticket in verified_tickets:
        price_warning = "" if ticket['price_accurate'] == 'Yes' else " ⚠️ (price differs from listing)"
        print(f"{ticket['section']:15} - Final: ${ticket['final_price_per_ticket']:3.0f}/ticket (${ticket['total_for_2']:4.0f} total) - {ticket['seller']}{price_warning}")
    
    # Alert about tickets under $300
    under_300 = [t for t in verified_tickets if t['final_price_per_ticket'] < 300]
    if under_300:
        print("\n🚨 ALERT: Tickets under $300/ticket (your threshold):")
        for ticket in under_300:
            print(f"   {ticket['section']} - ${ticket['final_price_per_ticket']:.0f}/ticket via {ticket['seller']}")
    
    return csv_filename

if __name__ == "__main__":
    csv_file = asyncio.run(extract_verified_tickets_to_csv())
    if csv_file:
        print(f"\n📁 CSV file created: {csv_file}")
    else:
        print("\n⚠️ No CSV created - no verified tickets met the criteria")