#!/usr/bin/env python3
import os
import requests
from datetime import datetime

def send_production_test_email():
    """Send a production-style test email with real formatting"""
    
    api_key = "mlsn.c67ce756febbf400128761affd927bb3b616c042237bca096d7b0edb8ed9e46c"
    from_email = "notifications@ferry-notifier.app"
    to_email = "keith@hadm.net"
    
    # Simulate real ticket data
    fake_tickets = [
        {
            "location": "Left",
            "section": "Section 101",
            "price": 350,
            "seller": "StubHub",
            "verified": True,
            "checkout_link": "https://www.stubhub.com/checkout/atmosphere-morrison-tickets"
        },
        {
            "location": "Center", 
            "section": "Floor Premium",
            "price": 375,
            "seller": "VividSeats",
            "verified": False,
            "checkout_link": "https://www.vividseats.com/checkout/atmosphere-morrison"
        },
        {
            "location": "Right",
            "section": "Section 202",
            "price": 320,
            "seller": "SeatGeek",
            "verified": True,
            "verified_price": 325,
            "checkout_link": "https://seatgeek.com/checkout/atmosphere-morrison"
        },
        {
            "location": "Center",
            "section": "Orchestra",
            "price": 290,
            "seller": "TickPick",
            "verified": True,
            "checkout_link": "https://www.tickpick.com/buy/atmosphere-morrison"
        },
        {
            "location": "Left",
            "section": "Section 103",
            "price": 380,
            "seller": "Gametime",
            "verified": False,
            "checkout_link": "https://gametime.co/checkout/atmosphere-morrison"
        }
    ]
    
    # Group by location
    left_tickets = [t for t in fake_tickets if t["location"] == "Left"]
    center_tickets = [t for t in fake_tickets if t["location"] == "Center"]
    right_tickets = [t for t in fake_tickets if t["location"] == "Right"]
    
    # Generate dynamic subject
    def format_section_for_subject(tickets, location):
        if not tickets:
            return ""
        prices = sorted([t["price"] for t in tickets])
        count = len(tickets)
        if count == 1:
            price_str = f"${prices[0]}"
        elif count == 2:
            price_str = f"${prices[0]}, ${prices[1]}"
        else:
            price_str = ", ".join([f"${p}" for p in prices[:3]])
        return f"{location} ({count}, {price_str})"
    
    subject_parts = []
    if left_tickets:
        subject_parts.append(format_section_for_subject(left_tickets, "Left"))
    if center_tickets:
        subject_parts.append(format_section_for_subject(center_tickets, "Center"))
    if right_tickets:
        subject_parts.append(format_section_for_subject(right_tickets, "Right"))
    
    subject = f"🎯 TEST: ATMOSPHERE RED ROCKS <$400 - {' '.join(subject_parts)}"
    
    # Build HTML body with proper formatting
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th {{ background-color: #2c3e50; color: white; padding: 12px; text-align: left; }}
            td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
            .section-header {{ background-color: #3498db; color: white; font-weight: bold; text-align: center; }}
            .left-header {{ background-color: #3498db; }}
            .center-header {{ background-color: #27ae60; }}
            .right-header {{ background-color: #e74c3c; }}
            .buy-button {{ 
                background-color: #27ae60; 
                color: white !important; 
                padding: 8px 16px; 
                text-decoration: none !important; 
                border-radius: 4px; 
                display: inline-block;
                font-weight: bold;
            }}
            .buy-button:hover {{ background-color: #229954; }}
            .location-badge {{
                display: inline-block;
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
                margin-right: 5px;
            }}
            .left-badge {{ background-color: #3498db; color: white; }}
            .center-badge {{ background-color: #27ae60; color: white; }}
            .right-badge {{ background-color: #e74c3c; color: white; }}
        </style>
    </head>
    <body>
        <h1>🧪 TEST NOTIFICATION - Premium Tickets Found</h1>
        <p><strong>Found {len(fake_tickets)} premium tickets under $400 for Atmosphere Morrison at Red Rocks</strong></p>
        <p>Event Date: September 19, 2025</p>
        
        <table>
            <thead>
                <tr>
                    <th>Location</th>
                    <th>Section</th>
                    <th>Price</th>
                    <th>Seller</th>
                    <th>Verified</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
    """
    
    # Add rows grouped by location
    for location_name, location_tickets, header_class in [
        ("Left", left_tickets, "left-header"),
        ("Center", center_tickets, "center-header"),
        ("Right", right_tickets, "right-header")
    ]:
        if location_tickets:
            html += f"""
                <tr>
                    <td colspan="6" class="section-header {header_class}">{location_name} Sections</td>
                </tr>
            """
            
            for ticket in sorted(location_tickets, key=lambda x: x["price"]):
                # Verification status
                if ticket.get("verified"):
                    if ticket.get("verified_price") and ticket["verified_price"] != ticket["price"]:
                        verification = "⚠️"
                        price_display = f"${ticket['price']} (actual: ${ticket['verified_price']})"
                    else:
                        verification = "✅"
                        price_display = f"${ticket['price']}"
                else:
                    verification = "❓"
                    price_display = f"${ticket['price']}"
                
                # Location badge
                badge_class = f"{location_name.lower()}-badge"
                
                html += f"""
                <tr>
                    <td><span class="location-badge {badge_class}">{location_name}</span></td>
                    <td>{ticket['section']}</td>
                    <td style="font-weight: bold;">{price_display}</td>
                    <td>{ticket['seller']}</td>
                    <td style="text-align: center;">{verification}</td>
                    <td>
                        <a href="{ticket['checkout_link']}" class="buy-button" target="_blank">
                            Buy on {ticket['seller']}
                        </a>
                    </td>
                </tr>
                """
    
    html += """
            </tbody>
        </table>
        
        <hr>
        
        <h3>📊 Summary by Location</h3>
        <ul>
    """
    
    # Add summary
    for location_name, location_tickets in [("Left", left_tickets), ("Center", center_tickets), ("Right", right_tickets)]:
        if location_tickets:
            prices = [t["price"] for t in location_tickets]
            sellers = list(set([t["seller"] for t in location_tickets]))
            html += f"""
            <li><strong>{location_name}:</strong> {len(location_tickets)} tickets, 
                ${min(prices)}-${max(prices)} via {', '.join(sellers)}</li>
            """
    
    html += f"""
        </ul>
        
        <hr>
        
        <p style="font-size: 12px; color: #666;">
        <strong>Legend:</strong><br>
        ✅ = Price verified at checkout<br>
        ⚠️ = Price differs at checkout (see actual price)<br>
        ❓ = Not yet verified<br>
        </p>
        
        <p><a href="https://seatpick.com/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/366607?quantity=2" 
              style="background-color: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; display: inline-block;">
            🎫 View all tickets on SeatPick
        </a></p>
        
        <p style="color: #666; font-size: 12px;">
        <em>This is a test notification showing production formatting<br>
        Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em>
        </p>
    </body>
    </html>
    """
    
    # Send email
    url = "https://api.mailersend.com/v1/email"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    email_data = {
        "from": {
            "email": from_email,
            "name": "SeatPick Monitor"
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "html": html
    }
    
    print(f"📧 Sending production-style test email...")
    print(f"📋 Subject: {subject}")
    
    response = requests.post(url, json=email_data, headers=headers)
    
    if response.status_code == 202:
        print("✅ Production test email sent successfully!")
        print(f"📧 Check {to_email} for the formatted email")
    else:
        print(f"❌ Failed to send: {response.status_code} - {response.text}")

if __name__ == "__main__":
    send_production_test_email()