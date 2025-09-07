#!/usr/bin/env python3
import asyncio
from premium_monitor import PremiumSeatPickMonitor

async def debug_verification():
    """Debug the price verification process"""
    
    monitor = PremiumSeatPickMonitor()
    
    # Get actual tickets
    tickets = await monitor.scrape_tickets_detailed()
    
    print(f"📊 Got {len(tickets)} verified tickets")
    
    for i, ticket in enumerate(tickets):
        print(f"\n🎫 Ticket {i+1}:")
        print(f"  Section: {ticket.get('section')}")
        print(f"  Row: {ticket.get('row', 'N/A')}")
        print(f"  Price (main): {ticket.get('price')}")
        print(f"  Final price: {ticket.get('final_price')}")
        print(f"  SeatPick price: {ticket.get('seatpick_price')}")
        print(f"  Price diff: {ticket.get('price_diff')}")
        print(f"  Seller: {ticket.get('seller')}")
        print(f"  Verified: {ticket.get('verified')}")
        print(f"  Accurate: {ticket.get('accurate')}")
        
        # Test price formatting like in HTML generation
        if ticket.get('verified') and ticket.get('final_price'):
            if ticket.get('accurate', True):
                price_display = f"${ticket['final_price']:.0f}"
            else:
                seatpick_price = ticket.get('seatpick_price', ticket['price'])
                price_display = f"${ticket['final_price']:.0f} (listed: ${seatpick_price})"
        else:
            price_display = f"${ticket['price']}"
        
        print(f"  Formatted for HTML: {price_display}")

if __name__ == "__main__":
    asyncio.run(debug_verification())