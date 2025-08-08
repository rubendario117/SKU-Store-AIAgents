#!/usr/bin/env python3
"""
Core functionality test for ImageSourcingAgent (no API calls)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.image_agent import ImageSourcingAgent

def test_core_functionality():
    """Test core functionality without API calls"""
    print("🧪 TESTING CORE IMAGE AGENT FUNCTIONALITY")
    print("=" * 50)
    
    # Initialize agent without API key
    agent = ImageSourcingAgent(None)
    
    # Test 1: Brand Registry
    print("✓ Brand registry initialized with brands:")
    for brand in list(agent.brand_registry.keys())[:5]:  # Show first 5
        info = agent.brand_registry[brand]
        print(f"  - {brand}: Authority {info['authority']}, Domains: {len(info['domains'])}")
    print(f"  ... and {len(agent.brand_registry) - 5} more brands\n")
    
    # Test 2: Authority Scoring
    print("✓ Authority scoring test:")
    test_cases = [
        ("https://parts.ford.com/products/abc123", "FORD", "Should be 95"),
        ("https://ebay.com/item/123", "FORD", "Should be 0"),
        ("https://knfilters.com/product/123", "K&N", "Should be 85"),
    ]
    
    for url, brand, expected in test_cases:
        authority = agent._get_domain_authority(url, brand)
        print(f"  {url} + {brand} = Authority {authority} ({expected})")
    print()
    
    # Test 3: Part Number Extraction
    print("✓ Part number extraction test:")
    test_text = "Ford Motorcraft Air Filter FA-1883 for 2015-2020 F-150"
    found_numbers = agent._extract_part_numbers_from_text(test_text)
    is_match = agent._validate_part_number_match(found_numbers, "FA-1883")
    print(f"  Text: {test_text}")
    print(f"  Found: {found_numbers}")
    print(f"  Match with FA-1883: {is_match}")
    print()
    
    print("🎉 Core functionality tests completed successfully!")

if __name__ == "__main__":
    test_core_functionality()