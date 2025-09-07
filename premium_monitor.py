#!/usr/bin/env python3
import asyncio
import os
import sys
from datetime import datetime
import re
import aiohttp
from playwright.async_api import async_playwright

# Import notification functionality from original monitor
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from monitor_tickets import SeatPickMonitor

class PremiumSeatPickMonitor(SeatPickMonitor):
    def __init__(self):
        super().__init__()
        self.event_id = "366607"
        self.base_url = "https://seatpick.com"
        self.api_url = f"https://seatpick.com/api/proxy/4/events/{self.event_id}/listings"
        
        # Your desired sections (NO GA)
        self.desired_sections = [
            "Center",
            "Front Center", 
            "Front Left",
            "Front Right",
            "Left",
            "Reserved Seating",
            "Right"
        ]
    
    async def scrape_tickets_detailed(self):
        """Fetch and verify tickets with final prices including all fees"""
        try:
            print("🔍 Fetching tickets from SeatPick API...")
            
            # Fetch from SeatPick API
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Referer': f'{self.base_url}/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/{self.event_id}'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, headers=headers) as response:
                    if response.status != 200:
                        print("❌ Failed to fetch listings")
                        return []
                        
                    data = await response.json()
            
            # Filter for desired sections only (NO GA) and quantity >= 2
            filtered = []
            for listing in data.get('listings', []):
                if listing.get('section') not in self.desired_sections:
                    continue
                
                # Check if exactly 2 tickets are available TOGETHER (no splits)
                quantity = listing.get('quantity', 1)
                splits = listing.get('splits', [])
                
                # Must be able to buy 2 tickets together
                # This means either quantity >= 2 AND (no splits OR splits contains 2)
                can_buy_two_together = quantity >= 2 and (not splits or 2 in splits or max(splits) >= 2)
                
                if not can_buy_two_together:
                    print(f"   Skipping {listing.get('section')} ${listing.get('price')} - quantity: {quantity}, splits: {splits} (need 2 together)")
                    continue
                    
                filtered.append({
                    'section': listing.get('section', ''),
                    'row': listing.get('row', ''),
                    'price': listing.get('price', 0),
                    'seller': listing.get('seller', ''),
                    'deepLink': listing.get('deepLink', ''),
                    'quantity': quantity,
                    'splits': splits,
                    'verified': False,
                    'final_price': None,
                    'price_diff': None
                })
            
            print(f"📊 Found {len(filtered)} tickets in premium sections")
            
            # Verify prices with fees for tickets under $500 (to catch misleading pricing)
            verified_tickets = []
            if filtered:
                print("🔍 Verifying final prices with all fees...")
                verified_tickets = await self.verify_final_prices(filtered[:20])  # Limit to avoid rate limiting
            
            return verified_tickets
            
        except Exception as e:
            print(f"❌ Error in ticket scraping: {e}")
            return []
    
    async def verify_final_prices(self, listings):
        """Verify FINAL checkout prices including all fees"""
        
        if not listings:
            return []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            
            verified = []
            
            for listing in listings:
                section = listing.get('section', '')
                row = listing.get('row', '')
                seatpick_price = listing.get('price', 0)
                seller = listing.get('seller', '')
                deeplink = listing.get('deepLink', '')
                
                if not deeplink:
                    # Add unverified listing
                    verified.append({
                        'section': section,
                        'row': row,
                        'price': seatpick_price,
                        'seller': seller,
                        'verified': False,
                        'final_price': seatpick_price,
                        'price_diff': 0,
                        'checkout_link': '',
                        'accurate': True
                    })
                    continue
                
                try:
                    page = await context.new_page()
                    await page.goto(deeplink, wait_until='domcontentloaded', timeout=20000)
                    await page.wait_for_timeout(3000)
                    
                    # Extract FINAL price with fees
                    final_price = await self.extract_final_price(page, seller)
                    
                    print(f"   Price extraction result: SeatPick=${seatpick_price}, Final=${final_price}")
                    
                    # Reject extracted price if it's suspiciously lower than SeatPick price
                    # For premium tickets, final price should NEVER be less than 80% of SeatPick price
                    if final_price and final_price < (seatpick_price * 0.8):
                        print(f"   ⚠️  Rejecting suspiciously low final price ${final_price} vs SeatPick ${seatpick_price} - likely extraction error")
                        final_price = None
                    
                    if final_price:
                        price_diff = final_price - seatpick_price
                        accurate = abs(price_diff) <= 10
                        
                        # Additional safety check: Never use extracted price if it's way too low
                        filter_price = final_price
                        if seatpick_price > 400 and final_price < 300:
                            print(f"   🛡️  Safety override: Using SeatPick ${seatpick_price} instead of extracted ${final_price} (too low)")
                            filter_price = seatpick_price
                            
                        verified.append({
                            'section': section,
                            'row': row,
                            'price': filter_price,  # Use safe price for filtering
                            'seller': seller,
                            'verified': True,
                            'final_price': final_price,
                            'seatpick_price': seatpick_price,
                            'price_diff': price_diff,
                            'checkout_link': deeplink,
                            'accurate': accurate
                        })
                    else:
                        # Fallback to SeatPick price if can't verify
                        verified.append({
                            'section': section,
                            'row': row,
                            'price': seatpick_price,
                            'seller': seller,
                            'verified': False,
                            'final_price': seatpick_price,
                            'price_diff': 0,
                            'checkout_link': deeplink,
                            'accurate': True
                        })
                    
                    await page.close()
                    
                except Exception as e:
                    print(f"   Error verifying {section}: {str(e)[:50]}")
                    # Add unverified listing on error
                    verified.append({
                        'section': section,
                        'row': row,
                        'price': seatpick_price,
                        'seller': seller,
                        'verified': False,
                        'final_price': seatpick_price,
                        'price_diff': 0,
                        'checkout_link': deeplink,
                        'accurate': True
                    })
                    try:
                        await page.close()
                    except:
                        pass
                
                await asyncio.sleep(1)  # Rate limiting
            
            await browser.close()
        
        return verified
    
    async def extract_final_price(self, page, seller):
        """Extract the FINAL price including all fees from checkout page"""
        
        try:
            content = await page.content()
            
            # VividSeats specific extraction
            if 'vivid' in seller.lower():
                # Look for "Estimated fees included" price first
                match = re.search(r'\$(\d+(?:\.\d{2})?)\s*(?:ea|each)?.*?(?:Estimated fees included|est)', content, re.IGNORECASE)
                if match:
                    price = float(match.group(1))
                    if price >= 100:  # Sanity check
                        return price
                
                # Look for all reasonable price patterns (2+ digits)
                matches = re.findall(r'\$(\d{2,4}(?:\.\d{2})?)', content)
                if matches:
                    prices = [float(m) for m in matches]
                    # Return highest reasonable price (likely the total with fees)
                    valid_prices = [p for p in prices if 100 <= p <= 1000]
                    if valid_prices:
                        return max(valid_prices)
                
                # Fallback: look for any price pattern but be more selective
                all_matches = re.findall(r'\$(\d+(?:\.\d{2})?)', content)
                if all_matches:
                    prices = [float(m) for m in all_matches]
                    reasonable_prices = [p for p in prices if 50 <= p <= 1000]
                    if reasonable_prices:
                        # Return the highest price that's not suspiciously low
                        return max(reasonable_prices)
            
            # TicketNetwork specific extraction  
            elif 'tn' in seller.lower() or 'ticketnetwork' in seller.lower():
                # TicketNetwork often shows misleading prices - be very conservative
                print(f"      Extracting from TicketNetwork page...")
                
                # Only look for very specific final total patterns
                patterns = [
                    r'(?:Order Total|Grand Total|Final Total)[\s\$]*(\d{3,4}(?:\.\d{2})?)',
                    r'(?:Total Due|Amount Due|You Pay)[\s\$]*(\d{3,4}(?:\.\d{2})?)',
                    r'(?:Total Price|Final Price)[\s\$]*(\d{3,4}(?:\.\d{2})?)'
                ]
                
                for i, pattern in enumerate(patterns):
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        for match in matches:
                            price = float(match)
                            print(f"      TicketNetwork pattern {i+1} found: ${price}")
                            # TicketNetwork final prices should be higher than SeatPick, not lower
                            if price >= 400:  # Conservative minimum for TicketNetwork
                                return price
                
                # If no good patterns found, return None (use SeatPick price)
                print(f"      No reliable TicketNetwork price found, using SeatPick price")
                return None
            
            # Viagogo specific extraction
            elif 'vgg' in seller.lower() or 'viagogo' in seller.lower() or 'te' in seller.lower():
                # Look for total price patterns
                patterns = [
                    r'(?:Total|total).*?\$(\d+(?:\.\d{2})?)',
                    r'(?:You Pay|Final Price).*?\$(\d+(?:\.\d{2})?)',
                    r'\$(\d+(?:\.\d{2})?)\s*(?:total|Total)'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        price = float(matches[0])
                        if price >= 200:  # Reasonable minimum
                            return price
                    
                # Fallback to highest reasonable price
                matches = re.findall(r'\$(\d{2,4}(?:\.\d{2})?)', content)
                if matches:
                    prices = [float(m) for m in matches]
                    valid_prices = [p for p in prices if 250 <= p <= 1000]
                    if valid_prices:
                        return max(valid_prices)
            
            # Generic extraction for other sellers
            else:
                # Look for total/final price keywords
                patterns = [
                    r'(?:Total|Final|Checkout).*?\$(\d+(?:\.\d{2})?)',
                    r'\$(\d+(?:\.\d{2})?)\s*(?:total|Total)',
                    r'(?:fees included|with fees).*?\$(\d+(?:\.\d{2})?)'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        price = float(matches[0])
                        if price >= 50:  # Sanity check
                            return price
                
                # Fallback: find highest reasonable price (relaxed minimum)
                matches = re.findall(r'\$(\d{2,4}(?:\.\d{2})?)', content)
                if matches:
                    prices = [float(m) for m in matches]
                    valid_prices = [p for p in prices if 100 <= p <= 1000]
                    if valid_prices:
                        return max(valid_prices)
                
                # Last resort: any price over $50
                all_matches = re.findall(r'\$(\d+(?:\.\d{2})?)', content)
                if all_matches:
                    prices = [float(m) for m in all_matches]
                    reasonable_prices = [p for p in prices if 50 <= p <= 1000]
                    if reasonable_prices:
                        return max(reasonable_prices)
            
        except Exception as e:
            print(f"      Error extracting price: {str(e)[:50]}")
        
        return None
    
    def sort_tickets_by_section(self, tickets):
        """Sort tickets by section preference: Left, Center, Right"""
        def section_priority(ticket):
            section = ticket['section'].lower()
            
            # Left sections (higher priority)
            if any(term in section for term in ['left', 'section l', 'section 1', 'section 2', 'section 3']):
                return (1, ticket['price'])
            
            # Center sections (highest priority)
            elif any(term in section for term in ['center', 'centre', 'middle', 'section c', 'orchestra', 'floor']):
                return (0, ticket['price'])
            
            # Right sections
            elif any(term in section for term in ['right', 'section r', 'section 4', 'section 5', 'section 6']):
                return (2, ticket['price'])
            
            # Everything else (numbered sections, etc.)
            else:
                return (3, ticket['price'])
        
        return sorted(tickets, key=section_priority)
    
    def get_section_category(self, section):
        """Get section category for display"""
        section_lower = section.lower()
        
        if any(term in section_lower for term in ['left', 'section l', 'section 1', 'section 2', 'section 3']):
            return "Left"
        elif any(term in section_lower for term in ['center', 'centre', 'middle', 'section c', 'orchestra', 'floor']):
            return "Center"  
        elif any(term in section_lower for term in ['right', 'section r', 'section 4', 'section 5', 'section 6']):
            return "Right"
        else:
            return "Other"
    
    def format_tickets_html_premium(self, tickets, title):
        """Create enhanced HTML table sorted by section with checkout links"""
        if not tickets:
            return f"<h2>{title}</h2><p>No premium tickets found.</p>"
        
        sorted_tickets = self.sort_tickets_by_section(tickets)
        
        html = f"""
        <h2>{title}</h2>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #2c3e50; color: white;">
                <th>Location</th>
                <th>Section</th>
                <th>Price</th>
                <th>Qty</th>
                <th>Seller</th>
                <th>Verified</th>
                <th>Buy Now</th>
            </tr>
        """
        
        current_category = None
        for ticket in sorted_tickets:
            category = self.get_section_category(ticket['section'])
            
            # Add category separator
            if category != current_category:
                category_colors = {
                    "Left": "#3498db",    # Blue
                    "Center": "#27ae60",  # Green  
                    "Right": "#e74c3c",   # Red
                    "Other": "#95a5a6"    # Gray
                }
                color = category_colors.get(category, "#95a5a6")
                
                html += f"""
                <tr style="background-color: {color}; color: white; font-weight: bold;">
                    <td colspan="7" style="text-align: center;">{category} Sections</td>
                </tr>
                """
                current_category = category
            
            # Verification status and pricing
            if ticket.get('verified') and ticket.get('final_price'):
                if ticket.get('accurate', True):
                    verification_icon = "✅"
                    price_display = f"${ticket['final_price']:.0f}"
                else:
                    verification_icon = "⚠️"
                    seatpick_price = ticket.get('seatpick_price', ticket['price'])
                    price_display = f"${ticket['final_price']:.0f} (listed: ${seatpick_price:.0f})"
            else:
                verification_icon = "❓"
                price_display = f"${ticket['price']:.0f}"
            
            # Debug logging for price issues
            print(f"   DEBUG: {ticket['section']} - price={ticket.get('price')}, final_price={ticket.get('final_price')}, display='{price_display}'")
            
            # Quantity display
            quantity_info = ticket.get('quantity', 1)
            splits = ticket.get('splits', [])
            if splits:
                qty_display = f"{quantity_info} (can buy: {', '.join(map(str, splits))})"
            else:
                qty_display = str(quantity_info)
            
            # Buy button
            if ticket.get('checkout_link'):
                buy_button = f'<a href="{ticket["checkout_link"]}" target="_blank" style="background-color: #27ae60; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">Buy Now</a>'
            else:
                buy_button = f'<a href="{self.url}" target="_blank" style="background-color: #3498db; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">View on SeatPick</a>'
            
            html += f"""
            <tr>
                <td style="font-weight: bold; color: {category_colors.get(category, '#95a5a6')};">{category}</td>
                <td>{ticket['section']}</td>
                <td style="font-weight: bold;">{price_display}</td>
                <td style="text-align: center;">{qty_display}</td>
                <td>{ticket['seller']}</td>
                <td style="text-align: center;">{verification_icon}</td>
                <td>{buy_button}</td>
            </tr>
            """
        
        html += """
        </table>
        <br>
        <p style="font-size: 12px; color: #666;">
        <strong>Legend:</strong> ✅ = Verified price | ⚠️ = Price different than listed | ❓ = Not yet verified
        </p>
        """
        
        return html
    
    def generate_dynamic_subject(self, tickets, price_limit, alert_type=""):
        """Generate dynamic subject line with section breakdown"""
        if not tickets:
            return f"ATMOSPHERE RED ROCKS - No tickets found"
        
        # Group by section category
        section_groups = {}
        for ticket in tickets:
            category = self.get_section_category(ticket['section'])
            if category not in section_groups:
                section_groups[category] = []
            section_groups[category].append(ticket['price'])
        
        # Sort prices in each section
        for category in section_groups:
            section_groups[category].sort()
        
        # Build subject line parts
        subject_parts = []
        
        for category in ["Left", "Center", "Right", "Other"]:
            if category in section_groups:
                prices = section_groups[category]
                count = len(prices)
                
                if count == 1:
                    price_summary = f"${prices[0]}"
                elif count == 2:
                    price_summary = f"${prices[0]}, ${prices[1]}"
                else:
                    # Show count and 2-3 lowest prices
                    lowest_prices = ", ".join([f"${p}" for p in prices[:3]])
                    price_summary = f"{lowest_prices}"
                
                subject_parts.append(f"{category} ({count}, {price_summary})")
        
        section_text = " ".join(subject_parts)
        
        prefix = "🎯 TEST: " if alert_type == "test" else "🚨 " if alert_type == "urgent" else ""
        
        return f"{prefix}ATMOSPHERE RED ROCKS <${price_limit} - {section_text}"
    
    async def check_for_alerts(self):
        """Enhanced alert checking with your specific requirements"""
        tickets = await self.scrape_tickets_detailed()
        if not tickets:
            print("No premium tickets found")
            return
        
        # Filter tickets by price ranges
        test_tickets = [t for t in tickets if t['price'] < 400]  # Test notifications for <$400
        immediate_tickets = [t for t in tickets if t['price'] < 300]  # Immediate alerts for <$300
        
        print(f"📊 Found {len(tickets)} premium tickets")
        print(f"📧 Test range (<$400): {len(test_tickets)} tickets")  
        print(f"🚨 Alert range (<$300): {len(immediate_tickets)} tickets")
        
        # Always send test notification if we have premium tickets under $400
        if test_tickets:
            subject = self.generate_dynamic_subject(test_tickets, 400, "test")
            
            body_html = f"""
            <h1>🧪 TEST NOTIFICATION - Premium Tickets Found</h1>
            <p><strong>Found {len(test_tickets)} premium tickets under $400</strong></p>
            {self.format_tickets_html_premium(test_tickets, "Premium Tickets Under $400")}
            <p><a href="{self.url}">🎫 View all tickets on SeatPick</a></p>
            <p><em>This is a test notification - checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
            """
            
            body_text = f"TEST: Found {len(test_tickets)} premium tickets under $400 for Atmosphere Morrison. Prices: " + ", ".join([f"{t['section']} ${t['price']}" for t in test_tickets[:5]])
            
            self.send_notifications(subject, body_html, body_text)
            print(f"📧 Test notification sent for {len(test_tickets)} tickets under $400")
        
        # Send immediate alert if we have tickets under $300
        if immediate_tickets:
            subject = self.generate_dynamic_subject(immediate_tickets, 300, "urgent")
            
            body_html = f"""
            <h1>🚨 URGENT TICKET ALERT!</h1>
            <p><strong>Found {len(immediate_tickets)} premium tickets under $300</strong></p>
            {self.format_tickets_html_premium(immediate_tickets, "Premium Tickets Under $300 - ACT FAST!")}
            <p><a href="{self.url}">🎫 View all tickets on SeatPick</a></p>
            <p><em>Immediate alert - checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
            """
            
            body_text = f"URGENT: Found {len(immediate_tickets)} premium tickets under $300! Prices: " + ", ".join([f"{t['section']} ${t['price']}" for t in immediate_tickets[:5]])
            
            self.send_notifications(subject, body_html, body_text)
            print(f"🚨 URGENT alert sent for {len(immediate_tickets)} tickets under $300")
        
        if not test_tickets and not immediate_tickets:
            print("No premium tickets under $400 found")
    
    async def send_daily_summary(self):
        """Daily summary of all premium tickets under $400 with section sorting"""
        tickets = await self.scrape_tickets_detailed()
        if not tickets:
            print("No premium tickets found for daily summary")
            return
        
        summary_tickets = [t for t in tickets if t['price'] < 400]
        
        subject = self.generate_dynamic_subject(summary_tickets, 400, "") if summary_tickets else f"📊 Daily Premium Ticket Summary - {datetime.now().strftime('%Y-%m-%d')}"
        
        if summary_tickets:
            sorted_tickets = self.sort_tickets_by_section(summary_tickets)
            
            # Generate section breakdown
            section_breakdown = {}
            for ticket in summary_tickets:
                category = self.get_section_category(ticket['section'])
                if category not in section_breakdown:
                    section_breakdown[category] = []
                section_breakdown[category].append(ticket)
            
            body_html = f"""
            <h1>📊 Daily Premium Ticket Summary</h1>
            <p><strong>Found {len(summary_tickets)} premium tickets under $400</strong></p>
            
            <h3>📈 Section Breakdown</h3>
            <ul>
            """
            
            for category in ["Center", "Left", "Right", "Other"]:
                if category in section_breakdown:
                    tickets_in_cat = section_breakdown[category]
                    min_price = min(t['price'] for t in tickets_in_cat)
                    max_price = max(t['price'] for t in tickets_in_cat)
                    avg_price = sum(t['price'] for t in tickets_in_cat) // len(tickets_in_cat)
                    
                    body_html += f"""
                    <li><strong>{category}:</strong> {len(tickets_in_cat)} tickets (${min_price}-${max_price}, avg: ${avg_price})</li>
                    """
            
            body_html += f"""
            </ul>
            
            {self.format_tickets_html_premium(summary_tickets, "All Premium Tickets Under $400 (Sorted by Section)")}
            
            <h3>🏪 Seller Breakdown</h3>
            <ul>
            """
            
            # Seller breakdown
            sellers = {}
            for ticket in summary_tickets:
                seller = ticket['seller']
                if seller not in sellers:
                    sellers[seller] = []
                sellers[seller].append(ticket['price'])
            
            for seller, prices in sellers.items():
                body_html += f"<li><strong>{seller}:</strong> {len(prices)} tickets (${min(prices)}-${max(prices)})</li>"
            
            body_html += f"""
            </ul>
            
            <p><a href="{self.url}">🎫 View all tickets on SeatPick</a></p>
            <p><em>Summary generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
            """
        else:
            body_html = f"""
            <h1>📊 Daily Premium Ticket Summary</h1>
            <p>No premium tickets under $400 found today.</p>
            <p><a href="{self.url}">🎫 Check SeatPick for current listings</a></p>
            <p><em>Summary generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
            """
        
        # Create text summary
        if summary_tickets:
            body_text = f"Daily summary: {len(summary_tickets)} premium tickets under $400 available for Atmosphere Morrison. Best deals by section: "
            
            section_prices = {}
            for ticket in summary_tickets:
                category = self.get_section_category(ticket['section'])
                if category not in section_prices:
                    section_prices[category] = []
                section_prices[category].append(ticket['price'])
            
            section_summaries = []
            for category in ["Center", "Left", "Right", "Other"]:
                if category in section_prices:
                    min_price = min(section_prices[category])
                    section_summaries.append(f"{category}: ${min_price}")
            
            body_text += ", ".join(section_summaries)
        else:
            body_text = "Daily summary: No premium tickets under $400 found today for Atmosphere Morrison."
        
        self.send_notifications(subject, body_html, body_text)
        print(f"📧 Daily summary sent: {len(summary_tickets) if summary_tickets else 0} premium tickets")

async def main():
    """Main function to run the premium monitor"""
    monitor = PremiumSeatPickMonitor()
    
    if len(sys.argv) > 1 and sys.argv[1] == "daily":
        await monitor.send_daily_summary()
    else:
        await monitor.check_for_alerts()

if __name__ == "__main__":
    asyncio.run(main())