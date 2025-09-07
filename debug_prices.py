#!/usr/bin/env python3
import asyncio
from premium_monitor import PremiumSeatPickMonitor

async def debug_prices():
    """Debug price formatting"""
    monitor = PremiumSeatPickMonitor()
    
    # Test with fake ticket data
    fake_tickets = [
        {
            'section': 'Center',
            'row': '10',
            'price': 285.50,
            'seller': 'vividseats',
            'verified': True,
            'final_price': 285.50,
            'seatpick_price': 250.00,
            'price_diff': 35.50,
            'checkout_link': 'https://example.com',
            'accurate': False
        },
        {
            'section': 'Left',
            'row': '5',
            'price': 320.00,
            'seller': 'viagogo',
            'verified': True,
            'final_price': 320.00,
            'seatpick_price': 320.00,
            'price_diff': 0,
            'checkout_link': 'https://example.com',
            'accurate': True
        }
    ]
    
    print("Testing price formatting:")
    for ticket in fake_tickets:
        print(f"Ticket: {ticket['section']} Row {ticket['row']}")
        print(f"  Raw price: {ticket['price']}")
        print(f"  Final price: {ticket['final_price']}")
        print(f"  Verified: {ticket['verified']}")
        print(f"  Accurate: {ticket['accurate']}")
        
        # Test the formatting logic from premium_monitor.py
        if ticket.get('verified') and ticket.get('final_price'):
            if ticket.get('accurate', True):
                verification_icon = "✅"
                price_display = f"${ticket['final_price']:.0f}"
            else:
                verification_icon = "⚠️"
                seatpick_price = ticket.get('seatpick_price', ticket['price'])
                price_display = f"${ticket['final_price']:.0f} (listed: ${seatpick_price})"
        else:
            verification_icon = "❓"
            price_display = f"${ticket['price']}"
            
        print(f"  Formatted price display: {price_display}")
        print(f"  Icon: {verification_icon}")
        print()
    
    # Test HTML generation
    html = monitor.format_tickets_html_premium(fake_tickets, "Test Tickets")
    print("Generated HTML snippet:")
    print(html[:500] + "..." if len(html) > 500 else html)

if __name__ == "__main__":
    asyncio.run(debug_prices())