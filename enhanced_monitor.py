#!/usr/bin/env python3
import asyncio
import os
import sys
from datetime import datetime
import re
from detailed_scraper import DetailedSeatPickScraper

# Import notification functionality from original monitor
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from monitor_tickets import SeatPickMonitor

class EnhancedSeatPickMonitor(SeatPickMonitor):
    def __init__(self):
        super().__init__()
        self.scraper = DetailedSeatPickScraper()
    
    async def scrape_tickets_detailed(self):
        """Use the enhanced scraper to get detailed ticket information"""
        try:
            print("🔍 Running enhanced ticket scraping...")
            tickets = await self.scraper.scrape_with_playwright()
            
            # Process tickets to match expected format
            processed_tickets = []
            for ticket in tickets:
                processed_tickets.append({
                    'section': ticket['section'],
                    'price': ticket['price'],
                    'seller': ticket['seller'],
                    'verified': ticket.get('verified', False),
                    'verified_price': ticket.get('verified_price'),
                    'raw_text': ticket.get('raw_text', '')
                })
            
            print(f"✅ Found {len(processed_tickets)} detailed tickets")
            return processed_tickets
            
        except Exception as e:
            print(f"❌ Error in enhanced scraping: {e}")
            # Fallback to basic scraping
            print("🔄 Falling back to basic scraping...")
            return self.scrape_tickets()
    
    def filter_tickets_by_criteria(self, tickets, max_price=400, include_ga=True):
        """Filter tickets based on criteria with separate categories"""
        premium_tickets = []
        ga_tickets = []
        
        for ticket in tickets:
            if ticket['price'] > max_price:
                continue
                
            section = ticket['section'].lower()
            is_ga = any(term in section for term in ['general admission', 'floor ga', 'section ga', 'row ga', ' ga '])
            
            if is_ga:
                if include_ga:
                    ga_tickets.append(ticket)
            else:
                premium_tickets.append(ticket)
        
        return premium_tickets, ga_tickets
    
    def format_tickets_html_enhanced(self, premium_tickets, ga_tickets, title):
        """Create enhanced HTML table with seller and verification info"""
        html = f"<h2>{title}</h2>"
        
        if premium_tickets:
            html += """
            <h3>🎯 Premium Tickets (Non-GA)</h3>
            <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse;">
                <tr style="background-color: #f0f0f0;">
                    <th>Section</th>
                    <th>Price</th>
                    <th>Seller</th>
                    <th>Verified</th>
                </tr>
            """
            
            for ticket in premium_tickets:
                verification_icon = "✅" if ticket.get('verified') else "❓"
                verified_price_text = f" (Actual: ${ticket.get('verified_price')})" if ticket.get('verified_price') else ""
                
                html += f"""
                <tr>
                    <td>{ticket['section']}</td>
                    <td>${ticket['price']}{verified_price_text}</td>
                    <td>{ticket['seller']}</td>
                    <td>{verification_icon}</td>
                </tr>
                """
            
            html += "</table><br>"
        
        if ga_tickets:
            html += f"""
            <h3>🎫 General Admission Tickets</h3>
            <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse;">
                <tr style="background-color: #f9f9f9;">
                    <th>Section</th>
                    <th>Price</th>
                    <th>Seller</th>
                    <th>Verified</th>
                </tr>
            """
            
            for ticket in ga_tickets[:10]:  # Limit GA tickets to first 10
                verification_icon = "✅" if ticket.get('verified') else "❓"
                verified_price_text = f" (Actual: ${ticket.get('verified_price')})" if ticket.get('verified_price') else ""
                
                html += f"""
                <tr>
                    <td>{ticket['section']}</td>
                    <td>${ticket['price']}{verified_price_text}</td>
                    <td>{ticket['seller']}</td>
                    <td>{verification_icon}</td>
                </tr>
                """
            
            if len(ga_tickets) > 10:
                html += f"<tr><td colspan='4'><em>... and {len(ga_tickets) - 10} more GA tickets</em></td></tr>"
            
            html += "</table><br>"
        
        return html
    
    async def check_for_alerts(self):
        """Enhanced alert checking with detailed ticket information"""
        tickets = await self.scrape_tickets_detailed()
        if not tickets:
            print("No tickets found")
            return
        
        premium_tickets, ga_tickets = self.filter_tickets_by_criteria(tickets, max_price=400)
        
        # Send alert if premium tickets are found, or if only GA tickets and they're very cheap
        should_alert = False
        alert_reason = ""
        
        if premium_tickets:
            should_alert = True
            alert_reason = f"Found {len(premium_tickets)} premium (non-GA) tickets under $400"
        elif ga_tickets:
            # Alert for GA tickets if they're under $100
            cheap_ga = [t for t in ga_tickets if t['price'] < 100]
            if cheap_ga:
                should_alert = True
                alert_reason = f"Found {len(cheap_ga)} GA tickets under $100"
        
        if should_alert:
            subject = f"🎵 Atmosphere Morrison Tickets Available! ({alert_reason})"
            
            body_html = f"""
            <h1>Ticket Alert: Atmosphere Morrison at Red Rocks!</h1>
            <p><strong>{alert_reason}</strong></p>
            {self.format_tickets_html_enhanced(premium_tickets, ga_tickets, "Available Tickets Under $400")}
            <p><a href="{self.url}">🎫 View all tickets on SeatPick</a></p>
            <p><em>Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
            
            <hr>
            <small>
            <p>Legend:</p>
            <ul>
                <li>✅ = Price verified by checking seller site</li>
                <li>❓ = Price not yet verified</li>
                <li>🎯 Premium = Non-GA tickets (better seating)</li>
                <li>🎫 GA = General Admission tickets</li>
            </ul>
            </small>
            """
            
            # Create text version for push notifications
            body_text = f"{alert_reason} for Atmosphere Morrison at Red Rocks on Sep 19, 2025.\n\n"
            
            if premium_tickets:
                body_text += f"Premium tickets: "
                body_text += ", ".join([f"{t['section']} ${t['price']}" for t in premium_tickets[:3]])
                if len(premium_tickets) > 3:
                    body_text += f" + {len(premium_tickets) - 3} more"
                body_text += "\n\n"
            
            if ga_tickets:
                cheap_ga = [t for t in ga_tickets if t['price'] < 100]
                if cheap_ga:
                    body_text += f"GA tickets: "
                    body_text += ", ".join([f"${t['price']}" for t in cheap_ga[:5]])
                    if len(cheap_ga) > 5:
                        body_text += f" + {len(cheap_ga) - 5} more"
                    body_text += "\n"
            
            body_text += f"\nCheck SeatPick for details and purchase links."
            
            self.send_notifications(subject, body_html, body_text)
            print(f"🚨 Alert sent: {alert_reason}")
            
            # Print summary to console
            print(f"\n📊 ALERT SUMMARY:")
            print(f"   Premium tickets: {len(premium_tickets)}")
            print(f"   GA tickets: {len(ga_tickets)}")
            
            if premium_tickets:
                print(f"   Premium price range: ${min(t['price'] for t in premium_tickets)}-${max(t['price'] for t in premium_tickets)}")
            if ga_tickets:
                print(f"   GA price range: ${min(t['price'] for t in ga_tickets)}-${max(t['price'] for t in ga_tickets)}")
        
        else:
            print("No tickets meeting alert criteria found")
            print(f"Total tickets found: {len(tickets)}")
            print(f"Premium tickets under $400: {len(premium_tickets)}")
            print(f"GA tickets under $400: {len(ga_tickets)}")
    
    async def send_daily_summary(self):
        """Enhanced daily summary with detailed ticket information"""
        tickets = await self.scrape_tickets_detailed()
        if not tickets:
            print("No tickets found for daily summary")
            return
        
        premium_tickets, ga_tickets = self.filter_tickets_by_criteria(tickets, max_price=400)
        all_summary_tickets = premium_tickets + ga_tickets
        
        subject = f"📊 Daily Atmosphere Morrison Ticket Summary - {datetime.now().strftime('%Y-%m-%d')}"
        
        if all_summary_tickets:
            body_html = f"""
            <h1>Daily Ticket Summary: Atmosphere Morrison at Red Rocks</h1>
            <p>Found <strong>{len(all_summary_tickets)} tickets under $400</strong> ({len(premium_tickets)} premium, {len(ga_tickets)} GA)</p>
            {self.format_tickets_html_enhanced(premium_tickets, ga_tickets, "All Available Tickets Under $400")}
            
            <h3>📈 Price Analysis</h3>
            <ul>
            """
            
            if premium_tickets:
                min_premium = min(t['price'] for t in premium_tickets)
                max_premium = max(t['price'] for t in premium_tickets)
                avg_premium = sum(t['price'] for t in premium_tickets) // len(premium_tickets)
                body_html += f"<li>Premium tickets: ${min_premium}-${max_premium} (avg: ${avg_premium})</li>"
            
            if ga_tickets:
                min_ga = min(t['price'] for t in ga_tickets)
                max_ga = max(t['price'] for t in ga_tickets)
                avg_ga = sum(t['price'] for t in ga_tickets) // len(ga_tickets)
                body_html += f"<li>GA tickets: ${min_ga}-${max_ga} (avg: ${avg_ga})</li>"
            
            # Seller breakdown
            sellers = {}
            for ticket in all_summary_tickets:
                seller = ticket['seller']
                if seller not in sellers:
                    sellers[seller] = []
                sellers[seller].append(ticket['price'])
            
            body_html += "</ul><h3>🏪 Sellers</h3><ul>"
            for seller, prices in sellers.items():
                body_html += f"<li>{seller}: {len(prices)} tickets (${min(prices)}-${max(prices)})</li>"
            
            body_html += f"""
            </ul>
            <p><a href="{self.url}">🎫 View all tickets on SeatPick</a></p>
            <p><em>Summary generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
            """
        else:
            body_html = f"""
            <h1>Daily Ticket Summary: Atmosphere Morrison at Red Rocks</h1>
            <p>No tickets under $400 found today.</p>
            <p><a href="{self.url}">🎫 Check SeatPick for current listings</a></p>
            <p><em>Summary generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
            """
        
        # Create text summary
        if all_summary_tickets:
            body_text = f"Daily summary: {len(all_summary_tickets)} tickets under $400 available ({len(premium_tickets)} premium, {len(ga_tickets)} GA) for Atmosphere Morrison at Red Rocks."
        else:
            body_text = "Daily summary: No tickets under $400 found for Atmosphere Morrison at Red Rocks today."
        
        self.send_notifications(subject, body_html, body_text)
        print(f"📧 Daily summary sent: {len(all_summary_tickets)} tickets found")

async def main():
    """Main function to run the enhanced monitor"""
    monitor = EnhancedSeatPickMonitor()
    
    if len(sys.argv) > 1 and sys.argv[1] == "daily":
        await monitor.send_daily_summary()
    else:
        await monitor.check_for_alerts()

if __name__ == "__main__":
    asyncio.run(main())