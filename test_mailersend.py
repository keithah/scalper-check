#!/usr/bin/env python3
import os
import requests

def test_mailersend_key():
    """Test MailerSend API key"""
    api_key = "mlsn.c67ce756febbf400128761affd927bb3b616c042237bca096d7b0edb8ed9e46c"
    from_email = "notifications@ferry-notifier.app"  # Using your ferry-notifier domain
    to_email = "keith@hadm.net"
    
    print(f"🔑 Testing MailerSend API key: {api_key[:20]}...")
    
    url = "https://api.mailersend.com/v1/email"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    email_data = {
        "from": {
            "email": from_email,
            "name": "SeatPick Monitor Test"
        },
        "to": [
            {
                "email": to_email,
                "name": "Keith"
            }
        ],
        "subject": "🧪 MailerSend Test - SeatPick Monitor",
        "html": """
        <h1>🧪 MailerSend Test Email</h1>
        <p>This is a test email from your SeatPick monitor system.</p>
        <p><strong>If you received this, your MailerSend API key is working correctly!</strong></p>
        <hr>
        <p>API Key: mlsn.c67ce756febbf400128761affd927bb3b616c042237bca096d7b0edb8ed9e46c</p>
        <p>From: notifications@ferry-notifier.app</p>
        <p>Test sent at: """ + str(__import__('datetime').datetime.now()) + """</p>
        """,
        "text": "MailerSend Test: If you received this, your API key is working! Key: mlsn.c67ce756febbf400128761affd927bb3b616c042237bca096d7b0edb8ed9e46c"
    }
    
    try:
        print("📤 Sending test email via MailerSend...")
        response = requests.post(url, json=email_data, headers=headers, timeout=30)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📊 Response headers: {dict(response.headers)}")
        
        if response.status_code == 202:
            print("✅ MailerSend test email sent successfully!")
            print(f"📧 Email sent to: {to_email}")
            print("🔍 Check your inbox (including spam folder)")
            return True
        else:
            print(f"❌ MailerSend test failed!")
            print(f"📊 Status: {response.status_code}")
            print(f"📊 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ MailerSend test error: {e}")
        return False

if __name__ == "__main__":
    success = test_mailersend_key()
    if success:
        print("\n🎉 MailerSend is ready to use!")
    else:
        print("\n⚠️ MailerSend test failed - check API key or domain settings")