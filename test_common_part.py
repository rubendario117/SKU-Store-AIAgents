#!/usr/bin/env python3
"""
Test with a very common automotive part likely to have official images
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.image_agent import ImageSourcingAgent
from config import PART_NUMBER_COLUMN_SOURCE, BRAND_COLUMN_SOURCE, DESCRIPTION_COLUMN_EN_SOURCE

def test_common_parts():
    """Test with common parts likely to have official images"""
    print("🧪 TESTING COMMON AUTOMOTIVE PARTS")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    
    if not serpapi_key:
        print("❌ SERPAPI_API_KEY not found")
        return
    
    agent = ImageSourcingAgent(serpapi_key)
    
    # Test with very common aftermarket parts
    test_products = [
        {
            PART_NUMBER_COLUMN_SOURCE: "33-2031-2",
            BRAND_COLUMN_SOURCE: "K&N",
            DESCRIPTION_COLUMN_EN_SOURCE: "Air Filter",
            'sanitized_part_number': "33-2031-2"
        }
    ]
    
    for product in test_products:
        print(f"\n🔍 Testing: {product[BRAND_COLUMN_SOURCE]} {product[PART_NUMBER_COLUMN_SOURCE]}")
        print(f"   Description: {product[DESCRIPTION_COLUMN_EN_SOURCE]}")
        print("-" * 30)
        
        try:
            # Test the brand registry lookup first
            brand_upper = product[BRAND_COLUMN_SOURCE].upper()
            if brand_upper in agent.brand_registry:
                brand_info = agent.brand_registry[brand_upper]
                print(f"✓ Brand found in registry:")
                print(f"  Authority: {brand_info['authority']}")
                print(f"  Domains: {brand_info['domains']}")
                print(f"  Search patterns: {brand_info['search_patterns']}")
            else:
                print(f"⚠️  Brand {brand_upper} not in registry")
            
            print(f"\n🔎 Starting image search...")
            image_paths = agent.find_product_images(product, max_images_per_product=1)
            
            if image_paths:
                print(f"\n✅ SUCCESS: Found {len(image_paths)} image(s)")
                for path in image_paths:
                    if os.path.exists(path):
                        file_size = os.path.getsize(path) / 1024
                        print(f"  📁 {path} ({file_size:.1f} KB)")
                    else:
                        print(f"  ❌ {path} (not found)")
            else:
                print(f"\n❌ No official images found")
                
        except Exception as e:
            print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    test_common_parts()