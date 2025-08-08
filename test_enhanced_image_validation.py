#!/usr/bin/env python3
"""
Test enhanced image validation system
"""

import os
import sys
import io
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.image_agent import ImageSourcingAgent

def create_test_image(width, height, color=(255, 255, 255)):
    """Create a test image with specified dimensions and color"""
    img = Image.new('RGB', (width, height), color)
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    return buffer.getvalue()

def test_basic_validation():
    """Test basic image validation functions"""
    print("🧪 TESTING BASIC IMAGE VALIDATION")
    print("=" * 50)
    
    agent = ImageSourcingAgent(None)  # No API key needed for validation tests
    
    # Test 1: Valid high-resolution image
    valid_image = create_test_image(800, 600, (255, 255, 255))
    validation = agent._enhanced_image_validation(
        valid_image, 
        "TEST-123", 
        "TEST_BRAND", 
        "https://example.com/product.jpg"
    )
    
    print(f"✅ High-resolution white image:")
    print(f"   Valid: {validation['is_valid']}")
    print(f"   Quality Score: {validation['quality_score']:.2f}")
    print(f"   Dimensions: {validation['validation_details'].get('dimensions', 'N/A')}")
    print()
    
    # Test 2: Too small image
    small_image = create_test_image(150, 150, (255, 255, 255))
    validation = agent._enhanced_image_validation(
        small_image, 
        "TEST-123", 
        "TEST_BRAND", 
        "https://example.com/small.jpg"
    )
    
    print(f"❌ Small image (should be rejected):")
    print(f"   Valid: {validation['is_valid']}")
    print(f"   Rejection Reason: {validation['rejection_reason']}")
    print()
    
    # Test 3: Non-white background
    colored_image = create_test_image(800, 600, (255, 0, 0))  # Red background
    validation = agent._enhanced_image_validation(
        colored_image, 
        "TEST-123", 
        "TEST_BRAND", 
        "https://example.com/colored.jpg"
    )
    
    print(f"❌ Colored background image (should be rejected):")
    print(f"   Valid: {validation['is_valid']}")
    print(f"   Rejection Reason: {validation['rejection_reason']}")
    print()

def test_quality_assessment():
    """Test image quality assessment"""
    print("🧪 TESTING QUALITY ASSESSMENT")
    print("=" * 40)
    
    agent = ImageSourcingAgent(None)
    
    # Create images with different quality characteristics
    test_cases = [
        ("High resolution", create_test_image(1920, 1080)),
        ("Medium resolution", create_test_image(800, 600)),
        ("Low resolution", create_test_image(400, 300)),
        ("Square format", create_test_image(500, 500)),
        ("Extreme aspect ratio", create_test_image(1000, 200))
    ]
    
    for test_name, image_bytes in test_cases:
        img = Image.open(io.BytesIO(image_bytes))
        quality_score = agent._assess_image_quality(img)
        print(f"{test_name:20s}: Quality score {quality_score:.2f}")

def test_generic_image_detection():
    """Test generic/stock image detection"""
    print("\n🧪 TESTING GENERIC IMAGE DETECTION")
    print("=" * 45)
    
    agent = ImageSourcingAgent(None)
    test_image = create_test_image(400, 400)
    img = Image.open(io.BytesIO(test_image))
    
    test_urls = [
        ("Normal product image", "https://brand.com/products/part123.jpg"),
        ("Placeholder image", "https://example.com/placeholder.jpg"),
        ("Stock image", "https://stock.com/generic_part.jpg"),
        ("Default thumbnail", "https://site.com/default-thumbnail.jpg"),
        ("Coming soon image", "https://brand.com/coming-soon.jpg")
    ]
    
    for test_name, url in test_urls:
        generic_score = agent._detect_generic_image(img, url)
        is_generic = "YES" if generic_score > 0.3 else "NO"
        print(f"{test_name:20s}: Generic score {generic_score:.2f} ({is_generic})")

def test_validation_pipeline():
    """Test complete validation pipeline"""
    print("\n🧪 TESTING COMPLETE VALIDATION PIPELINE")
    print("=" * 50)
    
    agent = ImageSourcingAgent(None)
    
    # Create various test scenarios
    scenarios = [
        {
            'name': 'High-quality product image',
            'image': create_test_image(1000, 800),
            'part_number': 'ABC-123',
            'brand': 'HONDA',
            'url': 'https://honda.com/parts/abc123.jpg',
            'expected_valid': True
        },
        {
            'name': 'Low-quality image',
            'image': create_test_image(200, 150),
            'part_number': 'XYZ-789',
            'brand': 'TOYOTA',
            'url': 'https://toyota.com/parts/xyz789.jpg',
            'expected_valid': False
        },
        {
            'name': 'Placeholder image',
            'image': create_test_image(300, 300),
            'part_number': 'DEF-456',
            'brand': 'FORD',
            'url': 'https://ford.com/placeholder.jpg',
            'expected_valid': False  # Should be rejected due to placeholder URL
        }
    ]
    
    for scenario in scenarios:
        print(f"\nScenario: {scenario['name']}")
        validation = agent._enhanced_image_validation(
            scenario['image'],
            scenario['part_number'],
            scenario['brand'],
            scenario['url']
        )
        
        print(f"  Valid: {validation['is_valid']} (expected: {scenario['expected_valid']})")
        print(f"  Quality Score: {validation['quality_score']:.2f}")
        
        if not validation['is_valid']:
            print(f"  Rejection Reason: {validation['rejection_reason']}")
        
        # Show quality breakdown for debugging
        if 'quality_factors' in validation['validation_details']:
            print(f"  Quality breakdown:")
            for factor_name, score, weight in validation['validation_details']['quality_factors']:
                print(f"    {factor_name}: {score:.2f} (weight: {weight})")

def main():
    """Run all enhanced image validation tests"""
    print("🚀 ENHANCED IMAGE VALIDATION SYSTEM TESTS")
    print("=" * 70)
    
    test_results = []
    
    try:
        test_basic_validation()
        test_results.append(("Basic Validation", True))
    except Exception as e:
        print(f"❌ Basic validation test failed: {e}")
        test_results.append(("Basic Validation", False))
    
    try:
        test_quality_assessment()
        test_results.append(("Quality Assessment", True))
    except Exception as e:
        print(f"❌ Quality assessment test failed: {e}")
        test_results.append(("Quality Assessment", False))
    
    try:
        test_generic_image_detection()
        test_results.append(("Generic Detection", True))
    except Exception as e:
        print(f"❌ Generic detection test failed: {e}")
        test_results.append(("Generic Detection", False))
    
    try:
        test_validation_pipeline()
        test_results.append(("Validation Pipeline", True))
    except Exception as e:
        print(f"❌ Validation pipeline test failed: {e}")
        test_results.append(("Validation Pipeline", False))
    
    # Results summary
    print("\n" + "=" * 70)
    print("📋 ENHANCED IMAGE VALIDATION TEST RESULTS")
    print("=" * 70)
    
    passed = 0
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:25s}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(test_results)} tests passed")
    
    if passed == len(test_results):
        print("🎉 ALL ENHANCED IMAGE VALIDATION TESTS PASSED!")
        return True
    else:
        print("⚠️  Some enhanced image validation tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)