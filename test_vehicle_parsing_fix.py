#!/usr/bin/env python3
"""
Test script to validate the critical vehicle application parsing fix
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.vehicle_application_agent import HawkPerformanceParser
import requests

def test_concatenated_parsing():
    """Test the new concatenated vehicle parsing functionality"""
    print("🧪 TESTING CONCATENATED VEHICLE PARSING FIX")
    print("=" * 60)
    
    # Create parser instance
    session = requests.Session()
    parser = HawkPerformanceParser(session)
    
    # Test case from actual cache data - massive concatenated string
    concatenated_text = """2020 Acura ILX Base OE Incl.Shims2020 Acura ILX 2.4L OE Incl.Shims2019 Acura ILX Base 2.4L OE Incl.Shims2019 Acura ILX 2.4L OE Incl.Shims2018 Acura ILX Base 2.4L OE Incl.Shims2017 Acura ILX Base 2.4L OE Incl.Shims2016 Acura ILX Base 2.4L OE Incl.Shims2015 Honda CR-Z EX 1.5L2015 Honda CR-Z Base 1.5L2015 Honda Civic Si 2.4L"""
    
    print(f"Input text (first 100 chars): {concatenated_text[:100]}...")
    print(f"Total length: {len(concatenated_text)} characters")
    print()
    
    # Parse using new method
    applications = parser._parse_concatenated_vehicle_text(concatenated_text)
    
    print(f"✅ PARSED {len(applications)} INDIVIDUAL APPLICATIONS:")
    print("-" * 40)
    
    for i, app in enumerate(applications[:10]):  # Show first 10
        print(f"{i+1:2d}. {app.to_display_string()}")
        
    if len(applications) > 10:
        print(f"    ... and {len(applications) - 10} more applications")
    
    print()
    
    # Validate parsing quality
    valid_apps = [app for app in applications if app.make and app.model and app.year_start]
    print(f"📊 QUALITY METRICS:")
    print(f"   Total applications: {len(applications)}")
    print(f"   Valid applications: {len(valid_apps)}")
    print(f"   Success rate: {(len(valid_apps)/len(applications)*100):.1f}%")
    
    # Check for duplicates
    unique_apps = set()
    for app in applications:
        unique_apps.add(f"{app.year_start}-{app.make}-{app.model}")
    print(f"   Unique combinations: {len(unique_apps)}")
    print(f"   Duplicate rate: {((len(applications) - len(unique_apps))/len(applications)*100):.1f}%")
    
    return len(valid_apps) > 5  # Success if we got at least 5 valid applications

def test_single_vehicle_parsing():
    """Test single vehicle parsing"""
    print("\n🧪 TESTING SINGLE VEHICLE PARSING")
    print("=" * 40)
    
    session = requests.Session()
    parser = HawkPerformanceParser(session)
    
    test_cases = [
        "2020 Acura ILX Base 2.4L OE Incl.Shims",
        "2015 Honda Civic Si 2.4L",
        "2019 Toyota Camry SE 2.5L",
        "2021 Ford F-150 3.5L V6"
    ]
    
    for text in test_cases:
        app = parser._parse_single_vehicle_application(text)
        if app:
            print(f"✅ '{text}' → {app.to_display_string()}")
        else:
            print(f"❌ Failed to parse: '{text}'")
    
    return True

def test_fallback_parsing():
    """Test fallback parsing mechanism"""
    print("\n🧪 TESTING FALLBACK PARSING")
    print("=" * 30)
    
    session = requests.Session()
    parser = HawkPerformanceParser(session)
    
    # Problematic text that might not split well
    problematic_text = "Various applications include 2019 Honda Civic and 2020 Toyota Corolla plus 2021 Ford Focus models"
    
    applications = parser._parse_fallback_concatenated_text(problematic_text)
    
    print(f"Problematic text: {problematic_text}")
    print(f"Extracted {len(applications)} applications:")
    for app in applications:
        print(f"  - {app.to_display_string()}")
    
    return len(applications) > 0

def main():
    """Run all parsing tests"""
    print("🚀 VEHICLE APPLICATION PARSING FIX VALIDATION")
    print("=" * 70)
    
    test_results = []
    
    # Run tests
    test_results.append(("Concatenated Parsing", test_concatenated_parsing()))
    test_results.append(("Single Vehicle Parsing", test_single_vehicle_parsing()))  
    test_results.append(("Fallback Parsing", test_fallback_parsing()))
    
    # Results summary
    print("\n" + "=" * 70)
    print("📋 TEST RESULTS SUMMARY")
    print("=" * 70)
    
    passed = 0
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:25s}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(test_results)} tests passed")
    
    if passed == len(test_results):
        print("🎉 ALL TESTS PASSED - Vehicle parsing fix is working correctly!")
        return True
    else:
        print("⚠️  Some tests failed - review parsing logic")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)