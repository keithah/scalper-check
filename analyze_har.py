#!/usr/bin/env python3
import json

with open('/Users/keith/src/scalper-check/seatpick.har', 'r') as f:
    har = json.load(f)
    
for entry in har['log']['entries']:
    if 'api/proxy/4/events/366607/listings' in entry['request']['url']:
        response_text = entry['response']['content']['text']
        data = json.loads(response_text)
        
        # Find tickets in desired sections under 400
        desired_sections = ['Center', 'Front Center', 'Front Left', 'Front Right', 'Left', 'Reserved Seating', 'Right']
        
        filtered = []
        for listing in data['listings']:
            section = listing.get('section', '')
            if section in desired_sections and listing['price'] < 400:
                filtered.append({
                    'section': section,
                    'row': listing.get('row', ''),
                    'price': listing['price'],
                    'seller': listing['seller'],
                    'deepLink': listing.get('deepLink', '')
                })
        
        # Sort by price
        filtered.sort(key=lambda x: x['price'])
        
        print(f'Found {len(filtered)} tickets in desired sections under $400:')
        print('-' * 60)
        for i, t in enumerate(filtered, 1):
            seller_names = {'vgg': 'Viagogo', 'vividseats': 'VividSeats', 'vividSeats': 'VividSeats', 'te': 'Events365', 'tn': 'TicketNetwork'}
            seller = seller_names.get(t['seller'], t['seller'])
            row_info = f"Row {t['row']}" if t['row'] else ''
            print(f"{i:2d}. {t['section']:20s} {row_info:10s} ${t['price']:4d}  via {seller}")
        
        print("\n" + "="*60)
        print("Your screenshot shows these premium tickets:")
        print("- Reserved Seating: $117 via Viagogo")
        print("- Right: $314 via VividSeats (Row 6)")
        print("- Left: $323 via VividSeats (Row 7)")
        print("- Front Right: $342 via Viagogo")
        print("- Front Left: $382 via Viagogo")
        print("\nSearching for these specific tickets...")
        
        # Find specific tickets
        for t in filtered:
            if t['section'] == 'Right' and t['price'] == 314:
                print(f"✓ Found Right $314: {t['deepLink'][:100]}...")
            if t['section'] == 'Left' and t['price'] == 323:
                print(f"✓ Found Left $323: {t['deepLink'][:100]}...")
                
        break