#!/usr/bin/env python3
import asyncio
import os
import sys
from datetime import datetime
import re
import aiohttp
from rebrowser_playwright.async_api import async_playwright
from camoufox.async_api import AsyncCamoufox
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Import notification functionality from original monitor
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from monitor_tickets import SeatPickMonitor

class PremiumSeatPickMonitor(SeatPickMonitor):
    def __init__(self):
        super().__init__()
        self.event_id = "366607"
        self.base_url = "https://seatpick.com"
        self.api_url = f"https://seatpick.com/api/proxy/4/events/{self.event_id}/listings"
    
    def sanitize_checkout_url(self, url):
        """Remove tracking parameters from checkout URLs while keeping essential params"""
        if not url:
            return url
        
        # For VividSeats URLs (through pxf.io tracking)
        if 'vivid-seats.pxf.io' in url or 'vividseats.pxf.io' in url:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if 'u' in params:
                actual_url = params['u'][0]
                parsed_actual = urlparse(actual_url)
                actual_params = parse_qs(parsed_actual.query)
                clean_params = {}
                if 'showDetails' in actual_params:
                    clean_params['showDetails'] = actual_params['showDetails'][0]
                if 'qty' in actual_params:
                    clean_params['qty'] = actual_params['qty'][0]
                
                return urlunparse((
                    parsed_actual.scheme,
                    parsed_actual.netloc,
                    parsed_actual.path,
                    '',
                    urlencode(clean_params),
                    ''
                ))
        
        # For Viagogo URLs (through prf.hn tracking)
        elif 'viagogo.prf.hn' in url:
            if 'destination:' in url:
                dest_start = url.find('destination:') + len('destination:')
                actual_url = url[dest_start:]
                import urllib.parse
                actual_url = urllib.parse.unquote(actual_url)
                return actual_url
        
        # For TicketNetwork URLs (through lusg.net tracking)
        elif 'ticketnetwork.lusg.net' in url:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if 'u' in params:
                actual_url = params['u'][0]
                parsed_actual = urlparse(actual_url)
                actual_params = parse_qs(parsed_actual.query)
                clean_params = {}
                if 'ticketGroupId' in actual_params:
                    clean_params['ticketGroupId'] = actual_params['ticketGroupId'][0]
                
                return urlunparse((
                    parsed_actual.scheme,
                    parsed_actual.netloc,
                    parsed_actual.path,
                    '',
                    urlencode(clean_params),
                    ''
                ))
        
        # For direct URLs, remove common tracking parameters
        else:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            tracking_params = [
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                'fbclid', 'gclid', 'msclkid', 'ref', 'referrer', 'source',
                'camref', 'pubref', 'clickid', 'affid', 'affiliate'
            ]
            
            clean_params = {k: v[0] for k, v in params.items() 
                           if k.lower() not in tracking_params}
            
            return urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                '',
                urlencode(clean_params) if clean_params else '',
                ''
            ))
        
        return url
    
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
                
                # STRICT REQUIREMENT: Must have exactly 2 tickets available together (side by side)
                quantity = listing.get('quantity', 1)
                splits = listing.get('splits', [])
                
                # Only accept if:
                # 1. Quantity is at least 2 (can buy 2+ tickets)
                # 2. Either no splits specified OR splits explicitly allows 2
                # 3. We specifically want 2 tickets, not 1, not 3+ (unless they allow splits of 2)
                has_two_available = quantity >= 2
                
                # Check if splits allow exactly 2 (or if no splits specified, assume ok)
                if splits:
                    # If splits are specified, 2 must be in the list
                    allows_exactly_two = 2 in splits
                else:
                    # No splits specified means any quantity up to max is allowed
                    allows_exactly_two = True
                
                can_buy_two_together = has_two_available and allows_exactly_two
                
                if not can_buy_two_together:
                    print(f"   ❌ Skipping single ticket: {listing.get('section')} ${listing.get('price')} - qty:{quantity}, splits:{splits}")
                    continue
                
                # Extract details
                section = listing.get('section')
                row = listing.get('row', 'General')
                seatpick_price = listing.get('price', 0)
                seller = listing.get('seller', '')
                deeplink = listing.get('deepLink', '')
                
                if not deeplink:
                    # Skip if no checkout link
                    filtered.append({
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
                
                print(f"   ✅ {section} ${seatpick_price} via {seller} (qty: {quantity})")
                filtered.append({
                    'section': section,
                    'row': row,
                    'price': seatpick_price,
                    'seller': seller,
                    'deeplink': deeplink,  # Keep original for verification
                    'quantity': quantity,
                    'splits': splits
                })
            
            print(f"📊 Found {len(filtered)} tickets in premium sections")
            
            # Verify prices with fees for tickets under $500 (to catch misleading pricing)
            verified_tickets = []
            if filtered:
                print("🔍 Verifying final prices with all fees...")
                verified_tickets = await self.verify_final_prices(filtered[:20])  # Limit to avoid rate limiting
            
            # DISABLED: SeatGeek integration
            # try:
            #     print("🦊 Checking SeatGeek for Reserved Left/Center sections...")
            #     seatgeek_tickets = await self.scrape_seatgeek_tickets()
            #     if seatgeek_tickets:
            #         verified_tickets.extend(seatgeek_tickets)
            #         print(f"🎫 Added {len(seatgeek_tickets)} SeatGeek tickets to results")
            #     else:
            #         print("🦊 SeatGeek: No target section tickets found")
            # except Exception as e:
            #     print(f"🦊 SeatGeek integration error: {e}")
            
            return verified_tickets
            
        except Exception as e:
            print(f"❌ Error in scrape_tickets_detailed: {e}")
            return []

        # Your desired sections (NO GA)
        self.desired_sections = [
            "Center",
            "Front Center", 
            "Front Left",
            "Front Right",
            "Left",
            "Reserved Seating",
            "Right",
            # SeatGeek specific sections
            "Reserved Left",
            "Reserved Center"
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
                
                # STRICT REQUIREMENT: Must have exactly 2 tickets available together (side by side)
                quantity = listing.get('quantity', 1)
                splits = listing.get('splits', [])
                
                # Only accept if:
                # 1. Quantity is at least 2 (can buy 2+ tickets)
                # 2. Either no splits specified OR splits explicitly allows 2
                # 3. We specifically want 2 tickets, not 1, not 3+ (unless they allow splits of 2)
                has_two_available = quantity >= 2
                
                # Check if splits allow exactly 2 (or if no splits specified, assume ok)
                if splits:
                    # If splits are specified, 2 must be in the list
                    allows_exactly_two = 2 in splits
                else:
                    # No splits specified means any quantity up to max is allowed
                    allows_exactly_two = True
                
                can_buy_two_together = has_two_available and allows_exactly_two
                
                if not can_buy_two_together:
                    print(f"   ❌ Skipping single ticket: {listing.get('section')} ${listing.get('price')} - qty:{quantity}, splits:{splits}")
                    continue
                
                # Additional check: reject if quantity is 1 (single ticket only)
                if quantity < 2:
                    print(f"   ❌ Skipping single ticket only: {listing.get('section')} ${listing.get('price')}")
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
            
            # DISABLED: SeatGeek integration
            # try:
            #     print("🦊 Checking SeatGeek for Reserved Left/Center sections...")
            #     seatgeek_tickets = await self.scrape_seatgeek_tickets()
            #     if seatgeek_tickets:
            #         verified_tickets.extend(seatgeek_tickets)
            #         print(f"🎫 Added {len(seatgeek_tickets)} SeatGeek tickets to results")
            #     else:
            #         print("🦊 SeatGeek: No target section tickets found")
            # except Exception as e:
            #     print(f"🦊 SeatGeek integration error: {e}")
            
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
                    # Use sanitized URL for cleaner navigation and validation
                    clean_url = self.sanitize_checkout_url(deeplink)
                    page = await context.new_page()
                    print(f"   🔍 Navigating to {seller} page for verification...")
                    print(f"     Using clean URL: {clean_url[:80]}...")
                    await page.goto(clean_url, wait_until='domcontentloaded', timeout=20000)
                    await page.wait_for_timeout(3000)
                    
                    # Extract FINAL price with fees
                    final_price = await self.extract_final_price(page, seller)
                    
                    print(f"   📊 Price extraction result for {section} via {seller}:")
                    print(f"      SeatPick shows: ${seatpick_price}")
                    print(f"      Extracted price: ${final_price}")
                    
                    # Reject extracted price if it's suspiciously lower than SeatPick price
                    # For premium tickets, final price should NEVER be less than 80% of SeatPick price
                    if final_price and final_price < (seatpick_price * 0.8):
                        print(f"   🚨 SAFETY REJECTION: Final price ${final_price} vs SeatPick ${seatpick_price} - difference {((seatpick_price - final_price) / seatpick_price * 100):.1f}% (extraction error)")
                        final_price = None
                    
                    if final_price:
                        price_diff = final_price - seatpick_price
                        accurate = abs(price_diff) <= 10
                        
                        # Additional safety check: Never use extracted price if it's way too low
                        filter_price = final_price
                        if seatpick_price > 400 and final_price < 300:
                            print(f"   🛡️  SAFETY OVERRIDE: Using SeatPick ${seatpick_price} instead of extracted ${final_price} (suspicious price)")
                            filter_price = seatpick_price
                        
                        print(f"   ✅ VERIFIED: {section} ${filter_price} ({'accurate' if accurate else 'price different'}) - diff: ${price_diff:+.2f}")
                            
                        verified.append({
                            'section': section,
                            'row': row,
                            'price': filter_price,  # Use safe price for filtering
                            'seller': seller,
                            'verified': True,
                            'final_price': final_price,
                            'seatpick_price': seatpick_price,
                            'price_diff': price_diff,
                            'checkout_link': clean_url,  # Use the clean URL we already sanitized
                            'accurate': accurate
                        })
                    else:
                        print(f"   ❓ UNVERIFIED: {section} ${seatpick_price} via {seller} - using SeatPick price")
                        # Fallback to SeatPick price if can't verify
                        verified.append({
                            'section': section,
                            'row': row,
                            'price': seatpick_price,
                            'seller': seller,
                            'verified': False,
                            'final_price': seatpick_price,
                            'price_diff': 0,
                            'checkout_link': clean_url,  # Use the clean URL
                            'accurate': True
                        })
                    
                    await page.close()
                    
                except Exception as e:
                    print(f"   ❌ ERROR verifying {section} via {seller}: {str(e)[:100]}")
                    print(f"      Adding as unverified ticket with SeatPick price ${seatpick_price}")
                    # Add unverified listing on error
                    verified.append({
                        'section': section,
                        'row': row,
                        'price': seatpick_price,
                        'seller': seller,
                        'verified': False,
                        'final_price': seatpick_price,
                        'price_diff': 0,
                        'checkout_link': self.sanitize_checkout_url(deeplink),  # Sanitize on error
                        'accurate': True
                    })
                    try:
                        await page.close()
                    except:
                        pass
                
                await asyncio.sleep(1)  # Rate limiting
            
            await browser.close()
        
        return verified
    
    async def scrape_seatgeek_tickets(self):
        """Scrape SeatGeek using Camoufox for Reserved Left/Center sections"""
        verified_tickets = []
        
        try:
            event_url = "https://seatgeek.com/atmosphere-tickets/morrison-colorado-red-rocks-amphitheatre-2025-09-19-6-pm/concert/17445672?quantity=2"
            
            # Use Camoufox which worked better than rebrowser-playwright
            async with AsyncCamoufox() as browser:
                
                page = await browser.new_page()
                api_data = None
                
                # Set up response interception to capture API data
                async def handle_response(response):
                    nonlocal api_data
                    url = response.url
                    
                    if 'event_listings_v2' in url:
                        print(f"🎯 SeatGeek API call: {response.status} - {url[:80]}...")
                        
                        if response.status == 200:
                            try:
                                data = await response.json()
                                api_data = data
                                print("✅ SeatGeek: API data captured successfully")
                            except:
                                pass  # Ignore JSON parse errors
                        elif response.status == 403:
                            try:
                                # Check if this is the interactive DataDome challenge
                                text = await response.text()
                                if "'rt':'i'" in text and 'captcha-delivery.com' in text:
                                    print("🛡️  SeatGeek: Got interactive DataDome challenge - solving...")
                                    # This is the solvable interactive challenge
                                    # Wait for the challenge to potentially resolve
                                    await page.wait_for_timeout(3000)
                                    
                                    # Let the challenge resolve naturally without reloading
                                    print("⏳ Letting interactive challenge resolve naturally...")
                                else:
                                    print("❌ SeatGeek: Hard blocked by DataDome")
                            except:
                                pass
                
                page.on('response', handle_response)
                
                print("🦊 SeatGeek: Loading event page...")
                try:
                    # Set viewport like successful tests
                    await page.set_viewport_size({"width": 1920, "height": 1080})
                    
                    # Navigate with longer timeout for challenge resolution
                    response = await page.goto(event_url, timeout=60000)
                    print(f"📊 SeatGeek response: {response.status if response else 'None'}")
                    
                    # Human-like interaction immediately after load
                    try:
                        await page.mouse.move(200, 200)
                        await asyncio.sleep(1)
                        await page.mouse.move(300, 300)
                        await asyncio.sleep(0.5)
                    except:
                        pass
                    
                    # Wait for page to fully settle and challenges to resolve
                    print("🛡️  Waiting for challenges to resolve...")
                    await asyncio.sleep(15)  # Give time for interactive challenge resolution
                    
                    # Try additional interactions to trigger API calls
                    try:
                        await page.mouse.wheel(0, 300)
                        await asyncio.sleep(2)
                        
                        # Try clicking interactive elements
                        buttons = await page.query_selector_all('button, [role="button"]')
                        for i, button in enumerate(buttons[:2]):
                            try:
                                await button.click()
                                await asyncio.sleep(1)
                            except:
                                pass
                    except:
                        pass
                    
                    # Final wait for any triggered API calls
                    await asyncio.sleep(5)
                    
                    # Check if we got data
                    if api_data and isinstance(api_data, dict):
                        print("🎯 SeatGeek: Processing captured API data...")
                        tickets = self.parse_seatgeek_data(api_data)
                        return tickets
                    else:
                        print("❌ SeatGeek: No API data captured")
                        return []
                        
                except Exception as e:
                    if "timeout" in str(e).lower():
                        print("⚠️  SeatGeek: Page timeout (likely DataDome challenge)")
                        # Still check if we got API data during the load
                        if api_data:
                            tickets = self.parse_seatgeek_data(api_data)
                            return tickets
                    else:
                        print(f"❌ SeatGeek navigation error: {e}")
                    return []
                    
        except Exception as e:
            print(f"❌ SeatGeek scraping error: {e}")
            return []
    
    def parse_seatgeek_data(self, api_data):
        """Parse SeatGeek API data for Reserved Left/Center sections"""
        verified_tickets = []
        target_sections = ["Reserved Left", "Reserved Center"]
        
        try:
            # Find listings in the API response
            listings = []
            if 'listings' in api_data:
                listings = api_data['listings']
            elif 'data' in api_data and isinstance(api_data['data'], list):
                listings = api_data['data']
            elif isinstance(api_data, list):
                listings = api_data
                
            print(f"🎫 SeatGeek: Found {len(listings)} total listings")
            
            for listing in listings:
                if not isinstance(listing, dict):
                    continue
                    
                # Extract section information
                section_name = ""
                for key in ['section', 'section_name', 'zone', 'area']:
                    if key in listing and listing[key]:
                        section_name = str(listing[key])
                        break
                
                # Only include Reserved Left and Reserved Center
                if not any(target in section_name for target in target_sections):
                    continue
                
                # Extract ticket details
                quantity = listing.get('quantity', 1)
                if quantity < 2:
                    continue  # Need at least 2 tickets together
                
                price = listing.get('price')
                if not price:
                    price_data = listing.get('price_data', {})
                    price = price_data.get('total') or price_data.get('amount')
                
                if not price:
                    continue
                    
                # Convert price to float
                try:
                    if isinstance(price, str):
                        price = float(re.sub(r'[^\d.]', '', price))
                    else:
                        price = float(price)
                except:
                    continue
                
                # Extract row info
                row = listing.get('row', 'General')
                if isinstance(row, dict):
                    row = row.get('name', 'General')
                
                # Create verified ticket entry
                verified_ticket = {
                    'section': section_name,
                    'row': str(row),
                    'price': price,
                    'seller': 'SeatGeek',
                    'verified': True,  # API data is considered verified
                    'final_price': price,
                    'seatpick_price': price,
                    'price_diff': 0,
                    'checkout_link': f"https://seatgeek.com/checkout?listing_id={listing.get('id', '')}&quantity=2",
                    'accurate': True
                }
                
                verified_tickets.append(verified_ticket)
                print(f"   ✅ SeatGeek: {section_name} Row {row} - ${price}")
                
            print(f"🎯 SeatGeek: Found {len(verified_tickets)} target section tickets")
            return verified_tickets
            
        except Exception as e:
            print(f"❌ Error parsing SeatGeek data: {e}")
            return []
    
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
                print(f"      Extracting from Viagogo/Events365 page...")
                # Debug: Show a sample of the page content to understand what we're parsing
                if len(content) > 500:
                    print(f"      DEBUG: Viagogo page sample: {content[200:500]}...")
                
                # Much more conservative Viagogo patterns - only look for clear checkout totals
                patterns = [
                    # Critical patterns for Viagogo's "1 x US$ 396" format
                    r'1\s*x\s*US\$\s*(\d{3,4})',  # Matches "1 x US$ 396"
                    r'2\s*x\s*US\$\s*(\d{3,4})',  # Matches "2 x US$ 396"
                    r'(\d+)\s*x\s*US\$\s*(\d{3,4})',  # Matches "N x US$ 396"
                    r'US\$\s*(\d{3,4}(?:\.\d{2})?)',  # Generic US dollar amounts
                    # Original patterns for other checkout formats
                    r'(?:Order Total|ORDER TOTAL|Grand Total|GRAND TOTAL)[\s\:]*\$(\d{3,4}(?:\.\d{2})?)',
                    r'(?:Total Cost|TOTAL COST|Total Price|TOTAL PRICE)[\s\:]*\$(\d{3,4}(?:\.\d{2})?)',
                    r'(?:You Pay|You pay|YOU PAY)[\s\:]*\$(\d{3,4}(?:\.\d{2})?)',
                    r'(?:Amount Due|AMOUNT DUE|Final Amount|FINAL AMOUNT)[\s\:]*\$(\d{3,4}(?:\.\d{2})?)',
                    # Additional pattern for order summary
                    r'Order summary[\s\S]*?US\$\s*(\d{3,4})'
                ]
                
                for i, pattern in enumerate(patterns):
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        for match in matches:
                            # Handle both single group and multi-group patterns
                            if isinstance(match, tuple):
                                # For patterns like "N x US$ 396", take the last group (price)
                                price_str = match[-1] if match[-1] else match[0]
                            else:
                                price_str = match
                            
                            try:
                                price = float(price_str)
                                print(f"      Viagogo pattern {i+1} found: ${price}")
                                # Accept prices from $300-$1000 for Viagogo (they add ~35% fees)
                                if 300 <= price <= 1000:
                                    return price
                                else:
                                    print(f"      Rejecting Viagogo price ${price} - outside expected range")
                            except (ValueError, TypeError):
                                continue
                
                # NO fallback patterns - if we can't find a clear total, don't guess
                print(f"      No reliable Viagogo checkout total found - using SeatPick price")
                return None
            
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
        <p style="color: #2c3e50; font-weight: bold;">💺 All prices shown are per ticket. You will be purchasing 2 tickets together (side by side).</p>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <tr style="background-color: #2c3e50; color: white;">
                <th>Location</th>
                <th>Section</th>
                <th>Price/Ticket</th>
                <th>Total (2 tix)</th>
                <th>Seller</th>
                <th>Verified</th>
                <th>Buy 2 Tickets</th>
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
                    price_per_ticket = ticket['final_price']
                    price_display = f"${price_per_ticket:.0f}"
                    total_display = f"${price_per_ticket * 2:.0f}"
                else:
                    verification_icon = "⚠️"
                    seatpick_price = ticket.get('seatpick_price', ticket['price'])
                    price_per_ticket = ticket['final_price']
                    price_display = f"${price_per_ticket:.0f}"
                    total_display = f"${price_per_ticket * 2:.0f}"
            else:
                verification_icon = "❓"
                price_per_ticket = ticket['price']
                price_display = f"${price_per_ticket:.0f}"
                total_display = f"${price_per_ticket * 2:.0f}"
            
            # Debug logging for price issues
            print(f"   DEBUG: {ticket['section']} - price={ticket.get('price')}, final_price={ticket.get('final_price')}, per_ticket={price_per_ticket}, total_for_2={price_per_ticket * 2}")
            
            # Buy button - updated text to be clear about buying 2 tickets
            if ticket.get('checkout_link'):
                buy_button = f'<a href="{ticket["checkout_link"]}" target="_blank" style="background-color: #27ae60; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">Buy 2 Tickets</a>'
            else:
                buy_button = f'<a href="{self.url}" target="_blank" style="background-color: #3498db; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">View on SeatPick</a>'
            
            html += f"""
            <tr>
                <td style="font-weight: bold; color: {category_colors.get(category, '#95a5a6')};">{category}</td>
                <td>{ticket['section']}</td>
                <td style="font-weight: bold;">{price_display}</td>
                <td style="font-weight: bold; color: #e74c3c;">{total_display}</td>
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
        
        # Collect test tickets for manual testing (won't auto-send)
        test_tickets = []
        for t in tickets:
            # Must be verified to be included
            if not t.get('verified'):
                continue
                
            # Use final verified price for filtering
            final_price = t.get('final_price', t['price'])
            
            if final_price < 400:
                test_tickets.append(t)
                print(f"   ✅ Found test-range ticket: {t['section']} final=${final_price} via {t['seller']}")
            else:
                print(f"   🚫 Verified but too expensive: {t['section']} final=${final_price} via {t['seller']}")
        
        # STRICT urgent alerts - ONLY verified prices under $300
        immediate_tickets = []
        for t in tickets:
            # Must be verified
            if not t.get('verified'):
                continue
                
            # Use final verified price
            final_price = t.get('final_price', t['price'])
            
            if final_price < 300:
                immediate_tickets.append(t)
                print(f"   🚨 Including verified urgent alert: {t['section']} final=${final_price} via {t['seller']}")
            elif final_price < 400:
                print(f"   📊 Verified but not urgent: {t['section']} final=${final_price} via {t['seller']}")
        
        print(f"📊 Found {len(tickets)} premium tickets")
        print(f"📧 Test range (<$400): {len(test_tickets)} tickets")
        print(f"🚨 Alert range (<$300): {len(immediate_tickets)} tickets")
        
        # TEST NOTIFICATIONS COMPLETELY DISABLED
        # Test notifications will never be sent automatically
        print(f"ℹ️  Test notifications are disabled - found {len(test_tickets)} tickets in test range but not sending notifications")
        
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
        
        if not immediate_tickets:
            print("No urgent alerts sent (no tickets under $300)")
    
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
    """Main function to run the premium monitor
    
    Usage:
        python3 premium_monitor.py          # Normal run (only sends urgent alerts <$300)
        python3 premium_monitor.py daily    # Daily summary
    """
    monitor = PremiumSeatPickMonitor()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "daily":
            await monitor.send_daily_summary()
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Usage: python3 premium_monitor.py [daily]")
            print("Note: Test notifications are permanently disabled")
    else:
        await monitor.check_for_alerts()

if __name__ == "__main__":
    asyncio.run(main())