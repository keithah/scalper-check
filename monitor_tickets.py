#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import sys
from datetime import datetime, timedelta
import re
try:
    from simplepush import send as simplepush_send
except ImportError:
    simplepush_send = None
    print("Warning: simplepush not installed - push notifications will be skipped")

class SeatPickMonitor:
    def __init__(self):
        self.url = "https://seatpick.com/atmosphere-morrison-red-rocks-amphitheatre-19-09-2025-tickets/event/366607?quantity=2"
        
        # Email settings (legacy SMTP)
        self.email_user = os.environ.get('EMAIL_USER')
        self.email_pass = os.environ.get('EMAIL_PASS')
        self.email_to = os.environ.get('EMAIL_TO')
        self.smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        
        # MailerSend settings
        self.mailersend_api_key = os.environ.get('MAILERSEND_API_KEY')
        self.mailersend_from_email = os.environ.get('MAILERSEND_FROM_EMAIL', 'notifications@ferry-notifier.app')
        self.mailersend_from_name = os.environ.get('MAILERSEND_FROM_NAME', 'SeatPick Monitor')
        
        # SimplePush settings
        self.simplepush_key = os.environ.get('SIMPLEPUSH_KEY')
        
        # Choose notification method preference
        self.use_mailersend = bool(self.mailersend_api_key and len(self.mailersend_api_key) > 20)
        self.use_simplepush = bool(self.simplepush_key and simplepush_send)
        
    def scrape_tickets(self):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            response = requests.get(self.url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            tickets = []
            
            # Find ticket listings - adapt selectors based on actual HTML structure
            ticket_sections = soup.find_all('div', class_=lambda x: x and 'listing' in x.lower() if x else False)
            if not ticket_sections:
                # Fallback: look for any div containing price information
                ticket_sections = soup.find_all('div', text=re.compile(r'\$\d+'))
            
            for section in ticket_sections:
                try:
                    # Extract section name
                    section_name = None
                    section_text = section.get_text(strip=True)
                    
                    # Look for section names in the text
                    if any(term in section_text.lower() for term in ['section', 'row', 'ga', 'general admission', 'floor']):
                        section_name = section_text
                    
                    # Extract price
                    price_match = re.search(r'\$(\d+)', section_text)
                    if price_match:
                        price = int(price_match.group(1))
                        
                        tickets.append({
                            'section': section_name or 'Unknown Section',
                            'price': price,
                            'raw_text': section_text
                        })
                except Exception as e:
                    print(f"Error parsing ticket section: {e}")
                    continue
            
            return tickets
            
        except Exception as e:
            print(f"Error scraping tickets: {e}")
            return []
    
    def filter_premium_tickets(self, tickets):
        """Filter for non-GA tickets under $300"""
        premium_tickets = []
        
        for ticket in tickets:
            section = ticket['section'].lower()
            price = ticket['price']
            
            # Skip General Admission, Floor GA, Section GA
            if any(term in section for term in ['general admission', 'floor ga', 'section ga', 'ga']):
                continue
                
            if price < 400:
                premium_tickets.append(ticket)
        
        return premium_tickets
    
    def filter_summary_tickets(self, tickets):
        """Filter for all tickets under $400"""
        return [ticket for ticket in tickets if ticket['price'] < 400]
    
    def send_mailersend_email(self, subject, body, is_html=False):
        """Send email via MailerSend API"""
        try:
            import requests
            
            url = "https://api.mailersend.com/v1/email"
            
            headers = {
                "Authorization": f"Bearer {self.mailersend_api_key}",
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            }
            
            email_data = {
                "from": {
                    "email": self.mailersend_from_email,
                    "name": self.mailersend_from_name
                },
                "to": [
                    {
                        "email": self.email_to
                    }
                ],
                "subject": subject,
            }
            
            if is_html:
                email_data["html"] = body
            else:
                email_data["text"] = body
            
            response = requests.post(url, json=email_data, headers=headers)
            response.raise_for_status()
            
            print("MailerSend email sent successfully")
            return True
            
        except Exception as e:
            print(f"Error sending MailerSend email: {e}")
            return False
    
    def send_smtp_email(self, subject, body, is_html=False):
        """Send email via SMTP (legacy method)"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_user
            msg['To'] = self.email_to
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html' if is_html else 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_pass)
            
            text = msg.as_string()
            server.sendmail(self.email_user, self.email_to, text)
            server.quit()
            
            print("SMTP email sent successfully")
            return True
            
        except Exception as e:
            print(f"Error sending SMTP email: {e}")
            return False
    
    def send_simplepush_notification(self, title, message):
        """Send push notification via SimplePush"""
        try:
            if not self.use_simplepush:
                print("SimplePush not configured")
                return False
            
            simplepush_send(
                key=self.simplepush_key,
                title=title,
                message=message
            )
            
            print("SimplePush notification sent successfully")
            return True
            
        except Exception as e:
            print(f"Error sending SimplePush notification: {e}")
            return False
    
    def send_notifications(self, subject, body_html, body_text=None):
        """Send notifications via all configured methods"""
        if body_text is None:
            # Convert HTML to plain text for push notifications
            from bs4 import BeautifulSoup
            body_text = BeautifulSoup(body_html, 'html.parser').get_text().strip()
        
        success_count = 0
        
        # Send email notification
        if self.use_mailersend:
            if self.send_mailersend_email(subject, body_html, is_html=True):
                success_count += 1
        elif self.email_user and self.email_pass:
            if self.send_smtp_email(subject, body_html, is_html=True):
                success_count += 1
        
        # Send push notification
        if self.use_simplepush:
            # Truncate message for push notification
            push_message = body_text[:1000] + "..." if len(body_text) > 1000 else body_text
            if self.send_simplepush_notification(subject, push_message):
                success_count += 1
        
        return success_count > 0
    
    def format_tickets_html(self, tickets, title):
        html = f"""
        <h2>{title}</h2>
        <table border="1" cellpadding="5" cellspacing="0">
            <tr>
                <th>Section</th>
                <th>Price</th>
            </tr>
        """
        
        for ticket in tickets:
            html += f"""
            <tr>
                <td>{ticket['section']}</td>
                <td>${ticket['price']}</td>
            </tr>
            """
        
        html += "</table><br>"
        return html
    
    def check_for_alerts(self):
        """Check for premium tickets and send immediate alert"""
        tickets = self.scrape_tickets()
        if not tickets:
            print("No tickets found")
            return
        
        premium_tickets = self.filter_premium_tickets(tickets)
        
        if premium_tickets:
            subject = f"🎵 Premium Atmosphere Morrison Tickets Available Under $300!"
            
            body = f"""
            <h1>Premium tickets found for Atmosphere Morrison at Red Rocks!</h1>
            <p>Found {len(premium_tickets)} premium ticket(s) under $300:</p>
            {self.format_tickets_html(premium_tickets, "Premium Tickets Under $300")}
            <p><a href="{self.url}">View tickets on SeatPick</a></p>
            <p>Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            """
            
            # Convert HTML to text for push notifications
            body_text = f"Found {len(premium_tickets)} premium tickets under $300 for Atmosphere Morrison at Red Rocks on Sep 19, 2025. Check SeatPick for details."
            
            self.send_notifications(subject, body, body_text)
            print(f"Alert sent for {len(premium_tickets)} premium tickets")
        else:
            print("No premium tickets under $300 found")
    
    def send_daily_summary(self):
        """Send daily summary of all tickets under $400"""
        tickets = self.scrape_tickets()
        if not tickets:
            print("No tickets found for daily summary")
            return
        
        summary_tickets = self.filter_summary_tickets(tickets)
        
        subject = f"📊 Daily Atmosphere Morrison Ticket Summary - {datetime.now().strftime('%Y-%m-%d')}"
        
        if summary_tickets:
            body = f"""
            <h1>Daily Ticket Summary for Atmosphere Morrison at Red Rocks</h1>
            <p>Found {len(summary_tickets)} ticket(s) under $400:</p>
            {self.format_tickets_html(summary_tickets, "All Tickets Under $400")}
            <p><a href="{self.url}">View tickets on SeatPick</a></p>
            <p>Summary generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            """
        else:
            body = f"""
            <h1>Daily Ticket Summary for Atmosphere Morrison at Red Rocks</h1>
            <p>No tickets under $400 found today.</p>
            <p><a href="{self.url}">View tickets on SeatPick</a></p>
            <p>Summary generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            """
        
        # Convert HTML to text for push notifications
        if summary_tickets:
            body_text = f"Daily summary: {len(summary_tickets)} tickets under $400 available for Atmosphere Morrison at Red Rocks."
        else:
            body_text = "Daily summary: No tickets under $400 found for Atmosphere Morrison at Red Rocks today."
        
        self.send_notifications(subject, body, body_text)
        print(f"Daily summary sent with {len(summary_tickets) if summary_tickets else 0} tickets")

if __name__ == "__main__":
    monitor = SeatPickMonitor()
    
    if len(sys.argv) > 1 and sys.argv[1] == "daily":
        monitor.send_daily_summary()
    else:
        monitor.check_for_alerts()