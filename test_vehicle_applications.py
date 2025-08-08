#!/usr/bin/env python3
"""
Test the VehicleApplicationAgent with real automotive parts
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.vehicle_application_agent import VehicleApplicationAgent, VehicleApplication
from agents.image_agent import ImageSourcingAgent
from config import PART_NUMBER_COLUMN_SOURCE, BRAND_COLUMN_SOURCE, DESCRIPTION_COLUMN_EN_SOURCE
from dotenv import load_dotenv

def test_vehicle_application_parsing():
    """Test individual vehicle application parsing"""
    print("🧪 TESTING VEHICLE APPLICATION PARSING")
    print("=" * 50)
    
    # Test VehicleApplication class
    print("✓ Testing VehicleApplication normalization:")
    
    test_app = VehicleApplication(
        year_start=2019,
        year_end=2021,
        make="HONDA",
        model="Civic",
        trim="Si",
        engine="2.0L Turbo"
    )
    
    print(f"  Input: 2019-2021 HONDA Civic Si 2.0L Turbo")
    print(f"  Normalized Make: {test_app.make}")
    print(f"  Display String: {test_app.to_display_string()}")
    print(f"  JSON: {test_app.to_dict()}")
    print()

def test_hawk_performance_parser():
    """Test Hawk Performance specific parsing"""
    print("🧪 TESTING HAWK PERFORMANCE PARSER")
    print("=" * 40)
    
    from agents.vehicle_application_agent import HawkPerformanceParser
    import requests
    
    session = requests.Session()
    parser = HawkPerformanceParser(session)
    
    # Test sample vehicle text parsing
    test_texts = [
        "2019 Honda Civic Si 2.0L Turbo",
        "2015-2020 Ford F-150 3.5L V6",
        "2018 Toyota Camry SE 2.5L",
        "2020 Chevrolet Silverado 1500 6.2L V8"
    ]
    
    for text in test_texts:
        app = parser._parse_hawk_vehicle_text(text)
        if app:
            print(f"✓ Parsed: {text}")
            print(f"  Result: {app.to_display_string()}")
        else:
            print(f"✗ Failed: {text}")
        print()

def test_real_vehicle_extraction():
    """Test with real vehicle extraction from websites"""
    print("🧪 TESTING REAL VEHICLE EXTRACTION")
    print("=" * 40)
    
    load_dotenv()
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    
    if not serpapi_key:
        print("❌ SERPAPI_API_KEY not found - skipping real extraction test")
        return
    
    # Initialize agents
    vehicle_agent = VehicleApplicationAgent()
    image_agent = ImageSourcingAgent(serpapi_key)
    
    # Test products from your examples
    test_products = [
        {
            PART_NUMBER_COLUMN_SOURCE: "hb145w-570",
            BRAND_COLUMN_SOURCE: "HAWK PERFORMANCE",
            DESCRIPTION_COLUMN_EN_SOURCE: "Brake Pad",
            'sanitized_part_number': "hb145w-570"
        },
        {
            PART_NUMBER_COLUMN_SOURCE: "24-186728",
            BRAND_COLUMN_SOURCE: "BILSTEIN",
            DESCRIPTION_COLUMN_EN_SOURCE: "B8 5100 Series Shock",
            'sanitized_part_number': "24-186728"
        }
    ]
    
    for product in test_products:
        part_num = product[PART_NUMBER_COLUMN_SOURCE]
        brand = product[BRAND_COLUMN_SOURCE]
        
        print(f"\n🔍 Testing: {brand} {part_num}")
        print("-" * 30)
        
        try:
            # Test direct URL extraction
            test_urls = [
                f"https://www.hawkperformance.com/pads/{part_num}",
                f"https://bilsteincanada.com/product/b8-5100-series-0-1-lift-rear-{part_num}/"
            ]
            
            for url in test_urls:
                if part_num.lower() in url.lower():
                    print(f"  Testing URL: {url}")
                    applications = vehicle_agent.extract_applications_from_url(url, part_num, brand)
                    
                    if applications:
                        print(f"  ✅ Found {len(applications)} applications:")
                        for i, app in enumerate(applications[:5], 1):  # Show first 5
                            print(f"    {i}. {app.to_display_string()}")
                        if len(applications) > 5:
                            print(f"    ... and {len(applications) - 5} more")
                    else:
                        print(f"  ❌ No applications found")
                    break
            
            # Test using find_and_extract_applications method
            print(f"\n  🔎 Testing automatic extraction...")
            applications = vehicle_agent.find_and_extract_applications(product, image_agent)
            
            if applications:
                print(f"  ✅ Auto-extracted {len(applications)} applications:")
                for i, app in enumerate(applications[:3], 1):  # Show first 3
                    print(f"    {i}. {app.to_display_string()}")
            else:
                print(f"  ❌ No applications auto-extracted")
                
        except Exception as e:
            print(f"  ❌ ERROR: {e}")

def test_application_merging():
    """Test merging official and Excel applications"""
    print("\n🧪 TESTING APPLICATION MERGING")
    print("=" * 35)
    
    from main import merge_applications
    
    # Create sample official applications
    official_apps = [
        VehicleApplication(2019, 2021, "Honda", "Civic", "Si", "2.0L Turbo"),
        VehicleApplication(2020, 2023, "Toyota", "Camry", "SE", "2.5L")
    ]
    
    # Sample Excel applications
    excel_apps = [
        "2018-2020 Honda Accord",
        "2019 Honda Civic Si 2.0L Turbo",  # Duplicate with official
        "2021 Toyota Corolla"
    ]
    
    merged = merge_applications(official_apps, excel_apps)
    
    print("✓ Official applications:")
    for app in official_apps:
        print(f"  - {app.to_display_string()}")
    
    print("\n✓ Excel applications:")
    for app in excel_apps:
        print(f"  - {app}")
    
    print("\n✓ Merged applications (duplicates removed):")
    for app in merged:
        print(f"  - {app}")

def main():
    """Run all vehicle application tests"""
    print("🚗 TESTING VEHICLE APPLICATION EXTRACTION SYSTEM")
    print("=" * 55)
    
    try:
        test_vehicle_application_parsing()
        test_hawk_performance_parser()
        test_application_merging()
        test_real_vehicle_extraction()
        
        print("\n" + "=" * 55)
        print("🎉 VEHICLE APPLICATION TESTS COMPLETED")
        print("=" * 55)
        
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()