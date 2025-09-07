#!/usr/bin/env python3
import asyncio
import json
import re
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import time

class DetailedSeatPickScraper:
    def __init__(self):
        self.url = "https://seatpick.com/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/366607?quantity=2"
        self.tickets = []
        
    async def scrape_with_playwright(self):
        """Use Playwright to scrape ticket listings with seller information"""
        print(f"🎫 Scraping SeatPick with Playwright...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Set user agent to avoid bot detection
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            })
            
            try:
                print(f"📱 Loading page: {self.url}")
                await page.goto(self.url, wait_until='networkidle')
                
                # Wait for ticket listings to load
                print("⏳ Waiting for ticket listings...")
                await page.wait_for_timeout(5000)  # Give time for JS to render
                
                # Try to find and click any "load more" or "show all" buttons
                try:
                    load_more_selectors = [
                        'button:has-text("Load more")',
                        'button:has-text("Show all")',
                        'button:has-text("See all")',
                        '[data-testid*="load"]',
                        '.load-more',
                        '.show-all'
                    ]
                    
                    for selector in load_more_selectors:
                        try:
                            if await page.locator(selector).count() > 0:
                                print(f"🔄 Clicking load more button: {selector}")
                                await page.locator(selector).click()
                                await page.wait_for_timeout(2000)
                                break
                        except:
                            continue
                except:
                    pass
                
                # Get page content after JavaScript rendering
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Try multiple approaches to find ticket listings
                tickets_found = await self.extract_tickets_multiple_approaches(page, soup)
                
                if not tickets_found:
                    # Fallback: try to interact with filters/selectors to reveal tickets
                    await self.try_reveal_tickets(page)
                    content = await page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    tickets_found = await self.extract_tickets_multiple_approaches(page, soup)
                
                print(f"📊 Found {len(self.tickets)} ticket listings")
                
                # Verify a few ticket prices by following through to seller sites
                if self.tickets:
                    await self.verify_ticket_prices(page, self.tickets[:3])  # Verify first 3 tickets
                
            except Exception as e:
                print(f"❌ Error during scraping: {e}")
                # Take screenshot for debugging
                await page.screenshot(path='seatpick_debug.png')
                
            finally:
                await browser.close()
        
        return self.tickets
    
    async def extract_tickets_multiple_approaches(self, page, soup):
        """Try multiple approaches to extract ticket data"""
        tickets_found = False
        
        # Approach 1: Look for ticket listing containers
        selectors_to_try = [
            '[data-testid*="ticket"]',
            '[data-testid*="listing"]',
            '.ticket-listing',
            '.listing-item',
            '.ticket-item',
            '[class*="ticket"]',
            '[class*="listing"]',
            '[class*="price"]'
        ]
        
        for selector in selectors_to_try:
            try:
                elements = await page.locator(selector).all()
                if elements:
                    print(f"🎯 Found {len(elements)} elements with selector: {selector}")
                    for i, element in enumerate(elements[:10]):  # Limit to first 10
                        try:
                            text = await element.inner_text()
                            if '$' in text and len(text) > 10:  # Has price and substantial content
                                ticket_data = await self.parse_ticket_element(element, text, f"{selector}[{i}]")
                                if ticket_data:
                                    self.tickets.append(ticket_data)
                                    tickets_found = True
                        except Exception as e:
                            print(f"Error parsing element {i}: {e}")
                            continue
                    
                    if tickets_found:
                        break
                        
            except Exception as e:
                print(f"Error with selector {selector}: {e}")
                continue
        
        # Approach 2: Look for structured data in scripts
        if not tickets_found:
            tickets_found = await self.extract_from_scripts(page)
        
        # Approach 3: Parse HTML for price patterns
        if not tickets_found:
            tickets_found = self.extract_from_html_patterns(soup)
        
        return tickets_found
    
    async def parse_ticket_element(self, element, text, selector_info):
        """Parse individual ticket element to extract details"""
        try:
            # Extract price
            price_match = re.search(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)', text)
            if not price_match:
                return None
            
            price = int(re.sub(r'[,$.]', '', price_match.group(1)))
            
            # Extract section/seat info
            section = "Unknown Section"
            text_lower = text.lower()
            
            # Look for section patterns
            section_patterns = [
                r'section\s+(\w+(?:\s+\w+)?)',
                r'row\s+(\w+)',
                r'floor\s+(\w+)?',
                r'general\s+admission',
                r'ga\s+(\w+)?',
                r'(section\s+\w+)',
                r'(floor)',
                r'(balcony)',
                r'(orchestra)',
                r'(mezzanine)'
            ]
            
            for pattern in section_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    section = match.group(0).title()
                    break
            
            # Try to find seller information
            seller = "Unknown Seller"
            try:
                # Look for seller info in nearby elements or attributes
                parent = await element.locator('..').first
                parent_text = await parent.inner_text() if parent else ""
                
                # Common seller patterns
                seller_patterns = [
                    r'(stubhub|vivid\s*seats|ticketmaster|seatgeek|viagogo|gametime|tickpick)',
                    r'sold\s+by\s+([^\n]+)',
                    r'from\s+([^\n]+)',
                    r'via\s+([^\n]+)'
                ]
                
                combined_text = f"{text} {parent_text}".lower()
                for pattern in seller_patterns:
                    match = re.search(pattern, combined_text)
                    if match:
                        seller = match.group(1).strip().title()
                        break
                
                # Try to find seller from link or button
                try:
                    links = await element.locator('a').all()
                    for link in links:
                        href = await link.get_attribute('href')
                        if href and any(site in href.lower() for site in ['stubhub', 'vividseats', 'ticketmaster', 'seatgeek', 'viagogo']):
                            for site in ['stubhub', 'vividseats', 'ticketmaster', 'seatgeek', 'viagogo']:
                                if site in href.lower():
                                    seller = site.title()
                                    break
                            break
                except:
                    pass
                    
            except Exception as e:
                print(f"Error extracting seller info: {e}")
            
            return {
                'section': section,
                'price': price,
                'seller': seller,
                'raw_text': text.strip()[:200],  # Truncate for readability
                'selector_info': selector_info,
                'verified': False
            }
            
        except Exception as e:
            print(f"Error parsing ticket element: {e}")
            return None
    
    async def extract_from_scripts(self, page):
        """Extract ticket data from JavaScript/JSON in scripts"""
        try:
            scripts = await page.locator('script').all()
            
            for script in scripts:
                content = await script.inner_text()
                if not content:
                    continue
                
                # Look for ticket data in JSON
                if 'ticket' in content.lower() or 'listing' in content.lower():
                    # Try to extract JSON objects
                    json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
                    
                    for json_str in json_matches:
                        try:
                            data = json.loads(json_str)
                            if self.extract_tickets_from_json(data):
                                return True
                        except:
                            continue
            
        except Exception as e:
            print(f"Error extracting from scripts: {e}")
        
        return False
    
    def extract_tickets_from_json(self, data):
        """Extract tickets from JSON data"""
        found_tickets = False
        
        def search_json(obj, path=""):
            nonlocal found_tickets
            
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if 'price' in key.lower() and isinstance(value, (int, float, str)):
                        # Found potential price data
                        try:
                            price = int(re.sub(r'[^0-9]', '', str(value)))
                            if 10 <= price <= 2000:  # Reasonable ticket price range
                                ticket = {
                                    'section': 'From JSON Data',
                                    'price': price,
                                    'seller': 'Unknown',
                                    'raw_text': f'Found in JSON: {key} = {value}',
                                    'selector_info': f'json:{path}.{key}',
                                    'verified': False
                                }
                                self.tickets.append(ticket)
                                found_tickets = True
                        except:
                            pass
                    
                    search_json(value, f"{path}.{key}" if path else key)
                    
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    search_json(item, f"{path}[{i}]")
        
        search_json(data)
        return found_tickets
    
    def extract_from_html_patterns(self, soup):
        """Extract tickets from HTML using pattern matching"""
        try:
            # Look for elements containing price patterns
            price_elements = soup.find_all(text=re.compile(r'\$\d{2,4}'))
            
            for price_text in price_elements:
                try:
                    price_match = re.search(r'\$(\d+)', price_text)
                    if not price_match:
                        continue
                    
                    price = int(price_match.group(1))
                    if price < 10 or price > 2000:  # Filter unreasonable prices
                        continue
                    
                    # Get context from parent elements
                    parent = price_text.parent
                    context_text = ""
                    
                    for _ in range(3):  # Go up 3 levels to get context
                        if parent:
                            context_text += parent.get_text(strip=True) + " "
                            parent = parent.parent
                        else:
                            break
                    
                    ticket = {
                        'section': self.extract_section_from_text(context_text),
                        'price': price,
                        'seller': self.extract_seller_from_text(context_text),
                        'raw_text': context_text[:200],
                        'selector_info': 'html_pattern',
                        'verified': False
                    }
                    
                    self.tickets.append(ticket)
                    
                except Exception as e:
                    print(f"Error processing price element: {e}")
                    continue
            
            return len(self.tickets) > 0
            
        except Exception as e:
            print(f"Error extracting from HTML patterns: {e}")
            return False
    
    def extract_section_from_text(self, text):
        """Extract section info from text"""
        text_lower = text.lower()
        
        section_patterns = [
            r'section\s+(\w+(?:\s+\w+)?)',
            r'row\s+(\w+)',
            r'(general\s+admission)',
            r'(floor)',
            r'(ga)',
            r'(balcony)',
            r'(orchestra)',
            r'(mezzanine)'
        ]
        
        for pattern in section_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1 if len(match.groups()) > 0 else 0).title()
        
        return "Unknown Section"
    
    def extract_seller_from_text(self, text):
        """Extract seller info from text"""
        text_lower = text.lower()
        
        sellers = ['stubhub', 'vividseats', 'vivid seats', 'ticketmaster', 'seatgeek', 'viagogo', 'gametime', 'tickpick']
        
        for seller in sellers:
            if seller in text_lower:
                return seller.replace(' ', '').title()
        
        return "Unknown Seller"
    
    async def try_reveal_tickets(self, page):
        """Try various interactions to reveal hidden tickets"""
        try:
            # Try clicking quantity selectors
            quantity_selectors = ['select[name*="quantity"]', '[data-testid*="quantity"]', 'select']
            for selector in quantity_selectors:
                try:
                    if await page.locator(selector).count() > 0:
                        await page.locator(selector).select_option('2')
                        await page.wait_for_timeout(2000)
                        break
                except:
                    continue
            
            # Try clicking filter buttons
            filter_selectors = [
                'button:has-text("Filter")',
                'button:has-text("Sort")',
                'button:has-text("Price")',
                '[data-testid*="filter"]',
                '[data-testid*="sort"]'
            ]
            
            for selector in filter_selectors:
                try:
                    if await page.locator(selector).count() > 0:
                        await page.locator(selector).click()
                        await page.wait_for_timeout(1000)
                        break
                except:
                    continue
            
        except Exception as e:
            print(f"Error trying to reveal tickets: {e}")
    
    async def verify_ticket_prices(self, page, tickets_to_verify):
        """Verify ticket prices by following through to seller sites"""
        print(f"🔍 Verifying prices for {len(tickets_to_verify)} tickets...")
        
        for i, ticket in enumerate(tickets_to_verify):
            try:
                print(f"  Verifying ticket {i+1}: {ticket['section']} - ${ticket['price']} from {ticket['seller']}")
                
                # Look for links that might lead to the ticket purchase
                purchase_links = await page.locator('a').all()
                
                for link in purchase_links:
                    try:
                        text = await link.inner_text()
                        href = await link.get_attribute('href')
                        
                        if href and ('buy' in text.lower() or 'purchase' in text.lower() or ticket['seller'].lower() in href.lower()):
                            print(f"    Following link: {href[:100]}...")
                            
                            # Open in new tab to verify
                            new_page = await page.context.new_page()
                            
                            try:
                                await new_page.goto(href, wait_until='networkidle', timeout=10000)
                                await new_page.wait_for_timeout(3000)
                                
                                # Look for price on the checkout page
                                checkout_content = await new_page.content()
                                price_matches = re.findall(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)', checkout_content)
                                
                                if price_matches:
                                    checkout_prices = [int(re.sub(r'[,$.]', '', p)) for p in price_matches]
                                    closest_price = min(checkout_prices, key=lambda x: abs(x - ticket['price']))
                                    
                                    price_diff = abs(closest_price - ticket['price'])
                                    if price_diff <= 5:  # Within $5 is considered accurate
                                        ticket['verified'] = True
                                        ticket['verified_price'] = closest_price
                                        print(f"    ✅ Price verified: ${closest_price}")
                                    else:
                                        ticket['verified'] = False
                                        ticket['verified_price'] = closest_price
                                        print(f"    ⚠️  Price mismatch: Listed ${ticket['price']}, actual ${closest_price}")
                                
                            except Exception as e:
                                print(f"    ❌ Error verifying: {e}")
                            
                            finally:
                                await new_page.close()
                            
                            break  # Found a purchase link, don't try others
                            
                    except Exception as e:
                        continue
                
                # Rate limiting - don't hammer seller sites
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"  Error verifying ticket {i+1}: {e}")
    
    def filter_premium_tickets(self, max_price=400):
        """Filter for non-GA tickets under specified price"""
        premium_tickets = []
        
        for ticket in self.tickets:
            section = ticket['section'].lower()
            price = ticket['price']
            
            # Skip General Admission, Floor GA, Section GA
            if any(term in section for term in ['general admission', 'floor ga', 'section ga', 'ga']):
                continue
            
            if price <= max_price:
                premium_tickets.append(ticket)
        
        return premium_tickets

async def main():
    """Main function to test the detailed scraper"""
    scraper = DetailedSeatPickScraper()
    
    print("🎭 Starting detailed SeatPick scraping...")
    tickets = await scraper.scrape_with_playwright()
    
    print(f"\n📈 RESULTS: Found {len(tickets)} total tickets")
    
    if tickets:
        print("\n🎫 All tickets:")
        for i, ticket in enumerate(tickets, 1):
            verification_status = "✅ Verified" if ticket.get('verified') else "❓ Unverified"
            verified_price = f" (actual: ${ticket.get('verified_price')})" if ticket.get('verified_price') else ""
            print(f"  {i}. {ticket['section']} - ${ticket['price']}{verified_price} from {ticket['seller']} [{verification_status}]")
        
        premium_tickets = scraper.filter_premium_tickets(400)
        print(f"\n🎯 Premium tickets (non-GA, under $400): {len(premium_tickets)}")
        
        for i, ticket in enumerate(premium_tickets, 1):
            verification_status = "✅ Verified" if ticket.get('verified') else "❓ Unverified"
            verified_price = f" (actual: ${ticket.get('verified_price')})" if ticket.get('verified_price') else ""
            print(f"  {i}. {ticket['section']} - ${ticket['price']}{verified_price} from {ticket['seller']} [{verification_status}]")
    
    else:
        print("❌ No tickets found")

if __name__ == "__main__":
    asyncio.run(main())