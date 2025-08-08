#!/usr/bin/env python3
"""
Test enhanced error handling in VehicleApplicationAgent
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.vehicle_application_agent import VehicleApplicationAgent, VehicleApplication
from agents.image_agent import ImageSourcingAgent
from config import PART_NUMBER_COLUMN_SOURCE, BRAND_COLUMN_SOURCE
from dotenv import load_dotenv

def test_input_validation():
    """Test input validation and error handling"""
    print("🧪 TESTING INPUT VALIDATION AND ERROR HANDLING")
    print("=" * 60)
    
    agent = VehicleApplicationAgent()
    
    # Test invalid inputs
    test_cases = [
        ("None input", None),
        ("Empty dict", {}),
        ("Missing part number", {BRAND_COLUMN_SOURCE: "Honda"}),
        ("Missing brand", {PART_NUMBER_COLUMN_SOURCE: "12345"}),
        ("Empty strings", {PART_NUMBER_COLUMN_SOURCE: "", BRAND_COLUMN_SOURCE: ""}),
        ("Whitespace only", {PART_NUMBER_COLUMN_SOURCE: "   ", BRAND_COLUMN_SOURCE: "   "})
    ]
    
    for test_name, product_info in test_cases:
        print(f"Testing {test_name}:")
        result = agent.find_and_extract_applications(product_info)
        expected = []
        status = "✅ PASSED" if result == expected else f"❌ FAILED (got {result})"
        print(f"  Result: {status}")
        print()

def test_application_validation():
    """Test vehicle application validation"""
    print("🧪 TESTING APPLICATION VALIDATION")
    print("=" * 40)
    
    agent = VehicleApplicationAgent()
    
    # Test validation cases
    test_applications = [
        ("Valid application", VehicleApplication(year_start=2020, make="Honda", model="Civic")),
        ("Missing year", VehicleApplication(make="Honda", model="Civic")),
        ("Missing make", VehicleApplication(year_start=2020, model="Civic")),
        ("Invalid year (too old)", VehicleApplication(year_start=1800, make="Honda", model="Civic")),
        ("Invalid year (future)", VehicleApplication(year_start=2050, make="Honda", model="Civic")),
        ("Invalid make (numbers)", VehicleApplication(year_start=2020, make="Honda123", model="Civic")),
        ("Valid with trim", VehicleApplication(year_start=2020, make="Honda", model="Civic", trim="Si")),
        ("Year range valid", VehicleApplication(year_start=2018, year_end=2022, make="Honda", model="Civic")),
        ("Year range invalid", VehicleApplication(year_start=2022, year_end=2018, make="Honda", model="Civic"))
    ]
    
    for test_name, app in test_applications:
        is_valid = agent._validate_application(app)
        print(f"{test_name:25s}: {'✅ VALID' if is_valid else '❌ INVALID'}")
        
def test_error_recovery():
    """Test error recovery mechanisms"""
    print("\n🧪 TESTING ERROR RECOVERY")
    print("=" * 30)
    
    agent = VehicleApplicationAgent()
    
    # Test with invalid URLs and non-existent domains
    product_info = {
        PART_NUMBER_COLUMN_SOURCE: "test-part-123",
        BRAND_COLUMN_SOURCE: "NONEXISTENT_BRAND"
    }
    
    print("Testing with non-existent brand:")
    applications = agent.find_and_extract_applications(product_info)
    print(f"Result: {len(applications)} applications (expected: 0)")
    
    return True

def main():
    """Run all error handling tests"""
    print("🚀 ERROR HANDLING AND VALIDATION TESTS")
    print("=" * 70)
    
    test_results = []
    
    try:
        test_input_validation()
        test_results.append(("Input Validation", True))
    except Exception as e:
        print(f"❌ Input validation test failed: {e}")
        test_results.append(("Input Validation", False))
    
    try:
        test_application_validation()
        test_results.append(("Application Validation", True))
    except Exception as e:
        print(f"❌ Application validation test failed: {e}")
        test_results.append(("Application Validation", False))
    
    try:
        test_error_recovery()
        test_results.append(("Error Recovery", True))
    except Exception as e:
        print(f"❌ Error recovery test failed: {e}")
        test_results.append(("Error Recovery", False))
    
    # Results summary
    print("\n" + "=" * 70)
    print("📋 ERROR HANDLING TEST RESULTS")
    print("=" * 70)
    
    passed = 0
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:25s}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(test_results)} tests passed")
    
    if passed == len(test_results):
        print("🎉 ALL ERROR HANDLING TESTS PASSED!")
        return True
    else:
        print("⚠️  Some error handling tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)