#!/usr/bin/env python3
"""
Comprehensive test suite for the monitoring and logging system
Tests performance monitoring, structured logging, and dashboard functionality
"""

import unittest
import tempfile
import shutil
import os
import time
import json
from unittest.mock import patch, MagicMock

# Import monitoring components
from monitoring.performance_monitor import (
    performance_monitor, OperationTimer, MetricPoint, 
    PerformanceStats, monitor_operation
)
from monitoring.logging_system import (
    StructuredLogger, get_logger, LogContext, log_operation
)

class TestPerformanceMonitor(unittest.TestCase):
    """Test performance monitoring functionality"""
    
    def setUp(self):
        """Set up test environment"""
        # Clear performance monitor state
        performance_monitor.metrics_history.clear()
        performance_monitor.active_operations.clear()
    
    def test_operation_timer_success(self):
        """Test successful operation timing"""
        with OperationTimer('test_agent', 'test_operation') as timer:
            time.sleep(0.1)  # Simulate work
            timer.set_metadata('test_key', 'test_value')
        
        # Check metrics were recorded
        self.assertEqual(len(performance_monitor.metrics_history), 1)
        
        metric = performance_monitor.metrics_history[0]
        self.assertEqual(metric.agent, 'test_agent')
        self.assertEqual(metric.operation, 'test_operation')
        self.assertTrue(metric.success)
        self.assertGreater(metric.duration, 0.05)  # Should be around 0.1 seconds
        self.assertEqual(metric.metadata['test_key'], 'test_value')
    
    def test_operation_timer_failure(self):
        """Test operation timing with exception"""
        try:
            with OperationTimer('test_agent', 'test_operation') as timer:
                timer.set_metadata('test_key', 'test_value')
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Check metrics were recorded with failure
        self.assertEqual(len(performance_monitor.metrics_history), 1)
        
        metric = performance_monitor.metrics_history[0]
        self.assertEqual(metric.agent, 'test_agent')
        self.assertEqual(metric.operation, 'test_operation')
        self.assertFalse(metric.success)
        self.assertIn('error', metric.metadata)
    
    def test_performance_stats_calculation(self):
        """Test performance statistics calculation"""
        # Add some test metrics
        for i in range(10):
            success = i < 8  # 80% success rate
            duration = 0.1 + (i * 0.01)  # Varying durations
            
            performance_monitor.record_instant_metric(
                'test_agent', 'test_operation', success, duration,
                {'iteration': i}
            )
        
        # Get performance stats
        stats = performance_monitor.get_performance_stats()
        
        self.assertIn('test_agent_test_operation', stats)
        stat = stats['test_agent_test_operation']
        
        self.assertEqual(stat.total_operations, 10)
        self.assertEqual(stat.successful_operations, 8)
        self.assertEqual(stat.failed_operations, 2)
        self.assertEqual(stat.success_rate, 0.8)
        self.assertGreater(stat.average_duration, 0.1)
        self.assertEqual(stat.min_duration, 0.1)
        self.assertGreater(stat.max_duration, 0.1)
    
    def test_recent_failures(self):
        """Test recent failures tracking"""
        # Add some successful and failed operations
        performance_monitor.record_instant_metric('test_agent', 'op1', True, 0.1)
        performance_monitor.record_instant_metric('test_agent', 'op2', False, 0.2, {'error': 'Test error'})
        performance_monitor.record_instant_metric('test_agent', 'op3', True, 0.1)
        performance_monitor.record_instant_metric('test_agent', 'op4', False, 0.3, {'error': 'Another error'})
        
        failures = performance_monitor.get_recent_failures(hours=24)
        
        self.assertEqual(len(failures), 2)
        self.assertEqual(failures[0].operation, 'op4')  # Most recent first
        self.assertEqual(failures[1].operation, 'op2')
        
        for failure in failures:
            self.assertFalse(failure.success)
            self.assertIn('error', failure.metadata)
    
    def test_monitor_operation_decorator(self):
        """Test operation monitoring decorator"""
        @monitor_operation('test_agent', 'decorated_operation', {'source': 'decorator'})
        def test_function(should_fail=False):
            if should_fail:
                raise RuntimeError("Test failure")
            return "success"
        
        # Test successful operation
        result = test_function()
        self.assertEqual(result, "success")
        
        # Test failed operation
        with self.assertRaises(RuntimeError):
            test_function(should_fail=True)
        
        # Check metrics
        self.assertEqual(len(performance_monitor.metrics_history), 2)
        
        success_metric = performance_monitor.metrics_history[0]
        self.assertTrue(success_metric.success)
        self.assertEqual(success_metric.metadata['source'], 'decorator')
        
        failure_metric = performance_monitor.metrics_history[1]
        self.assertFalse(failure_metric.success)
        self.assertIn('error', failure_metric.metadata)

class TestStructuredLogger(unittest.TestCase):
    """Test structured logging functionality"""
    
    def setUp(self):
        """Set up temporary log directory"""
        self.temp_dir = tempfile.mkdtemp()
        self.logger = StructuredLogger('test_logger', self.temp_dir)
    
    def tearDown(self):
        """Clean up temporary files"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_basic_logging_levels(self):
        """Test all logging levels"""
        self.logger.debug("Debug message")
        self.logger.info("Info message")
        self.logger.warning("Warning message")
        self.logger.error("Error message")
        self.logger.critical("Critical message")
        self.logger.success("Success message")
        self.logger.performance("Performance message", duration=1.5)
        self.logger.business("Business message")
        
        # Check log files were created
        log_files = os.listdir(self.temp_dir)
        self.assertTrue(any('test_logger.log' in f for f in log_files))
        self.assertTrue(any('test_logger_structured.jsonl' in f for f in log_files))
    
    def test_context_management(self):
        """Test logging context management"""
        # Set context
        self.logger.set_context(user_id='123', session_id='abc')
        
        # Log message
        self.logger.info("Test message with context")
        
        # Clear context
        self.logger.clear_context()
        
        # Check context was included (would need to parse log file in real test)
        context = self.logger._get_context()
        self.assertEqual(len(context), 0)  # Should be cleared
    
    def test_log_context_manager(self):
        """Test LogContext context manager"""
        with LogContext(self.logger, operation='test_op', request_id='req_123'):
            self.logger.info("Message within context")
            
            # Check context is set
            context = self.logger._get_context()
            self.assertEqual(context['operation'], 'test_op')
            self.assertEqual(context['request_id'], 'req_123')
        
        # Context should be cleared after exiting
        context = self.logger._get_context()
        self.assertEqual(len(context), 0)
    
    def test_log_operation_decorator(self):
        """Test log operation decorator"""
        @log_operation('test_logger', 'decorated_function')
        def test_function(should_fail=False):
            if should_fail:
                raise ValueError("Test error")
            return "success"
        
        # Test successful operation
        result = test_function()
        self.assertEqual(result, "success")
        
        # Test failed operation
        with self.assertRaises(ValueError):
            test_function(should_fail=True)
        
        # Check log files exist (detailed content checking would require parsing)
        log_files = os.listdir(self.temp_dir)
        self.assertTrue(any('test_logger.log' in f for f in log_files))

class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios combining monitoring and logging"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        performance_monitor.metrics_history.clear()
        performance_monitor.active_operations.clear()
    
    def tearDown(self):
        """Clean up"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_pipeline_simulation(self):
        """Test complete pipeline simulation with monitoring"""
        logger = StructuredLogger('pipeline_test', self.temp_dir)
        
        def simulate_image_sourcing(sku):
            """Simulate image sourcing operation"""
            with LogContext(logger, operation='image_sourcing', sku=sku):
                with OperationTimer('image_agent', 'image_search', {'sku': sku}):
                    logger.info(f"Starting image search for SKU: {sku}")
                    time.sleep(0.05)  # Simulate work
                    
                    # Simulate occasional failures
                    if sku == 'FAIL_SKU':
                        logger.error("Image sourcing failed")
                        raise RuntimeError("Image not found")
                    
                    logger.success(f"Found images for SKU: {sku}")
                    return [f"image_{sku}.jpg"]
        
        def simulate_vehicle_apps(sku):
            """Simulate vehicle application extraction"""
            with LogContext(logger, operation='vehicle_apps', sku=sku):
                with OperationTimer('vehicle_agent', 'application_extraction', {'sku': sku}):
                    logger.info(f"Extracting vehicle applications for SKU: {sku}")
                    time.sleep(0.03)  # Simulate work
                    logger.success(f"Found 3 applications for SKU: {sku}")
                    return ["2020-2023 Honda Civic", "2019-2022 Acura ILX", "2021-2023 Honda Accord"]
        
        def simulate_bigcommerce_upload(sku):
            """Simulate BigCommerce upload"""
            with LogContext(logger, operation='bigcommerce_upload', sku=sku):
                with OperationTimer('bigcommerce_agent', 'product_upload', {'sku': sku}):
                    logger.info(f"Uploading product to BigCommerce: {sku}")
                    time.sleep(0.02)  # Simulate work
                    logger.success(f"Product uploaded successfully: {sku}")
                    return {"id": f"bc_{sku}", "status": "active"}
        
        # Simulate processing multiple products
        test_skus = ["ABC123", "DEF456", "FAIL_SKU", "GHI789"]
        results = []
        
        for sku in test_skus:
            try:
                logger.business(f"Processing product: {sku}")
                
                # Process each pipeline step
                images = simulate_image_sourcing(sku)
                apps = simulate_vehicle_apps(sku)  # Will only run if image sourcing succeeds
                product = simulate_bigcommerce_upload(sku)
                
                results.append({"sku": sku, "status": "success", "product_id": product["id"]})
                logger.performance(f"Successfully processed {sku}")
                
            except Exception as e:
                results.append({"sku": sku, "status": "failed", "error": str(e)})
                logger.error(f"Failed to process {sku}: {e}")
        
        # Verify results
        self.assertEqual(len(results), 4)
        
        # Check success/failure counts
        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] == "failed"]
        
        self.assertEqual(len(successful), 3)  # ABC123, DEF456, GHI789
        self.assertEqual(len(failed), 1)     # FAIL_SKU
        
        # Check performance metrics were recorded
        stats = performance_monitor.get_performance_stats()
        
        # Should have metrics for each agent/operation combination
        expected_keys = [
            'image_agent_image_search',
            'vehicle_agent_application_extraction', 
            'bigcommerce_agent_product_upload'
        ]
        
        for key in expected_keys:
            if key == 'image_agent_image_search':
                # Image agent should have 1 failure (FAIL_SKU)
                self.assertIn(key, stats)
                self.assertEqual(stats[key].failed_operations, 1)
            else:
                # Other agents should have no failures (they don't run after image failure)
                if key in stats:
                    self.assertEqual(stats[key].failed_operations, 0)
        
        # Check log files were created
        log_files = os.listdir(self.temp_dir)
        self.assertTrue(any('pipeline_test.log' in f for f in log_files))
        self.assertTrue(any('pipeline_test_structured.jsonl' in f for f in log_files))

if __name__ == '__main__':
    # Run all tests
    unittest.main(verbosity=2)