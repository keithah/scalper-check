#!/usr/bin/env python3
import os
import sys

# Add the monitor_tickets module to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from monitor_tickets import SeatPickMonitor

def test_notifications():
    print("=== Testing Notification Systems ===")
    
    # Initialize monitor
    monitor = SeatPickMonitor()
    
    # Create fake ticket data for testing
    fake_tickets = [
        {"section": "Section 101", "price": 350, "raw_text": "Section 101 - $350 each"},
        {"section": "Floor Premium", "price": 375, "raw_text": "Floor Premium - $375 each"},
        {"section": "Section 202", "price": 320, "raw_text": "Section 202 - $320 each"}
    ]
    
    print(f"Testing with {len(fake_tickets)} fake premium tickets")
    
    # Test notification methods
    subject = "🎵 TEST: Premium Atmosphere Morrison Tickets Available Under $400!"
    
    body_html = f"""
    <h1>TEST: Premium tickets found for Atmosphere Morrison at Red Rocks!</h1>
    <p>Found {len(fake_tickets)} premium ticket(s) under $400:</p>
    <table border="1" cellpadding="5" cellspacing="0">
        <tr>
            <th>Section</th>
            <th>Price</th>
        </tr>
    """
    
    for ticket in fake_tickets:
        body_html += f"""
        <tr>
            <td>{ticket['section']}</td>
            <td>${ticket['price']}</td>
        </tr>
        """
    
    body_html += """
    </table>
    <p><a href="https://seatpick.com/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/366607?quantity=2">View tickets on SeatPick</a></p>
    <p>This is a test notification - the script is working!</p>
    """
    
    body_text = f"TEST: Found {len(fake_tickets)} premium tickets under $400 for Atmosphere Morrison at Red Rocks on Sep 19, 2025. Sections: " + ", ".join([f"{t['section']} (${t['price']})" for t in fake_tickets]) + ". This is a test notification - the script is working!"
    
    # Test notifications
    print("\n--- Testing Notifications ---")
    success = monitor.send_notifications(subject, body_html, body_text)
    
    if success:
        print("✓ At least one notification method worked!")
    else:
        print("✗ No notification methods worked")
    
    # Print configuration status
    print("\n--- Configuration Status ---")
    print(f"MailerSend configured: {monitor.use_mailersend} (API key: {'✓' if monitor.mailersend_api_key else '✗'})")
    print(f"SimplePush configured: {monitor.use_simplepush} (key: {'✓' if monitor.simplepush_key else '✗'})")
    print(f"SMTP configured: {'✓' if monitor.email_user and monitor.email_pass else '✗'}")
    print(f"Email recipient: {monitor.email_to or 'Not set'}")

if __name__ == "__main__":
    test_notifications()