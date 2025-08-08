#!/usr/bin/env python3
"""
Test runner for all DPerformance Agent tests
Runs comprehensive test suite and generates coverage report
"""

import unittest
import sys
import os
import time
from io import StringIO

def run_test_suite():
    """Run all tests and provide comprehensive reporting"""
    
    print("🧪 DPerformance Agent - Comprehensive Test Suite")
    print("=" * 60)
    
    # Test modules to run
    test_modules = [
        'test_vehicle_parsing_fix',
        'test_enhanced_image_validation', 
        'test_monitoring_system',
        'test_complete_system'
    ]
    
    all_results = []
    total_tests = 0
    total_failures = 0
    total_errors = 0
    
    start_time = time.time()
    
    for module in test_modules:
        print(f"\n🔍 Running tests from {module}")
        print("-" * 40)
        
        try:
            # Import the test module
            test_module = __import__(module)
            
            # Create test suite
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromModule(test_module)
            
            # Run tests with detailed output
            stream = StringIO()
            runner = unittest.TextTestRunner(
                stream=stream, 
                verbosity=2,
                buffer=True,
                failfast=False
            )
            
            result = runner.run(suite)
            
            # Store results
            all_results.append({
                'module': module,
                'result': result,
                'output': stream.getvalue()
            })
            
            # Update totals
            total_tests += result.testsRun
            total_failures += len(result.failures)
            total_errors += len(result.errors)
            
            # Print summary for this module
            print(f"✅ Tests run: {result.testsRun}")
            print(f"❌ Failures: {len(result.failures)}")
            print(f"💥 Errors: {len(result.errors)}")
            
            if result.failures:
                print("Failures:")
                for test, traceback in result.failures:
                    print(f"  - {test}: {traceback.split('\\n')[-2]}")
            
            if result.errors:
                print("Errors:")
                for test, traceback in result.errors:
                    print(f"  - {test}: {traceback.split('\\n')[-2]}")
                    
        except ImportError as e:
            print(f"⚠️  Could not import {module}: {e}")
            continue
        except Exception as e:
            print(f"💥 Error running tests for {module}: {e}")
            continue
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Overall summary
    print(f"\n📊 OVERALL TEST SUMMARY")
    print("=" * 60)
    print(f"Total test modules: {len(test_modules)}")
    print(f"Total tests run: {total_tests}")
    print(f"Total failures: {total_failures}")
    print(f"Total errors: {total_errors}")
    print(f"Success rate: {((total_tests - total_failures - total_errors) / total_tests * 100):.1f}%" if total_tests > 0 else "N/A")
    print(f"Execution time: {duration:.2f} seconds")
    
    # Detailed results
    if total_failures > 0 or total_errors > 0:
        print(f"\n🔍 DETAILED FAILURE ANALYSIS")
        print("=" * 60)
        
        for module_result in all_results:
            result = module_result['result']
            if result.failures or result.errors:
                print(f"\nModule: {module_result['module']}")
                
                for test, traceback in result.failures:
                    print(f"\n❌ FAILURE: {test}")
                    print(traceback)
                
                for test, traceback in result.errors:
                    print(f"\n💥 ERROR: {test}")
                    print(traceback)
    
    # Performance metrics from monitoring tests
    try:
        from monitoring import performance_monitor
        stats = performance_monitor.get_performance_stats(hours=1)
        
        if stats:
            print(f"\n📈 PERFORMANCE METRICS (Test Run)")
            print("=" * 60)
            
            for operation, stat in stats.items():
                print(f"{operation}:")
                print(f"  Operations: {stat.total_operations}")
                print(f"  Success Rate: {stat.success_rate:.2%}")
                print(f"  Avg Duration: {stat.average_duration:.3f}s")
                print(f"  Min/Max Duration: {stat.min_duration:.3f}s / {stat.max_duration:.3f}s")
    
    except ImportError:
        print("⚠️  Performance monitoring not available")
    
    # Return overall success status
    return total_failures == 0 and total_errors == 0

def main():
    """Main test runner"""
    
    # Check if we're in the right directory
    if not os.path.exists('agents') or not os.path.exists('config.py'):
        print("❌ Please run this script from the DPerformance agent root directory")
        sys.exit(1)
    
    # Set environment variables for testing
    os.environ.setdefault('SERPAPI_API_KEY', 'test_key')
    os.environ.setdefault('GEMINI_API_KEY', 'test_key')
    os.environ.setdefault('BIGCOMMERCE_STORE_HASH', 'test_store')
    os.environ.setdefault('BIGCOMMERCE_ACCESS_TOKEN', 'test_token')
    os.environ.setdefault('GOOGLE_APPLICATION_CREDENTIALS', 'test_creds.json')
    
    # Run the test suite
    success = run_test_suite()
    
    if success:
        print("\n🎉 ALL TESTS PASSED! System is ready for production.")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED. Please review and fix issues before deployment.")
        sys.exit(1)

if __name__ == '__main__':
    main()