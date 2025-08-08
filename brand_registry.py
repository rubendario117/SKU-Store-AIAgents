#!/usr/bin/env python3
"""
Unified Brand Registry for DPerformance Agent
Centralized brand detection, parsing rules, and vendor-specific configurations
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

@dataclass
class VendorConfig:
    """Configuration for a specific automotive parts vendor"""
    brand_names: List[str]  # All possible brand name variations
    domains: List[str]      # Official domains for this brand
    authority_score: int    # Authority score (0-100) for prioritization
    
    # Parsing configurations
    parsing_rules: Dict[str, Any] = field(default_factory=dict)
    common_selectors: List[str] = field(default_factory=list)  # CSS selectors for vehicle data
    text_patterns: List[str] = field(default_factory=list)     # Regex patterns for text extraction
    
    # Vehicle application patterns
    vehicle_patterns: Dict[str, str] = field(default_factory=dict)
    fallback_strategies: List[str] = field(default_factory=list)

class UnifiedBrandRegistry:
    """Unified brand registry for all DPerformance agents"""
    
    def __init__(self):
        self.vendors = self._initialize_vendor_registry()
        self.brand_to_vendor = self._build_brand_mapping()
        self.domain_to_vendor = self._build_domain_mapping()
        
        # Compile regex patterns for performance
        self._compile_patterns()
    
    def _initialize_vendor_registry(self) -> Dict[str, VendorConfig]:
        """Initialize comprehensive vendor registry with parsing configurations"""
        
        vendors = {
            # === OEM Manufacturers (Tier 1 - Highest Authority) ===
            'FORD': VendorConfig(
                brand_names=['Ford', 'FORD', 'ford', 'Motorcraft', 'MOTORCRAFT'],
                domains=['parts.ford.com', 'fordparts.com', 'ford.com', 'motorcraft.com', 'ford.oempartsonline.com'],
                authority_score=95,
                parsing_rules={
                    'primary_strategy': 'structured_data',
                    'fallback_strategies': ['table_parser', 'list_parser', 'text_extraction']
                },
                common_selectors=[
                    '.vehicle-compatibility', '.fitment-info', '.application-data',
                    'table[class*="vehicle"]', 'table[class*="fitment"]',
                    '.product-specifications', '.compatibility-table'
                ],
                text_patterns=[
                    r'(\d{4}(?:-\d{4})?)\s+(Ford|FORD)\s+([A-Za-z0-9\-\s]+)',
                    r'(Ford|FORD)\s+([A-Za-z0-9\-\s]+)\s+(\d{4}(?:-\d{4})?)',
                ]
            ),
            
            'CHEVROLET': VendorConfig(
                brand_names=['Chevrolet', 'CHEVROLET', 'Chevy', 'CHEVY', 'GMC', 'Cadillac'],
                domains=['parts.gm.com', 'gmpartsdirect.com', 'chevroletparts.com'],
                authority_score=95,
                parsing_rules={'primary_strategy': 'structured_data'},
                common_selectors=[
                    '.vehicle-fitment', '.compatibility-info', '.application-list',
                    'table[class*="compatibility"]'
                ],
                text_patterns=[
                    r'(\d{4}(?:-\d{4})?)\s+(Chevrolet|CHEVROLET|Chevy|CHEVY|GMC|Cadillac)\s+([A-Za-z0-9\-\s]+)',
                ]
            ),
            
            'HONDA': VendorConfig(
                brand_names=['Honda', 'HONDA', 'Acura', 'ACURA'],
                domains=['parts.honda.com', 'hondapartsnow.com', 'acurapartsnow.com'],
                authority_score=95,
                parsing_rules={'primary_strategy': 'structured_data'},
                common_selectors=['.fitment-data', '.vehicle-application', 'table.compatibility'],
                text_patterns=[
                    r'(\d{4}(?:-\d{4})?)\s+(Honda|HONDA|Acura|ACURA)\s+([A-Za-z0-9\-\s]+)',
                ]
            ),
            
            'TOYOTA': VendorConfig(
                brand_names=['Toyota', 'TOYOTA', 'Lexus', 'LEXUS', 'Scion', 'SCION'],
                domains=['parts.toyota.com', 'toyotapartsdeal.com', 'lexuspartsnow.com'],
                authority_score=95,
                parsing_rules={'primary_strategy': 'structured_data'},
                common_selectors=['.vehicle-compatibility', '.fitment-table'],
                text_patterns=[
                    r'(\d{4}(?:-\d{4})?)\s+(Toyota|TOYOTA|Lexus|LEXUS|Scion|SCION)\s+([A-Za-z0-9\-\s]+)',
                ]
            ),
            
            'NISSAN': VendorConfig(
                brand_names=['Nissan', 'NISSAN', 'Infiniti', 'INFINITI'],
                domains=['parts.nissanusa.com', 'nissanpartsdeal.com', 'infinitipartsdeal.com'],
                authority_score=95,
                parsing_rules={'primary_strategy': 'structured_data'},
                common_selectors=['.vehicle-fitment', '.compatibility-data'],
                text_patterns=[
                    r'(\d{4}(?:-\d{4})?)\s+(Nissan|NISSAN|Infiniti|INFINITI)\s+([A-Za-z0-9\-\s]+)',
                ]
            ),
            
            # === Performance/Aftermarket Brands (Tier 2 - High Authority) ===
            'HAWK_PERFORMANCE': VendorConfig(
                brand_names=['Hawk Performance', 'HAWK PERFORMANCE', 'Hawk', 'HAWK'],
                domains=['hawkperformance.com', 'hawkperformanceparts.com'],
                authority_score=90,
                parsing_rules={
                    'primary_strategy': 'custom_hawk_parser',
                    'handles_concatenated_text': True,
                    'fallback_strategies': ['text_extraction', 'table_parser']
                },
                common_selectors=[
                    '.vehicle-applications', '.fitment-list', '.compatibility-info',
                    'ul[class*="vehicle"]', 'div[class*="application"]'
                ],
                text_patterns=[
                    r'(\d{4}(?:-\d{4})?)\s+([A-Za-z]+)\s+([A-Za-z0-9\-\s]+)',
                    r'(\d{4})\s+([A-Za-z]+)\s+([A-Za-z0-9\-\s]+?)(?=\d{4}|$)',
                ],
                vehicle_patterns={
                    'concatenated': r'(\d{4}(?:-\d{4})?\s+[A-Z][a-zA-Z\s]+?(?=\d{4}|$))',
                    'single': r'(\d{4})(?:-(\d{4}))?\s+([A-Za-z]+)\s+([A-Za-z0-9\-\s]+)',
                    'year_range': r'(\d{4})-(\d{4})',
                    'single_year': r'^(\d{4})\s+'
                }
            ),
            
            'BILSTEIN': VendorConfig(
                brand_names=['Bilstein', 'BILSTEIN'],
                domains=['bilstein.com', 'bilsteincanada.com', 'bilsteinparts.com'],
                authority_score=88,
                parsing_rules={
                    'primary_strategy': 'custom_bilstein_parser',
                    'structured_format': True,
                    'fallback_strategies': ['text_extraction', 'table_parser']
                },
                common_selectors=[
                    '.fitment-info', '.vehicle-compatibility', '.application-data',
                    'div[class*="fitment"]', 'section[class*="compatibility"]'
                ],
                text_patterns=[
                    r'Years:\s*(\d{4})\s*[–-]\s*(\d{4}),\s*Make:\s*([A-Z]+),\s*Model:\s*([A-Za-z0-9\-\s]+)',
                    r'(\d{4})[–-](\d{4})\s+([A-Za-z]+)\s+([A-Za-z0-9\-\s]+)',
                ],
                vehicle_patterns={
                    'structured': r'Years:\s*(\d{4})\s*[–-]\s*(\d{4}),\s*Make:\s*([A-Z]+),\s*Model:\s*([A-Za-z0-9\-\s]+)',
                    'concatenated': r'(\d{4}[–-]\d{4}\s+[A-Za-z]+\s+[A-Za-z0-9\-\s]+)',
                    'simple': r'(\d{4}(?:[–-]\d{4})?)\s+([A-Za-z]+)\s+([A-Za-z0-9\-\s]+)'
                }
            ),
            
            'BREMBO': VendorConfig(
                brand_names=['Brembo', 'BREMBO'],
                domains=['brembo.com', 'bremboparts.com'],
                authority_score=87,
                parsing_rules={'primary_strategy': 'table_parser'},
                common_selectors=['.vehicle-application', 'table[class*="fitment"]'],
                text_patterns=[r'(\d{4}(?:-\d{4})?)\s+([A-Za-z]+)\s+([A-Za-z0-9\-\s]+)']
            ),
            
            'KN_FILTERS': VendorConfig(
                brand_names=['K&N', 'KN', 'K&N Filters'],
                domains=['knfilters.com', 'knperformance.com'],
                authority_score=85,
                parsing_rules={'primary_strategy': 'table_parser'},
                common_selectors=['.vehicle-search-results', '.fitment-table'],
                text_patterns=[r'(\d{4}(?:-\d{4})?)\s+([A-Za-z]+)\s+([A-Za-z0-9\-\s]+)']
            ),
            
            'BOSCH': VendorConfig(
                brand_names=['Bosch', 'BOSCH'],
                domains=['boschparts.com', 'boschonline.com'],
                authority_score=85,
                parsing_rules={'primary_strategy': 'structured_data'},
                common_selectors=['.product-fitment', '.vehicle-compatibility'],
                text_patterns=[r'(\d{4}(?:-\d{4})?)\s+([A-Za-z]+)\s+([A-Za-z0-9\-\s]+)']
            ),
            
            # === European Brands (Tier 2) ===
            'BMW': VendorConfig(
                brand_names=['BMW', 'bmw', 'Mini', 'MINI'],
                domains=['parts.bmw.com', 'bmwpartsnow.com', 'minipartsnow.com'],
                authority_score=90,
                parsing_rules={'primary_strategy': 'structured_data'},
                common_selectors=['.vehicle-fitment', '.compatibility-info'],
                text_patterns=[
                    r'(\d{4}(?:-\d{4})?)\s+(BMW|bmw|Mini|MINI)\s+([A-Za-z0-9\-\s]+)',
                ]
            ),
            
            'MERCEDES_BENZ': VendorConfig(
                brand_names=['Mercedes-Benz', 'MERCEDES-BENZ', 'Mercedes', 'MERCEDES', 'MB'],
                domains=['parts.mbusa.com', 'mercedespartscenter.com'],
                authority_score=90,
                parsing_rules={'primary_strategy': 'structured_data'},
                common_selectors=['.fitment-data', '.vehicle-application'],
                text_patterns=[
                    r'(\d{4}(?:-\d{4})?)\s+(Mercedes(?:-Benz)?|MERCEDES(?:-BENZ)?|MB)\s+([A-Za-z0-9\-\s]+)',
                ]
            ),
            
            'AUDI': VendorConfig(
                brand_names=['Audi', 'AUDI'],
                domains=['parts.audi.com', 'audipartsnow.com'],
                authority_score=88,
                parsing_rules={'primary_strategy': 'structured_data'},
                common_selectors=['.vehicle-compatibility', '.fitment-table'],
                text_patterns=[r'(\d{4}(?:-\d{4})?)\s+(Audi|AUDI)\s+([A-Za-z0-9\-\s]+)']
            ),
            
            'VOLKSWAGEN': VendorConfig(
                brand_names=['Volkswagen', 'VOLKSWAGEN', 'VW', 'vw'],
                domains=['parts.vw.com', 'vwpartsnow.com'],
                authority_score=88,
                parsing_rules={'primary_strategy': 'structured_data'},
                common_selectors=['.vehicle-fitment', '.compatibility-data'],
                text_patterns=[
                    r'(\d{4}(?:-\d{4})?)\s+(Volkswagen|VOLKSWAGEN|VW|vw)\s+([A-Za-z0-9\-\s]+)',
                ]
            ),
            
            # === Generic/Universal Vendors (Tier 3 - Medium Authority) ===
            'AUTOZONE': VendorConfig(
                brand_names=['AutoZone', 'AUTOZONE'],
                domains=['autozone.com', 'autozonepro.com'],
                authority_score=70,
                parsing_rules={'primary_strategy': 'table_parser'},
                common_selectors=['.vehicle-fitment', 'table[class*="compatibility"]'],
                text_patterns=[r'(\d{4}(?:-\d{4})?)\s+([A-Za-z]+)\s+([A-Za-z0-9\-\s]+)']
            ),
            
            'ADVANCE_AUTO': VendorConfig(
                brand_names=['Advance Auto Parts', 'ADVANCE AUTO PARTS', 'Advance'],
                domains=['advanceautoparts.com'],
                authority_score=70,
                parsing_rules={'primary_strategy': 'table_parser'},
                common_selectors=['.fitment-info', '.vehicle-application'],
                text_patterns=[r'(\d{4}(?:-\d{4})?)\s+([A-Za-z]+)\s+([A-Za-z0-9\-\s]+)']
            ),
        }
        
        return vendors
    
    def _build_brand_mapping(self) -> Dict[str, str]:
        """Build mapping from brand names to vendor keys"""
        mapping = {}
        
        for vendor_key, config in self.vendors.items():
            for brand_name in config.brand_names:
                # Add exact matches
                mapping[brand_name.upper()] = vendor_key
                mapping[brand_name.lower()] = vendor_key
                mapping[brand_name] = vendor_key
                
                # Add partial matches for compound names
                if ' ' in brand_name:
                    parts = brand_name.split()
                    for part in parts:
                        if len(part) >= 3:  # Avoid short words like "K", "N"
                            mapping[part.upper()] = vendor_key
                            mapping[part.lower()] = vendor_key
        
        return mapping
    
    def _build_domain_mapping(self) -> Dict[str, str]:
        """Build mapping from domains to vendor keys"""
        mapping = {}
        
        for vendor_key, config in self.vendors.items():
            for domain in config.domains:
                mapping[domain] = vendor_key
                # Also map subdomains
                if '.' in domain:
                    base_domain = '.'.join(domain.split('.')[-2:])
                    mapping[base_domain] = vendor_key
        
        return mapping
    
    def _compile_patterns(self):
        """Compile regex patterns for performance"""
        self.compiled_patterns = {}
        
        for vendor_key, config in self.vendors.items():
            self.compiled_patterns[vendor_key] = {
                'text_patterns': [re.compile(pattern, re.IGNORECASE) for pattern in config.text_patterns],
                'vehicle_patterns': {
                    name: re.compile(pattern, re.IGNORECASE) 
                    for name, pattern in config.vehicle_patterns.items()
                }
            }
    
    def identify_vendor_by_brand(self, brand: str) -> Optional[str]:
        """Identify vendor by brand name"""
        if not brand:
            return None
            
        brand_clean = brand.strip()
        
        # Try exact match first
        if brand_clean in self.brand_to_vendor:
            return self.brand_to_vendor[brand_clean]
        
        # Try case-insensitive match
        brand_upper = brand_clean.upper()
        if brand_upper in self.brand_to_vendor:
            return self.brand_to_vendor[brand_upper]
        
        # Try partial matching
        for brand_key, vendor_key in self.brand_to_vendor.items():
            if brand_upper in brand_key.upper() or brand_key.upper() in brand_upper:
                return vendor_key
        
        return None
    
    def identify_vendor_by_url(self, url: str) -> Optional[str]:
        """Identify vendor by URL/domain"""
        if not url:
            return None
            
        url_lower = url.lower()
        
        # Try exact domain match
        for domain, vendor_key in self.domain_to_vendor.items():
            if domain in url_lower:
                return vendor_key
        
        return None
    
    def get_vendor_config(self, vendor_key: str) -> Optional[VendorConfig]:
        """Get vendor configuration"""
        return self.vendors.get(vendor_key)
    
    def get_parsing_strategies(self, vendor_key: str) -> List[str]:
        """Get ordered list of parsing strategies for a vendor"""
        config = self.get_vendor_config(vendor_key)
        if not config:
            return ['table_parser', 'list_parser', 'text_extraction']  # Default fallback
        
        strategies = [config.parsing_rules.get('primary_strategy', 'table_parser')]
        strategies.extend(config.parsing_rules.get('fallback_strategies', []))
        
        return strategies
    
    def get_css_selectors(self, vendor_key: str) -> List[str]:
        """Get CSS selectors for vehicle data extraction"""
        config = self.get_vendor_config(vendor_key)
        if not config:
            return [
                '.vehicle-compatibility', '.fitment-info', '.application-data',
                'table[class*="vehicle"]', 'table[class*="fitment"]', 
                '.vehicle-application', '.compatibility-table'
            ]  # Default selectors
        
        return config.common_selectors
    
    def get_text_patterns(self, vendor_key: str) -> List[re.Pattern]:
        """Get compiled regex patterns for text extraction"""
        return self.compiled_patterns.get(vendor_key, {}).get('text_patterns', [])
    
    def get_vehicle_patterns(self, vendor_key: str) -> Dict[str, re.Pattern]:
        """Get compiled vehicle-specific regex patterns"""
        return self.compiled_patterns.get(vendor_key, {}).get('vehicle_patterns', {})
    
    def get_all_supported_brands(self) -> List[str]:
        """Get list of all supported brand names"""
        brands = set()
        for config in self.vendors.values():
            brands.update(config.brand_names)
        return sorted(list(brands))
    
    def get_vendor_authority_score(self, vendor_key: str) -> int:
        """Get authority score for vendor (for prioritization)"""
        config = self.get_vendor_config(vendor_key)
        return config.authority_score if config else 0

# Global instance for use throughout the application
brand_registry = UnifiedBrandRegistry()