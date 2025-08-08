#!/usr/bin/env python3
"""
Test Ford part sourcing with updated domain configuration
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.image_agent import ImageSourcingAgent
from config import PART_NUMBER_COLUMN_SOURCE, BRAND_COLUMN_SOURCE, DESCRIPTION_COLUMN_EN_SOURCE

def test_ford_part_sourcing():
    """Test Ford part with updated domain configuration"""
    print("🧪 TESTING FORD PART WITH UPDATED DOMAINS")
    print("=" * 45)
    
    load_dotenv()
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    
    if not serpapi_key:
        print("❌ SERPAPI_API_KEY not found")
        return
    
    agent = ImageSourcingAgent(serpapi_key)
    
    # Test with a common Ford part
    test_product = {
        PART_NUMBER_COLUMN_SOURCE: "FL-820-S",
        BRAND_COLUMN_SOURCE: "FORD",
        DESCRIPTION_COLUMN_EN_SOURCE: "Motorcraft Oil Filter",
        'sanitized_part_number': "FL-820-S"
    }
    
    print(f"🔍 Testing: {test_product[BRAND_COLUMN_SOURCE]} {test_product[PART_NUMBER_COLUMN_SOURCE]}")
    print(f"   Description: {test_product[DESCRIPTION_COLUMN_EN_SOURCE]}")
    
    # Show Ford registry info
    ford_info = agent.brand_registry['FORD']
    print(f"\n✓ Ford domains: {len(ford_info['domains'])} official domains")
    print(f"  Including: ford.oempartsonline.com")
    
    print(f"\n🔎 Starting search...")
    try:
        image_paths = agent.find_product_images(test_product, max_images_per_product=1)
        
        if image_paths:
            print(f"\n✅ SUCCESS: Found {len(image_paths)} image(s)")
            for path in image_paths:
                if os.path.exists(path):
                    size = os.path.getsize(path) / 1024
                    print(f"  📁 {path} ({size:.1f} KB)")
                else:
                    print(f"  ❌ {path} (not found)")
        else:
            print(f"\n❌ No official images found")
            print("   This may be normal if the specific part has no official images")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    test_ford_part_sourcing()