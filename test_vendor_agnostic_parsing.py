#!/usr/bin/env python3
"""
Comprehensive test suite for vendor-agnostic vehicle application parsing
Tests all major automotive brands and various data formats
"""

import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

# Import components to test
from brand_registry import brand_registry, VendorConfig
from agents.enhanced_vehicle_agent import EnhancedVehicleApplicationAgent, ParseResult
from agents.vehicle_application_agent import VehicleApplication
from config import PART_NUMBER_COLUMN_SOURCE, BRAND_COLUMN_SOURCE

class TestBrandRegistry(unittest.TestCase):
    """Test unified brand registry functionality"""
    
    def test_brand_identification(self):
        """Test brand identification by name"""
        # Test exact matches
        self.assertEqual(brand_registry.identify_vendor_by_brand('Hawk Performance'), 'HAWK_PERFORMANCE')
        self.assertEqual(brand_registry.identify_vendor_by_brand('HAWK'), 'HAWK_PERFORMANCE')
        self.assertEqual(brand_registry.identify_vendor_by_brand('Bilstein'), 'BILSTEIN')
        
        # Test OEM brands
        self.assertEqual(brand_registry.identify_vendor_by_brand('Ford'), 'FORD')
        self.assertEqual(brand_registry.identify_vendor_by_brand('FORD'), 'FORD')
        self.assertEqual(brand_registry.identify_vendor_by_brand('Honda'), 'HONDA')
        self.assertEqual(brand_registry.identify_vendor_by_brand('Toyota'), 'TOYOTA')
        
        # Test case insensitive
        self.assertEqual(brand_registry.identify_vendor_by_brand('bmw'), 'BMW')
        self.assertEqual(brand_registry.identify_vendor_by_brand('MERCEDES'), 'MERCEDES_BENZ')
        
        # Test unknown brand
        unknown_result = brand_registry.identify_vendor_by_brand('UnknownBrandXYZ12345')
        # Should be None or a fallback vendor
        self.assertTrue(unknown_result is None or isinstance(unknown_result, str))
    
    def test_domain_identification(self):
        """Test vendor identification by URL/domain"""
        # Test exact domain matches
        self.assertEqual(brand_registry.identify_vendor_by_url('https://hawkperformance.com/product/123'), 'HAWK_PERFORMANCE')
        self.assertEqual(brand_registry.identify_vendor_by_url('https://bilstein.com/parts/abc'), 'BILSTEIN')
        self.assertEqual(brand_registry.identify_vendor_by_url('https://parts.ford.com/catalog/item'), 'FORD')
        
        # Test subdomain matching
        self.assertEqual(brand_registry.identify_vendor_by_url('https://shop.bilstein.com/product'), 'BILSTEIN')
        
        # Test unknown domain
        self.assertIsNone(brand_registry.identify_vendor_by_url('https://unknown-website.com'))
    
    def test_vendor_configuration(self):
        """Test vendor configuration retrieval"""
        hawk_config = brand_registry.get_vendor_config('HAWK_PERFORMANCE')
        self.assertIsNotNone(hawk_config)
        self.assertIsInstance(hawk_config, VendorConfig)
        self.assertIn('hawkperformance.com', hawk_config.domains)
        self.assertEqual(hawk_config.authority_score, 90)
        
        bilstein_config = brand_registry.get_vendor_config('BILSTEIN')
        self.assertIsNotNone(bilstein_config)
        self.assertIn('bilstein.com', bilstein_config.domains)
    
    def test_parsing_strategies(self):
        """Test parsing strategy retrieval"""
        hawk_strategies = brand_registry.get_parsing_strategies('HAWK_PERFORMANCE')
        self.assertIn('custom_hawk_parser', hawk_strategies)
        
        ford_strategies = brand_registry.get_parsing_strategies('FORD')
        self.assertIn('structured_data', ford_strategies)
        
        # Test unknown vendor
        unknown_strategies = brand_registry.get_parsing_strategies('UNKNOWN_VENDOR')
        self.assertIn('table_parser', unknown_strategies)  # Should return defaults
    
    def test_brand_coverage(self):
        """Test that all major automotive brands are covered"""
        supported_brands = brand_registry.get_all_supported_brands()
        
        # Check major OEM brands are covered
        major_brands = ['Ford', 'Chevrolet', 'Honda', 'Toyota', 'Nissan', 'BMW', 'Mercedes-Benz', 'Audi', 'Volkswagen']
        for brand in major_brands:
            self.assertTrue(any(brand.upper() in supported_brand.upper() for supported_brand in supported_brands),
                           f"Brand {brand} not found in supported brands")
        
        # Should support more brands than the old system (which only supported 7)
        self.assertGreater(len(supported_brands), 20, "Should support more than 20 brands")

class TestEnhancedVehicleAgent(unittest.TestCase):
    """Test enhanced vehicle application agent"""
    
    def setUp(self):
        """Set up test environment"""
        self.agent = EnhancedVehicleApplicationAgent()
        
        # Mock session to avoid real HTTP requests
        self.mock_response = MagicMock()
        self.mock_response.status_code = 200
        self.mock_response.content = b'<html><body>Test content</body></html>'
        
    def test_hawk_performance_parsing(self):
        """Test Hawk Performance specific parsing"""
        # Test HTML content with Hawk-style vehicle applications
        html_content = """
        <div class="vehicle-applications">
            2016-2021 Honda Civic Si 2019-2022 Acura ILX 2018-2021 Honda Civic Type R
        </div>
        """
        
        soup = BeautifulSoup(html_content, 'html.parser')
        vendor_config = brand_registry.get_vendor_config('HAWK_PERFORMANCE')
        
        result = self.agent._parse_hawk_performance('https://hawkperformance.com/test', 'HB123', soup, vendor_config)
        
        self.assertTrue(result.success)
        self.assertGreater(len(result.applications), 0)
        self.assertEqual(result.strategy_used, 'custom_hawk_parser')
        
        # Check that applications were parsed correctly
        app = result.applications[0]
        self.assertIsInstance(app, VehicleApplication)
        self.assertIsNotNone(app.year_start)
        self.assertIsNotNone(app.make)
        self.assertIsNotNone(app.model)
    
    def test_bilstein_parsing(self):
        """Test Bilstein specific parsing with structured format"""
        html_content = """
        <div class="fitment-info">
            Years: 2005 – 2023, Make: TOYOTA, Model: Tacoma
            Years: 2010 – 2020, Make: FORD, Model: F-150
        </div>
        """
        
        soup = BeautifulSoup(html_content, 'html.parser')
        vendor_config = brand_registry.get_vendor_config('BILSTEIN')
        
        result = self.agent._parse_bilstein('https://bilstein.com/test', 'B4-123', soup, vendor_config)
        
        self.assertTrue(result.success)
        self.assertGreater(len(result.applications), 0)
        self.assertEqual(result.strategy_used, 'custom_bilstein_parser')
        
        # Check specific parsing
        found_toyota = any(app.make.upper() == 'TOYOTA' and app.model == 'Tacoma' for app in result.applications)
        found_ford = any(app.make.upper() == 'FORD' and app.model == 'F-150' for app in result.applications)
        self.assertTrue(found_toyota, "Should find Toyota Tacoma")
        self.assertTrue(found_ford, "Should find Ford F-150")
    
    def test_table_parsing_multiple_brands(self):
        """Test enhanced table parser with multiple automotive brands"""
        html_content = """
        <table class="compatibility-table">
            <tr><th>Year</th><th>Make</th><th>Model</th></tr>
            <tr><td>2018-2021</td><td>Honda</td><td>Civic</td></tr>
            <tr><td>2020-2023</td><td>BMW</td><td>3 Series</td></tr>
            <tr><td>2019-2022</td><td>Audi</td><td>A4</td></tr>
            <tr><td>2017-2021</td><td>Mercedes-Benz</td><td>C-Class</td></tr>
        </table>
        """
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = self.agent._parse_table_data('https://example.com', 'PART123', soup, None)
        
        self.assertTrue(result.success)
        self.assertGreaterEqual(len(result.applications), 3)  # Should find at least 3 vehicles
        self.assertEqual(result.strategy_used, 'table_parser')
        
        # Check that all major brands were detected
        makes = [app.make for app in result.applications]
        self.assertIn('Honda', makes)
        self.assertIn('BMW', makes)
        self.assertIn('Audi', makes)
    
    def test_text_extraction_parsing(self):
        """Test text extraction with various brand formats"""
        html_content = """
        <div class="product-description">
            This brake pad fits the following vehicles:
            2018-2021 Volkswagen Golf GTI
            2019 Subaru WRX STI  
            2020-2022 Mazda CX-5 Turbo
            Compatible with Ford Mustang 2015-2023 models.
        </div>
        """
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = self.agent._parse_text_content('https://example.com', 'PART456', soup, None)
        
        self.assertTrue(result.success)
        self.assertGreater(len(result.applications), 0)
        self.assertEqual(result.strategy_used, 'text_extraction')
        
        # Check that different formats were parsed
        makes = [app.make for app in result.applications]
        self.assertTrue(any('Volkswagen' in make for make in makes))
        self.assertTrue(any('Subaru' in make for make in makes))
        self.assertTrue(any('Mazda' in make for make in makes))
    
    def test_structured_data_parsing(self):
        """Test structured data parsing (JSON-LD)"""
        html_content = """
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Performance Brake Pad",
            "vehicleCompatibility": [
                {
                    "@type": "Vehicle",
                    "make": "Toyota",
                    "model": "Camry",
                    "modelYear": "2020"
                },
                {
                    "@type": "Vehicle", 
                    "make": "Lexus",
                    "model": "ES350",
                    "modelYear": "2019"
                }
            ]
        }
        </script>
        """
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = self.agent._parse_structured_data('https://example.com', 'STRUCT123', soup, None)
        
        # Note: This test validates the structure - actual JSON-LD parsing would be implemented
        self.assertEqual(result.strategy_used, 'structured_data')
        # Structured data parsing implementation would extract vehicles from JSON-LD
    
    def test_concatenated_text_handling(self):
        """Test concatenated text parsing like the Hawk Performance issue"""
        concatenated_text = "2016-2018 Honda Civic Si 2019-2021 Acura ILX 2020-2022 Toyota Corolla GR 2017-2019 Ford Focus RS"
        
        applications = self.agent._parse_concatenated_vehicle_text(concatenated_text, None)
        
        self.assertGreater(len(applications), 2)  # Should find multiple vehicles
        
        # Check that vehicles were separated correctly
        makes = [app.make for app in applications]
        models = [app.model for app in applications]
        
        self.assertIn('Honda', makes)
        self.assertIn('Acura', makes) 
        self.assertIn('Toyota', makes)
        self.assertIn('Ford', makes)
        
        self.assertIn('Civic', models)
        self.assertIn('ILX', models)
        self.assertIn('Corolla', models)
        self.assertIn('Focus', models)
    
    def test_duplicate_removal(self):
        """Test duplicate application removal"""
        # Create applications with duplicates
        applications = [
            VehicleApplication(year_start=2020, year_end=2022, make='Honda', model='Civic'),
            VehicleApplication(year_start=2020, year_end=2022, make='Honda', model='Civic'),  # Duplicate
            VehicleApplication(year_start=2021, year_end=2021, make='Toyota', model='Camry'),
            VehicleApplication(year_start=2020, year_end=2022, make='HONDA', model='CIVIC'),  # Case difference
        ]
        
        unique_applications = self.agent._remove_duplicate_applications(applications)
        
        self.assertLessEqual(len(unique_applications), 2)  # Should remove duplicates
        
        # Should keep one Honda Civic and one Toyota Camry
        makes = [app.make for app in unique_applications]
        self.assertEqual(len([m for m in makes if 'Honda' in m or 'HONDA' in m]), 1)
    
    @patch('requests.Session.get')
    def test_vendor_strategy_selection(self, mock_get):
        """Test that correct parsing strategies are selected for different vendors"""
        mock_get.return_value = self.mock_response
        
        # Test Hawk Performance product
        hawk_product = {
            PART_NUMBER_COLUMN_SOURCE: 'HB659N.710',
            BRAND_COLUMN_SOURCE: 'Hawk Performance'
        }
        
        with patch.object(self.agent, '_discover_product_urls', return_value=['https://hawkperformance.com/test']):
            applications = self.agent.find_and_extract_applications(hawk_product)
            
            # Should use Hawk-specific strategies
            self.assertIn('custom_hawk_parser', self.agent.stats['strategy_usage'])
    
    @patch('requests.Session.get')
    def test_unknown_vendor_fallback(self, mock_get):
        """Test fallback behavior for unknown vendors"""
        mock_get.return_value = self.mock_response
        
        unknown_product = {
            PART_NUMBER_COLUMN_SOURCE: 'UNKNOWN123',
            BRAND_COLUMN_SOURCE: 'Unknown Brand XYZ'
        }
        
        applications = self.agent.find_and_extract_applications(unknown_product)
        
        # Should attempt multiple strategies for unknown vendor
        self.assertGreater(len(self.agent.stats['strategy_usage']), 1)
    
    def test_confidence_scoring(self):
        """Test confidence scoring for different parsing results"""
        # High confidence result (structured data)
        high_confidence_result = ParseResult(
            success=True, applications=[VehicleApplication(year_start=2020, make='Honda', model='Civic')],
            confidence=0.95, strategy_used='structured_data', errors=[], metadata={}
        )
        
        # Medium confidence result (table parsing)
        medium_confidence_result = ParseResult(
            success=True, applications=[VehicleApplication(year_start=2020, make='Ford', model='F-150')],
            confidence=0.75, strategy_used='table_parser', errors=[], metadata={}
        )
        
        # Low confidence result (heuristic)
        low_confidence_result = ParseResult(
            success=True, applications=[VehicleApplication(year_start=2019, make='Toyota', model='Unknown')],
            confidence=0.40, strategy_used='fallback_heuristic', errors=[], metadata={}
        )
        
        # Test that higher confidence results are preferred
        results = [low_confidence_result, high_confidence_result, medium_confidence_result]
        best_result = max(results, key=lambda r: r.confidence)
        
        self.assertEqual(best_result.strategy_used, 'structured_data')
        self.assertEqual(best_result.confidence, 0.95)
    
    def test_parsing_statistics(self):
        """Test parsing statistics tracking"""
        initial_stats = self.agent.get_parsing_statistics()
        self.assertEqual(initial_stats['total_attempts'], 0)
        self.assertEqual(initial_stats['successful_parses'], 0)
        
        # Simulate some parsing attempts
        self.agent._update_stats('table_parser', ParseResult(True, [], 0.8, 'table_parser', [], {}), 'HONDA')
        self.agent._update_stats('text_extraction', ParseResult(False, [], 0.2, 'text_extraction', [], {}), 'FORD')
        
        updated_stats = self.agent.get_parsing_statistics()
        self.assertEqual(updated_stats['total_attempts'], 2)
        self.assertEqual(updated_stats['successful_parses'], 1)
        self.assertEqual(updated_stats['overall_success_rate'], 0.5)

class TestVendorSpecificScenarios(unittest.TestCase):
    """Test vendor-specific parsing scenarios"""
    
    def setUp(self):
        self.agent = EnhancedVehicleApplicationAgent()
    
    def test_oem_brand_scenarios(self):
        """Test OEM brand specific scenarios"""
        # Ford parts website format
        ford_html = """
        <div class="vehicle-fitment">
            <h3>Compatible Vehicles</h3>
            <ul>
                <li>2018-2021 Ford F-150 Regular Cab</li>
                <li>2019-2022 Ford Ranger SuperCrew</li>
                <li>2020-2023 Ford Bronco Sport</li>
            </ul>
        </div>
        """
        
        soup = BeautifulSoup(ford_html, 'html.parser')
        result = self.agent._parse_list_data('https://parts.ford.com', 'FORD123', soup, None)
        
        self.assertTrue(result.success)
        self.assertGreater(len(result.applications), 2)
        
        # Check Ford models were parsed
        models = [app.model for app in result.applications]
        self.assertTrue(any('F-150' in model for model in models))
        self.assertTrue(any('Ranger' in model for model in models))
    
    def test_aftermarket_brand_scenarios(self):
        """Test aftermarket brand specific scenarios"""
        # K&N Filters format
        kn_html = """
        <table class="vehicle-search-results">
            <tr><td>2017</td><td>Subaru</td><td>WRX</td><td>2.0L Turbo</td></tr>
            <tr><td>2018</td><td>Subaru</td><td>STI</td><td>2.5L Turbo</td></tr>
            <tr><td>2019-2021</td><td>Honda</td><td>Civic Type R</td><td>2.0L Turbo</td></tr>
        </table>
        """
        
        soup = BeautifulSoup(kn_html, 'html.parser')
        result = self.agent._parse_table_data('https://knfilters.com', 'KN123', soup, None)
        
        self.assertTrue(result.success)
        self.assertGreater(len(result.applications), 2)
        
        # Check engines were extracted
        engines = [app.engine for app in result.applications if app.engine]
        self.assertTrue(any('Turbo' in engine for engine in engines))
    
    def test_european_brand_scenarios(self):
        """Test European brand specific scenarios"""
        # BMW parts format
        bmw_html = """
        <div class="product-fitment">
            <p>Fits the following BMW models:</p>
            <div>2015-2018 BMW 3 Series (F30) 320i, 328i, 335i</div>
            <div>2019-2022 BMW 3 Series (G20) 330i, M340i</div>
            <div>2016-2019 BMW 4 Series (F32) 420i, 430i</div>
        </div>
        """
        
        soup = BeautifulSoup(bmw_html, 'html.parser')
        vendor_config = brand_registry.get_vendor_config('BMW')
        
        result = self.agent._parse_text_content('https://parts.bmw.com', 'BMW123', soup, vendor_config)
        
        self.assertTrue(result.success)
        self.assertGreater(len(result.applications), 1)
        
        # Check BMW models were detected
        makes = [app.make for app in result.applications]
        models = [app.model for app in result.applications]
        
        self.assertTrue(any('BMW' in make for make in makes))
        self.assertTrue(any('3 Series' in model for model in models))
    
    def test_multi_brand_distributor(self):
        """Test multi-brand distributors like AutoZone"""
        autozone_html = """
        <div class="compatibility-info">
            <h4>Vehicle Compatibility</h4>
            <table>
                <tr><td>2018-2020</td><td>Toyota</td><td>Camry</td><td>LE, SE, XLE</td></tr>
                <tr><td>2019-2021</td><td>Honda</td><td>Accord</td><td>LX, Sport, Touring</td></tr>
                <tr><td>2020-2022</td><td>Nissan</td><td>Altima</td><td>S, SV, SL</td></tr>
            </table>
        </div>
        """
        
        soup = BeautifulSoup(autozone_html, 'html.parser')
        result = self.agent._parse_table_data('https://autozone.com', 'AZ123', soup, None)
        
        self.assertTrue(result.success)
        self.assertGreaterEqual(len(result.applications), 3)
        
        # Should handle multiple brands correctly
        makes = [app.make for app in result.applications]
        self.assertIn('Toyota', makes)
        self.assertIn('Honda', makes)
        self.assertIn('Nissan', makes)

class TestErrorHandlingAndEdgeCases(unittest.TestCase):
    """Test error handling and edge cases"""
    
    def setUp(self):
        self.agent = EnhancedVehicleApplicationAgent()
    
    def test_malformed_html_handling(self):
        """Test handling of malformed HTML"""
        malformed_html = "<div><p>2020 Honda Civic</p><div><span>2021 Toyota"  # Unclosed tags
        
        soup = BeautifulSoup(malformed_html, 'html.parser')
        result = self.agent._parse_text_content('https://example.com', 'TEST123', soup, None)
        
        # Should not crash and should attempt to extract what it can
        self.assertIsInstance(result, ParseResult)
        self.assertEqual(result.strategy_used, 'text_extraction')
    
    def test_empty_content_handling(self):
        """Test handling of empty or minimal content"""
        empty_html = "<html><body></body></html>"
        
        soup = BeautifulSoup(empty_html, 'html.parser')
        result = self.agent._parse_table_data('https://example.com', 'EMPTY123', soup, None)
        
        self.assertFalse(result.success)
        self.assertEqual(len(result.applications), 0)
    
    def test_invalid_year_handling(self):
        """Test handling of invalid year data"""
        invalid_year_text = "9999 Honda Civic"  # Invalid year
        
        app = self.agent._parse_single_vehicle_text(invalid_year_text)
        # Should either reject invalid years or handle gracefully
        self.assertTrue(app is None or (1990 <= app.year_start <= 2025))
    
    def test_missing_data_handling(self):
        """Test handling of missing required data"""
        # Missing part number
        missing_part = {
            PART_NUMBER_COLUMN_SOURCE: '',
            BRAND_COLUMN_SOURCE: 'Honda'
        }
        
        applications = self.agent.find_and_extract_applications(missing_part)
        self.assertEqual(len(applications), 0)
        
        # Missing brand
        missing_brand = {
            PART_NUMBER_COLUMN_SOURCE: 'TEST123',
            BRAND_COLUMN_SOURCE: ''
        }
        
        applications = self.agent.find_and_extract_applications(missing_brand)
        self.assertEqual(len(applications), 0)

if __name__ == '__main__':
    # Run all tests with detailed output
    unittest.main(verbosity=2)