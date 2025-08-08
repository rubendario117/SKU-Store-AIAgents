#!/usr/bin/env python3
"""
Test updated Ford configuration with OEM Parts Online domain
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.image_agent import ImageSourcingAgent

def test_ford_domain_update():
    """Test Ford domain configuration including new OEM Parts Online"""
    print("🧪 TESTING UPDATED FORD DOMAIN CONFIGURATION")
    print("=" * 50)
    
    agent = ImageSourcingAgent(None)
    
    # Check Ford brand registry
    ford_info = agent.brand_registry['FORD']
    print("✓ Ford brand registry:")
    print(f"  Authority: {ford_info['authority']}")
    print(f"  Domains: {ford_info['domains']}")
    print(f"  Search patterns: {ford_info['search_patterns']}")
    print()
    
    # Test authority scoring for various Ford URLs
    test_urls = [
        "https://ford.oempartsonline.com/oem-parts/ford-brake-pad-12345",
        "https://parts.ford.com/products/brake-pad-12345", 
        "https://fordparts.com/catalog/part/12345",
        "https://motorcraft.com/parts/brake-pad-12345",
        "https://amazon.com/ford-brake-pad-12345",
        "https://autozone.com/ford-parts"
    ]
    
    print("✓ Authority scoring test:")
    for url in test_urls:
        authority = agent._get_domain_authority(url, "FORD")
        is_official = agent._is_official_brand_site(url, "FORD")
        print(f"  {url}")
        print(f"    Authority: {authority}")
        print(f"    Official: {'✓' if is_official else '✗'}")
        print(f"    Would process: {'✓' if authority >= 75 else '✗'}")
        print()

if __name__ == "__main__":
    test_ford_domain_update()