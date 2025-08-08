#!/usr/bin/env python3
"""
Test script for enhanced ImageSourcingAgent
Tests official website detection, part number validation, and image sourcing
"""

import os
import sys
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.image_agent import ImageSourcingAgent
from config import PART_NUMBER_COLUMN_SOURCE, BRAND_COLUMN_SOURCE, DESCRIPTION_COLUMN_EN_SOURCE

def test_brand_registry_and_authority():
    """Test brand registry initialization and authority scoring"""
    print("=" * 60)
    print("TEST 1: Brand Registry and Authority Scoring")
    print("=" * 60)
    
    # Initialize agent without API key for registry testing
    agent = ImageSourcingAgent(None)
    
    # Test brand registry initialization
    print(f"✓ Brand registry initialized with {len(agent.brand_registry)} brands")
    
    # Test authority scoring for known brands
    test_cases = [
        ("https://parts.ford.com/products/abc123", "FORD", 95),
        ("https://gmpartsdirect.com/part/xyz789", "CHEVROLET", 95),
        ("https://knfilters.com/product/123", "K&N", 85),
        ("https://ebay.com/item/123", "FORD", 0),
        ("https://autozone.com/parts/456", "TOYOTA", 0),
    ]
    
    for url, brand, expected_min_authority in test_cases:
        authority = agent._get_domain_authority(url, brand)
        is_official = agent._is_official_brand_site(url, brand)
        
        print(f"URL: {url}")
        print(f"  Brand: {brand}")
        print(f"  Authority Score: {authority}")
        print(f"  Is Official: {'✓' if is_official else '✗'}")
        print(f"  Expected >= {expected_min_authority}: {'✓' if authority >= expected_min_authority else '✗'}")
        print()

def test_part_number_extraction():
    """Test part number extraction and validation"""
    print("=" * 60)
    print("TEST 2: Part Number Extraction and Validation")
    print("=" * 60)
    
    agent = ImageSourcingAgent(None)
    
    test_texts = [
        "Ford Motorcraft Air Filter FA-1883 for 2015-2020 F-150",
        "K&N Performance Air Filter 33-2031-2 Cold Air Intake",
        "OEM Toyota Part Number 90915-YZZD4 Oil Filter",
        "Bilstein B4 Shock Absorber 19-063257 Front Left",
        "Part# AC-DELCO PF53 Engine Oil Filter"
    ]
    
    target_parts = ["FA-1883", "33-2031-2", "90915-YZZD4", "19-063257", "PF53"]
    
    for i, text in enumerate(test_texts):
        print(f"Text: {text}")
        found_numbers = agent._extract_part_numbers_from_text(text)
        target = target_parts[i]
        is_match = agent._validate_part_number_match(found_numbers, target)
        
        print(f"  Found Part Numbers: {found_numbers}")
        print(f"  Target: {target}")
        print(f"  Match Found: {'✓' if is_match else '✗'}")
        print()

def test_image_sourcing_with_real_parts():
    """Test actual image sourcing with real automotive parts"""
    print("=" * 60)
    print("TEST 3: Real Image Sourcing Test")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    
    if not serpapi_key:
        print("❌ SERPAPI_API_KEY not found in environment variables")
        print("   Please add SERPAPI_API_KEY to your .env file to test image sourcing")
        return
    
    agent = ImageSourcingAgent(serpapi_key)
    
    # Test with real automotive parts from different brands
    test_products = [
        {
            PART_NUMBER_COLUMN_SOURCE: "FA-1883",
            BRAND_COLUMN_SOURCE: "FORD",
            DESCRIPTION_COLUMN_EN_SOURCE: "Motorcraft Air Filter",
            'sanitized_part_number': "FA-1883"
        },
        {
            PART_NUMBER_COLUMN_SOURCE: "33-2031-2", 
            BRAND_COLUMN_SOURCE: "K&N",
            DESCRIPTION_COLUMN_EN_SOURCE: "Performance Air Filter",
            'sanitized_part_number': "33-2031-2"
        },
        {
            PART_NUMBER_COLUMN_SOURCE: "19-063257",
            BRAND_COLUMN_SOURCE: "BILSTEIN", 
            DESCRIPTION_COLUMN_EN_SOURCE: "B4 Shock Absorber",
            'sanitized_part_number': "19-063257"
        }
    ]
    
    for product in test_products:
        print(f"\nTesting: {product[BRAND_COLUMN_SOURCE]} {product[PART_NUMBER_COLUMN_SOURCE]}")
        print("-" * 50)
        
        try:
            # Test image sourcing
            image_paths = agent.find_product_images(product, max_images_per_product=1)
            
            if image_paths:
                print(f"✓ SUCCESS: Found {len(image_paths)} image(s)")
                for path in image_paths:
                    if os.path.exists(path):
                        file_size = os.path.getsize(path) / 1024  # KB
                        print(f"  - {path} ({file_size:.1f} KB)")
                    else:
                        print(f"  - {path} (FILE NOT FOUND)")
            else:
                print("❌ No images found")
                
        except Exception as e:
            print(f"❌ ERROR: {e}")

def test_url_authority_detection():
    """Test URL authority detection with various automotive websites"""
    print("=" * 60)
    print("TEST 4: URL Authority Detection")
    print("=" * 60)
    
    agent = ImageSourcingAgent(None)
    
    # Test URLs from various automotive websites
    test_urls = [
        # Official OEM sites (should be high authority)
        ("https://parts.ford.com/catalog/part/FA-1883", "FORD"),
        ("https://gmpartsdirect.com/parts/engine-oil-filter", "CHEVROLET"),
        ("https://parts.toyota.com/productDisplay?partId=12345", "TOYOTA"),
        
        # Official aftermarket sites (should be high authority)
        ("https://knfilters.com/air-filters/33-2031", "K&N"),
        ("https://bilstein.com/us/en/products/shock-absorber", "BILSTEIN"),
        
        # Third-party retailers (should be low/zero authority)
        ("https://autozone.com/filters-and-pcv/air-filter", "FORD"),
        ("https://ebay.com/itm/ford-air-filter-fa1883", "FORD"),
        ("https://amazon.com/dp/B001234567", "K&N"),
        
        # Generic parts sites (should be zero authority)
        ("https://rockauto.com/en/catalog/ford,2020,f-150", "FORD"),
        ("https://partsgeek.com/mmford-f150-air-filters.html", "FORD")
    ]
    
    for url, brand in test_urls:
        authority = agent._get_domain_authority(url, brand)
        is_official = agent._is_official_brand_site(url, brand)
        
        print(f"URL: {url}")
        print(f"  Brand: {brand}")
        print(f"  Authority: {authority}")
        print(f"  Official: {'✓' if is_official else '✗'}")
        print(f"  Would Process: {'✓' if authority >= 75 else '✗'}")
        print()

def main():
    """Run all tests"""
    print("🧪 TESTING ENHANCED IMAGE SOURCING AGENT")
    print("=" * 60)
    
    try:
        # Test 1: Brand registry and authority scoring
        test_brand_registry_and_authority()
        
        # Test 2: Part number extraction
        test_part_number_extraction()
        
        # Test 3: URL authority detection
        test_url_authority_detection()
        
        # Test 4: Real image sourcing (requires API key)
        test_image_sourcing_with_real_parts()
        
        print("=" * 60)
        print("🎉 ALL TESTS COMPLETED")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()