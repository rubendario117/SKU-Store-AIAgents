#!/usr/bin/env python3
"""
Test Bilstein shock absorber - another brand in registry
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.image_agent import ImageSourcingAgent
from config import PART_NUMBER_COLUMN_SOURCE, BRAND_COLUMN_SOURCE, DESCRIPTION_COLUMN_EN_SOURCE

def test_bilstein_part():
    """Test with Bilstein shock absorber"""
    print("🧪 TESTING BILSTEIN SHOCK ABSORBER")
    print("=" * 40)
    
    load_dotenv()
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    
    if not serpapi_key:
        print("❌ SERPAPI_API_KEY not found")
        return
    
    agent = ImageSourcingAgent(serpapi_key)
    
    test_product = {
        PART_NUMBER_COLUMN_SOURCE: "24-186728",
        BRAND_COLUMN_SOURCE: "BILSTEIN",
        DESCRIPTION_COLUMN_EN_SOURCE: "B4 Shock Absorber",
        'sanitized_part_number': "24-186728"
    }
    
    print(f"🔍 Testing: {test_product[BRAND_COLUMN_SOURCE]} {test_product[PART_NUMBER_COLUMN_SOURCE]}")
    
    # Check brand registry
    brand_upper = test_product[BRAND_COLUMN_SOURCE].upper()
    if brand_upper in agent.brand_registry:
        brand_info = agent.brand_registry[brand_upper]
        print(f"✓ Brand in registry - Authority: {brand_info['authority']}")
        print(f"  Domains: {brand_info['domains']}")
    
    print(f"\n🔎 Starting search...")
    try:
        image_paths = agent.find_product_images(test_product, max_images_per_product=1)
        
        if image_paths:
            print(f"\n✅ Found {len(image_paths)} image(s)")
            for path in image_paths:
                if os.path.exists(path):
                    size = os.path.getsize(path) / 1024
                    print(f"  📁 {path} ({size:.1f} KB)")
        else:
            print(f"\n❌ No images found - this is normal if no official images available")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    test_bilstein_part()