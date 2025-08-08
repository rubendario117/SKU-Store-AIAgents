#!/usr/bin/env python3
"""
Test single image sourcing with real API call
"""

import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.image_agent import ImageSourcingAgent
from config import PART_NUMBER_COLUMN_SOURCE, BRAND_COLUMN_SOURCE, DESCRIPTION_COLUMN_EN_SOURCE

def test_single_image_sourcing():
    """Test image sourcing for one automotive part"""
    print("🧪 TESTING SINGLE IMAGE SOURCING")
    print("=" * 40)
    
    # Load environment variables
    load_dotenv()
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    
    if not serpapi_key:
        print("❌ SERPAPI_API_KEY not found in .env file")
        print("   Cannot test real image sourcing without API key")
        return
    
    # Initialize agent
    agent = ImageSourcingAgent(serpapi_key)
    
    # Test with a well-known Ford part
    test_product = {
        PART_NUMBER_COLUMN_SOURCE: "F7TZ-9601-A",
        BRAND_COLUMN_SOURCE: "FORD",
        DESCRIPTION_COLUMN_EN_SOURCE: "Power Steering Pump",
        'sanitized_part_number': "F7TZ-9601-A"
    }
    
    print(f"Testing: {test_product[BRAND_COLUMN_SOURCE]} {test_product[PART_NUMBER_COLUMN_SOURCE]}")
    print(f"Description: {test_product[DESCRIPTION_COLUMN_EN_SOURCE]}")
    print("-" * 40)
    
    try:
        # Test image sourcing with timeout protection
        print("Starting image search...")
        image_paths = agent.find_product_images(test_product, max_images_per_product=1)
        
        if image_paths:
            print(f"\n✅ SUCCESS: Found {len(image_paths)} image(s)")
            for path in image_paths:
                if os.path.exists(path):
                    file_size = os.path.getsize(path) / 1024  # KB
                    print(f"  📁 {path}")
                    print(f"     Size: {file_size:.1f} KB")
                    
                    # Basic validation
                    from PIL import Image
                    try:
                        img = Image.open(path)
                        print(f"     Dimensions: {img.width}x{img.height}")
                        print(f"     Format: {img.format}")
                        img.close()
                    except Exception as e:
                        print(f"     ❌ Image validation error: {e}")
                else:
                    print(f"  ❌ File not found: {path}")
        else:
            print("\n❌ No images found")
            print("   This might be expected if no official images are available")
            
    except Exception as e:
        print(f"\n❌ ERROR during image sourcing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_single_image_sourcing()