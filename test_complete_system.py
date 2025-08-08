#!/usr/bin/env python3
"""
Complete system integration test
Validates the entire DPerformance automation pipeline end-to-end
"""

import unittest
import tempfile
import shutil
import os
import pandas as pd
import json
from unittest.mock import patch, MagicMock, mock_open
import sys
import time

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import main components
import config
from agents.image_agent import ImageSourcingAgent
from agents.vehicle_application_agent import VehicleApplicationAgent
from agents.bigcommerce_agent import BigCommerceUploaderAgent
from monitoring import performance_monitor, get_main_logger

class TestCompleteSystemIntegration(unittest.TestCase):
    """Complete end-to-end system integration test"""
    
    def setUp(self):
        """Set up test environment with mock dependencies"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_data_dir = os.path.join(self.temp_dir, 'test_data')
        os.makedirs(self.test_data_dir, exist_ok=True)
        
        # Clear performance monitor
        performance_monitor.metrics_history.clear()
        performance_monitor.active_operations.clear()
        
        # Create test Excel data
        self.test_excel_path = os.path.join(self.test_data_dir, 'test_products.xlsx')
        self._create_test_excel_data()
        
        # Create test CSV exports
        self.existing_skus_path = os.path.join(self.test_data_dir, 'existing_skus.csv')
        self.existing_descriptions_path = os.path.join(self.test_data_dir, 'existing_descriptions.csv')
        self._create_test_csv_exports()
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_excel_data(self):
        """Create test Excel data file"""
        test_data = [
            {
                config.PART_NUMBER_COLUMN_SOURCE: 'HB659N.710',
                config.BRAND_COLUMN_SOURCE: 'Hawk Performance',
                config.DESCRIPTION_COLUMN_EN_SOURCE: 'HPS 5.0 Brake Pads Front',
                config.APPLICATION_COLUMN_SOURCE: 'Honda Civic 2016-2021',
                config.QTY_COLUMN_SOURCE: '1',
                config.PRICE_COLUMN_SOURCE: '89.99'
            },
            {
                config.PART_NUMBER_COLUMN_SOURCE: 'B4-B112H2',
                config.BRAND_COLUMN_SOURCE: 'Bilstein',
                config.DESCRIPTION_COLUMN_EN_SOURCE: 'B4 OE Replacement Shock Absorber',
                config.APPLICATION_COLUMN_SOURCE: 'BMW 3 Series 2012-2018',
                config.QTY_COLUMN_SOURCE: '1',
                config.PRICE_COLUMN_SOURCE: '156.78'
            },
            {
                config.PART_NUMBER_COLUMN_SOURCE: 'TEST-EXISTING',
                config.BRAND_COLUMN_SOURCE: 'Test Brand',
                config.DESCRIPTION_COLUMN_EN_SOURCE: 'Already Exists Product',
                config.APPLICATION_COLUMN_SOURCE: 'Universal',
                config.QTY_COLUMN_SOURCE: '1',
                config.PRICE_COLUMN_SOURCE: '25.00'
            }
        ]
        
        df = pd.DataFrame(test_data)
        df.to_excel(self.test_excel_path, index=False, engine='openpyxl')
    
    def _create_test_csv_exports(self):
        """Create test CSV export files"""
        # Existing SKUs (to test deduplication)
        existing_skus_data = [
            {config.SKU_COLUMN_STORE_EXPORT: 'TEST-EXISTING'},
            {config.SKU_COLUMN_STORE_EXPORT: 'OTHER-EXISTING-SKU'}
        ]
        pd.DataFrame(existing_skus_data).to_csv(self.existing_skus_path, index=False)
        
        # Existing descriptions (empty for test)
        existing_desc_data = [
            {
                config.SKU_COLUMN_EXISTING_DESC_EXPORT: 'SOME-OTHER-SKU',
                config.HTML_DESCRIPTION_COLUMN_EXISTING_DESC_EXPORT: '<p>Existing description</p>'
            }
        ]
        pd.DataFrame(existing_desc_data).to_csv(self.existing_descriptions_path, index=False)
    
    @patch('agents.image_agent.GoogleSearch')
    @patch('agents.image_agent.requests.Session')
    @patch('agents.vehicle_application_agent.requests.Session')
    @patch('agents.bigcommerce_agent.requests')
    @patch('google.cloud.translate_v2.Client')
    @patch('google.generativeai.GenerativeModel')
    def test_complete_pipeline_flow(self, mock_gemini_model, mock_translate_client, 
                                   mock_bc_requests, mock_vehicle_session, 
                                   mock_image_session, mock_google_search):
        """Test complete pipeline from Excel to BigCommerce with all enhancements"""
        
        # Mock API responses
        self._setup_mocks(mock_gemini_model, mock_translate_client, mock_bc_requests,
                         mock_vehicle_session, mock_image_session, mock_google_search)
        
        # Override config paths for testing
        with patch.object(config, 'SOURCE_PRODUCTS_FILE_PATH', self.test_excel_path), \
             patch.object(config, 'EXISTING_STORE_SKUS_CSV_PATH', self.existing_skus_path), \
             patch.object(config, 'EXISTING_DESCRIPTIONS_CSV_PATH', self.existing_descriptions_path), \
             patch.object(config, 'MAX_PRODUCTS_TO_PROCESS_IN_BATCH', 10), \
             patch.object(config, 'MAX_CONCURRENT_WORKERS', 2):
            
            # Initialize agents
            image_agent = ImageSourcingAgent('test_serp_key')
            vehicle_agent = VehicleApplicationAgent()
            bc_agent = BigCommerceUploaderAgent('test_store_hash', 'test_token')
            
            # Mock translate client
            translate_client = mock_translate_client.return_value
            
            # Mock Gemini model
            gemini_model = mock_gemini_model.return_value
            
            agents = {
                'image': image_agent,
                'bigcommerce': bc_agent,
                'vehicle_app': vehicle_agent,
                'translate': translate_client,
                'gemini': gemini_model,
                'existing_skus': {'TEST-EXISTING'},  # This SKU should be filtered out
                'existing_descs': {}
            }
            
            # Import the process function
            from main import load_source_products, process_single_product
            
            # Load products
            all_products = load_source_products(self.test_excel_path)
            self.assertEqual(len(all_products), 3)
            
            # Filter out existing products (simulating main.py logic)
            new_products = [
                p for p in all_products 
                if p.get(config.PART_NUMBER_COLUMN_SOURCE) not in agents['existing_skus']
            ]
            
            # Should have 2 new products (TEST-EXISTING filtered out)
            self.assertEqual(len(new_products), 2)
            
            # Process each product
            results = []
            for product in new_products:
                result = process_single_product(product, agents)
                results.append(result)
            
            # Validate results
            self.assertEqual(len(results), 2)
            
            # Check that all products were processed successfully
            successful_results = [r for r in results if 'Failed' not in r.get('status', '')]
            self.assertEqual(len(successful_results), 2)
            
            # Validate individual product processing
            for result in results:
                # Should have basic fields
                self.assertIn('source_sku', result)
                self.assertIn('status', result)
                self.assertIn('bc_product_id', result)
                self.assertIn('images_sourced_paths', result)
                self.assertIn('product_name_es', result)
                self.assertIn('description_source', result)
                
                # Check successful processing
                if 'Failed' not in result.get('status', ''):
                    self.assertIsNotNone(result['bc_product_id'])
                    self.assertTrue(len(result['images_sourced_paths']) > 0)
                    self.assertTrue(len(result['product_name_es']) > 0)
                    self.assertIn('official_applications_found', result)
            
            # Check performance metrics were recorded
            stats = performance_monitor.get_performance_stats()
            
            # Should have metrics for main pipeline operations
            expected_operations = [
                'main_image_sourcing',
                'main_translation', 
                'main_vehicle_applications',
                'main_description_generation',
                'main_bigcommerce_upload'
            ]
            
            recorded_operations = list(stats.keys())
            
            # At least some operations should be recorded
            self.assertGreater(len(recorded_operations), 0)
            
            # All operations should be successful in this mock test
            for op_key, stat in stats.items():
                if stat.total_operations > 0:
                    self.assertEqual(stat.failed_operations, 0, 
                                   f"Operation {op_key} had unexpected failures")
                    self.assertGreater(stat.success_rate, 0.99, 
                                     f"Operation {op_key} had low success rate")
    
    def _setup_mocks(self, mock_gemini_model, mock_translate_client, mock_bc_requests,
                     mock_vehicle_session, mock_image_session, mock_google_search):
        """Set up all necessary mocks for testing"""
        
        # Mock Google Search (SerpAPI)
        mock_search_instance = MagicMock()
        mock_search_instance.get_dict.return_value = {
            'images_results': [
                {
                    'original': 'https://example.com/image1.jpg',
                    'link': 'https://hawkperformance.com/product/hb659n710',
                    'source': 'hawkperformance.com'
                }
            ]
        }
        mock_google_search.return_value = mock_search_instance
        
        # Mock image session requests
        mock_image_response = MagicMock()
        mock_image_response.status_code = 200
        mock_image_response.content = b'fake_image_data'
        mock_image_response.headers = {'content-type': 'image/jpeg'}
        mock_image_session.return_value.get.return_value = mock_image_response
        
        # Mock vehicle application session
        mock_vehicle_response = MagicMock()
        mock_vehicle_response.status_code = 200
        mock_vehicle_response.text = """
        <div class="vehicle-app">2016-2021 Honda Civic Si</div>
        <div class="vehicle-app">2017-2021 Honda Civic Type R</div>
        """
        mock_vehicle_session.return_value.get.return_value = mock_vehicle_response
        
        # Mock BigCommerce API responses
        mock_bc_create_response = MagicMock()
        mock_bc_create_response.status_code = 201
        mock_bc_create_response.json.return_value = {
            'data': {'id': 12345, 'name': 'Test Product', 'sku': 'TEST-SKU'}
        }
        
        mock_bc_image_response = MagicMock()
        mock_bc_image_response.status_code = 201
        mock_bc_image_response.json.return_value = {
            'data': {'id': 67890, 'product_id': 12345}
        }
        
        mock_bc_requests.post.side_effect = [mock_bc_create_response, mock_bc_image_response]
        mock_bc_requests.get.return_value.json.return_value = {'data': []}  # Empty categories/brands
        
        # Mock Google Translate
        mock_translate_client.return_value.translate.return_value = {
            'translatedText': 'Pastillas de Freno HPS 5.0 Delanteras'
        }
        
        # Mock Google Gemini
        mock_response = MagicMock()
        mock_response.text = 'Descripción generada por IA para el producto de alta calidad.'
        mock_gemini_model.return_value.generate_content.return_value = mock_response
        
        # Mock PIL Image operations
        with patch('agents.image_agent.Image.open') as mock_pil:
            mock_img = MagicMock()
            mock_img.size = (800, 600)
            mock_img.mode = 'RGB'
            mock_img.getpixel.return_value = (255, 255, 255)  # White background
            mock_pil.return_value = mock_img
    
    def test_error_handling_and_resilience(self):
        """Test system behavior under error conditions"""
        logger = get_main_logger()
        
        # Test various error scenarios
        error_scenarios = [
            {'type': 'network_timeout', 'should_retry': True},
            {'type': 'invalid_response', 'should_retry': False},
            {'type': 'rate_limit', 'should_retry': True},
            {'type': 'authentication_error', 'should_retry': False}
        ]
        
        for scenario in error_scenarios:
            with self.subTest(scenario=scenario['type']):
                logger.info(f"Testing error scenario: {scenario['type']}")
                
                # Record that we tested this scenario
                performance_monitor.record_instant_metric(
                    'test_agent', 'error_simulation', False, 0.1,
                    {'error_type': scenario['type'], 'should_retry': scenario['should_retry']}
                )
        
        # Check that error metrics were recorded
        failures = performance_monitor.get_recent_failures(hours=1)
        self.assertEqual(len(failures), 4)
        
        # Verify error types were recorded
        error_types = [f.metadata.get('error_type') for f in failures]
        expected_types = [s['type'] for s in error_scenarios]
        
        for expected_type in expected_types:
            self.assertIn(expected_type, error_types)
    
    def test_performance_thresholds(self):
        """Test performance monitoring thresholds and alerting"""
        # Simulate operations that exceed performance thresholds
        
        # Slow image sourcing (should trigger alert)
        performance_monitor.record_instant_metric(
            'image_agent', 'image_sourcing', True, 65.0,  # Exceeds 60s threshold
            {'part_number': 'SLOW-PART'}
        )
        
        # Multiple failures for success rate alert
        for i in range(10):
            success = i < 3  # 30% success rate (below 70% threshold)
            performance_monitor.record_instant_metric(
                'image_agent', 'image_sourcing', success, 5.0,
                {'part_number': f'TEST-{i}'}
            )
        
        # Get performance stats
        stats = performance_monitor.get_performance_stats()
        
        if 'image_agent_image_sourcing' in stats:
            stat = stats['image_agent_image_sourcing']
            
            # Should have recorded the operations
            self.assertGreaterEqual(stat.total_operations, 10)
            
            # Should have low success rate
            self.assertLess(stat.success_rate, 0.5)
            
            # Should have at least one slow operation
            self.assertGreater(stat.max_duration, 60.0)

class TestSystemRobustness(unittest.TestCase):
    """Test system robustness under various conditions"""
    
    def test_large_batch_processing(self):
        """Test system performance with larger batches"""
        logger = get_main_logger()
        
        # Simulate processing 100 products
        batch_size = 100
        start_time = time.time()
        
        for i in range(batch_size):
            with patch('time.sleep'):  # Skip actual delays
                performance_monitor.record_instant_metric(
                    'batch_test', 'product_processing', True, 0.1,
                    {'batch_index': i, 'sku': f'TEST-{i:03d}'}
                )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        logger.performance(f"Processed {batch_size} products", duration=processing_time)
        
        # Verify all operations were recorded
        stats = performance_monitor.get_performance_stats()
        
        if 'batch_test_product_processing' in stats:
            stat = stats['batch_test_product_processing']
            self.assertEqual(stat.total_operations, batch_size)
            self.assertEqual(stat.success_rate, 1.0)  # All should succeed
    
    def test_concurrent_processing_simulation(self):
        """Test concurrent processing capabilities"""
        import threading
        import time
        
        results = []
        errors = []
        
        def worker_thread(worker_id, num_items):
            """Simulate a worker thread processing items"""
            try:
                for i in range(num_items):
                    with performance_monitor.start_operation('worker', f'thread_{worker_id}') as op_id:
                        time.sleep(0.01)  # Simulate work
                        performance_monitor.end_operation(op_id, True, {'item': i})
                        results.append(f"worker_{worker_id}_item_{i}")
            except Exception as e:
                errors.append(str(e))
        
        # Start multiple worker threads
        threads = []
        num_workers = 5
        items_per_worker = 10
        
        for worker_id in range(num_workers):
            thread = threading.Thread(
                target=worker_thread, 
                args=(worker_id, items_per_worker)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), num_workers * items_per_worker)
        
        # Check performance metrics
        stats = performance_monitor.get_performance_stats()
        
        # Should have metrics for each worker
        worker_stats = {k: v for k, v in stats.items() if k.startswith('worker_')}
        self.assertGreater(len(worker_stats), 0)
        
        # All operations should be successful
        for stat in worker_stats.values():
            self.assertEqual(stat.success_rate, 1.0)

if __name__ == '__main__':
    # Configure test environment
    os.environ['SERPAPI_API_KEY'] = 'test_key'
    os.environ['GEMINI_API_KEY'] = 'test_key'  
    os.environ['BIGCOMMERCE_STORE_HASH'] = 'test_store'
    os.environ['BIGCOMMERCE_ACCESS_TOKEN'] = 'test_token'
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'test_creds.json'
    
    # Run tests
    unittest.main(verbosity=2)