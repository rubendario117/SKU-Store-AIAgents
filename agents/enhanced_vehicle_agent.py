#!/usr/bin/env python3
"""
Enhanced Vehicle Application Agent - Vendor-Agnostic Multi-Strategy Parser
Supports 60+ automotive brands with adaptive parsing strategies
"""

import os
import re
import json
import time
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any, Tuple
import logging
from dataclasses import dataclass

# Import existing vehicle application structure
from agents.vehicle_application_agent import VehicleApplication

# Import unified brand registry
from brand_registry import brand_registry, VendorConfig

# Import monitoring system
from monitoring import OperationTimer, get_vehicle_logger, LogContext

# Import settings
from config import PART_NUMBER_COLUMN_SOURCE, BRAND_COLUMN_SOURCE

@dataclass
class ParseResult:
    """Result from parsing attempt"""
    success: bool
    applications: List[VehicleApplication]
    confidence: float  # 0.0 to 1.0
    strategy_used: str
    errors: List[str]
    metadata: Dict[str, Any]

class EnhancedVehicleApplicationAgent:
    """Enhanced vehicle application agent with multi-strategy parsing"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Initialize monitoring
        self.logger = get_vehicle_logger()
        
        # Initialize parsing strategies
        self.parsing_strategies = {
            'custom_hawk_parser': self._parse_hawk_performance,
            'custom_bilstein_parser': self._parse_bilstein,
            'structured_data': self._parse_structured_data,
            'table_parser': self._parse_table_data,
            'list_parser': self._parse_list_data,
            'text_extraction': self._parse_text_content,
            'machine_learning': self._parse_ml_enhanced,
            'fallback_heuristic': self._parse_fallback_heuristic
        }
        
        # Cache for parsed applications
        self.cache_file = "enhanced_vehicle_applications_cache.json"
        self.cache = self._load_cache()
        
        # Statistics tracking
        self.stats = {
            'total_attempts': 0,
            'successful_parses': 0,
            'strategy_usage': {},
            'vendor_success_rates': {},
            'confidence_scores': []
        }
    
    def find_and_extract_applications(self, product_data: Dict[str, str], 
                                     image_agent=None) -> List[VehicleApplication]:
        """Main method to find and extract vehicle applications with enhanced strategies"""
        
        part_number = product_data.get(PART_NUMBER_COLUMN_SOURCE, '').strip()
        brand = product_data.get(BRAND_COLUMN_SOURCE, '').strip()
        
        with LogContext(self.logger, part_number=part_number, brand=brand):
            self.logger.info(f"Extracting applications for {brand} {part_number}")
            
            # Input validation
            if not part_number or not brand:
                self.logger.warning(f"Missing required data: part_number='{part_number}', brand='{brand}'")
                return []
            
            with OperationTimer('enhanced_vehicle_agent', 'application_extraction', 
                              {'part_number': part_number, 'brand': brand}):
                
                # Check cache first
                cache_key = f"{brand}_{part_number}".replace(' ', '_').upper()
                if cache_key in self.cache:
                    self.logger.info(f"Using cached applications for {part_number}")
                    return self._deserialize_applications(self.cache[cache_key])
                
                # Identify vendor and get configuration
                vendor_key = brand_registry.identify_vendor_by_brand(brand)
                if vendor_key:
                    self.logger.info(f"Identified vendor: {vendor_key}")
                    vendor_config = brand_registry.get_vendor_config(vendor_key)
                else:
                    self.logger.info(f"Unknown vendor for brand: {brand}, using generic strategies")
                    vendor_config = None
                
                # Get parsing strategies in priority order
                strategies = self._get_parsing_strategies(vendor_key, vendor_config)
                
                # Try multiple search sources
                search_urls = self._discover_product_urls(part_number, brand, image_agent)
                
                best_result = ParseResult(
                    success=False, applications=[], confidence=0.0,
                    strategy_used='none', errors=[], metadata={}
                )
                
                # Try each URL with progressive strategy fallback
                for url in search_urls[:3]:  # Limit to top 3 URLs to avoid excessive processing
                    self.logger.info(f"Attempting to parse URL: {url}")
                    
                    try:
                        # Fetch page content
                        response = self.session.get(url, timeout=30)
                        if response.status_code != 200:
                            continue
                        
                        soup = BeautifulSoup(response.content, 'html.parser')
                        
                        # Try each parsing strategy
                        for strategy in strategies:
                            self.logger.info(f"Trying strategy: {strategy}")
                            
                            try:
                                result = self._execute_parsing_strategy(
                                    strategy, url, part_number, soup, vendor_config
                                )
                                
                                # Update statistics
                                self._update_stats(strategy, result, vendor_key)
                                
                                # Use best result (highest confidence)
                                if result.success and result.confidence > best_result.confidence:
                                    best_result = result
                                    
                                # If we have high confidence, use it immediately
                                if result.confidence >= 0.9:
                                    self.logger.success(f"High confidence result with {strategy}")
                                    break
                                    
                            except Exception as e:
                                self.logger.error(f"Strategy {strategy} failed: {e}")
                                continue
                        
                        # If we found good results, break from URL loop
                        if best_result.confidence >= 0.7:
                            break
                            
                    except Exception as e:
                        self.logger.error(f"Error processing URL {url}: {e}")
                        continue
                
                # Cache and return results
                applications = best_result.applications
                if applications:
                    self.cache[cache_key] = self._serialize_applications(applications)
                    self._save_cache()
                    self.logger.success(f"Found {len(applications)} applications using {best_result.strategy_used}")
                else:
                    self.logger.warning(f"No applications found for {part_number}")
                
                return applications
    
    def _get_parsing_strategies(self, vendor_key: Optional[str], 
                               vendor_config: Optional[VendorConfig]) -> List[str]:
        """Get ordered list of parsing strategies based on vendor"""
        
        if vendor_config:
            # Use vendor-specific strategies
            strategies = brand_registry.get_parsing_strategies(vendor_key)
        else:
            # Use comprehensive fallback strategy chain
            strategies = [
                'structured_data',      # Try structured data first (JSON-LD, microdata)
                'table_parser',         # HTML tables
                'list_parser',          # HTML lists (ul, ol)
                'text_extraction',      # Raw text parsing
                'machine_learning',     # ML-enhanced parsing
                'fallback_heuristic'    # Last resort heuristics
            ]
        
        return strategies
    
    def _discover_product_urls(self, part_number: str, brand: str, 
                              image_agent=None) -> List[str]:
        """Discover potential product URLs for parsing"""
        urls = []
        
        # Strategy 1: Use image agent's found URLs (highest priority)
        if image_agent and hasattr(image_agent, 'last_search_results'):
            for result in getattr(image_agent, 'last_search_results', []):
                if 'link' in result:
                    urls.append(result['link'])
        
        # Strategy 2: Use brand registry domains for direct search
        vendor_key = brand_registry.identify_vendor_by_brand(brand)
        if vendor_key:
            vendor_config = brand_registry.get_vendor_config(vendor_key)
            for domain in vendor_config.domains[:2]:  # Top 2 official domains
                # Construct potential URLs
                safe_part = re.sub(r'[^a-zA-Z0-9\-_]', '', part_number.replace(' ', '-'))
                potential_urls = [
                    f"https://{domain}/product/{safe_part}",
                    f"https://{domain}/parts/{safe_part}",
                    f"https://{domain}/catalog/{safe_part}",
                    f"https://{domain}/search?q={safe_part}"
                ]
                urls.extend(potential_urls)
        
        # Strategy 3: Generic search patterns for unknown vendors
        if not urls:
            generic_patterns = [
                f"https://www.google.com/search?q={brand}+{part_number}+vehicle+fitment+compatibility",
                f"https://www.google.com/search?q=\"{part_number}\"+{brand}+applications"
            ]
            urls.extend(generic_patterns)
        
        return urls[:10]  # Limit to prevent excessive requests
    
    def _execute_parsing_strategy(self, strategy: str, url: str, part_number: str, 
                                  soup: BeautifulSoup, vendor_config: Optional[VendorConfig]) -> ParseResult:
        """Execute a specific parsing strategy"""
        
        try:
            if strategy in self.parsing_strategies:
                return self.parsing_strategies[strategy](url, part_number, soup, vendor_config)
            else:
                return ParseResult(
                    success=False, applications=[], confidence=0.0,
                    strategy_used=strategy, errors=[f"Unknown strategy: {strategy}"], metadata={}
                )
        except Exception as e:
            return ParseResult(
                success=False, applications=[], confidence=0.0,
                strategy_used=strategy, errors=[str(e)], metadata={}
            )
    
    def _parse_hawk_performance(self, url: str, part_number: str, soup: BeautifulSoup, 
                               vendor_config: Optional[VendorConfig]) -> ParseResult:
        """Enhanced Hawk Performance parser with concatenation handling"""
        applications = []
        errors = []
        
        try:
            # Use vendor-specific selectors if available
            selectors = vendor_config.common_selectors if vendor_config else [
                '.vehicle-applications', '.fitment-list', '.compatibility-info',
                'ul[class*="vehicle"]', 'div[class*="application"]'
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                for element in elements:
                    text_content = element.get_text(strip=True)
                    if len(text_content) > 20:  # Must have substantial content
                        # Use enhanced concatenated text parsing
                        parsed_apps = self._parse_concatenated_vehicle_text(text_content, vendor_config)
                        applications.extend(parsed_apps)
            
            # Remove duplicates
            applications = self._remove_duplicate_applications(applications)
            
            confidence = min(0.95, len(applications) * 0.15)  # Higher confidence for Hawk
            
            return ParseResult(
                success=len(applications) > 0,
                applications=applications,
                confidence=confidence,
                strategy_used='custom_hawk_parser',
                errors=errors,
                metadata={'selector_count': len(selectors), 'elements_found': len(elements)}
            )
            
        except Exception as e:
            return ParseResult(
                success=False, applications=[], confidence=0.0,
                strategy_used='custom_hawk_parser', errors=[str(e)], metadata={}
            )
    
    def _parse_bilstein(self, url: str, part_number: str, soup: BeautifulSoup, 
                       vendor_config: Optional[VendorConfig]) -> ParseResult:
        """Enhanced Bilstein parser with concatenation handling"""
        applications = []
        errors = []
        
        try:
            # Bilstein-specific selectors
            selectors = vendor_config.common_selectors if vendor_config else [
                '.fitment-info', '.vehicle-compatibility', '.application-data',
                'div[class*="fitment"]', 'section[class*="compatibility"]'
            ]
            
            # Get Bilstein-specific patterns
            patterns = brand_registry.get_vehicle_patterns('BILSTEIN') if vendor_config else {}
            
            for selector in selectors:
                elements = soup.select(selector)
                for element in elements:
                    text_content = element.get_text(strip=True)
                    
                    # Try structured format first: "Years: 2005 – 2023, Make: TOYOTA, Model: Tacoma"
                    if 'structured' in patterns:
                        structured_matches = patterns['structured'].findall(text_content)
                        for match in structured_matches:
                            year_start, year_end, make, model = match
                            app = VehicleApplication(
                                year_start=int(year_start),
                                year_end=int(year_end),
                                make=make,
                                model=model.strip()
                            )
                            applications.append(app)
                    
                    # Try concatenated format for multiple vehicles
                    elif len(text_content) > 50:
                        parsed_apps = self._parse_concatenated_vehicle_text(text_content, vendor_config)
                        applications.extend(parsed_apps)
            
            # Remove duplicates
            applications = self._remove_duplicate_applications(applications)
            
            confidence = min(0.92, len(applications) * 0.2)  # Good confidence for Bilstein
            
            return ParseResult(
                success=len(applications) > 0,
                applications=applications,
                confidence=confidence,
                strategy_used='custom_bilstein_parser',
                errors=errors,
                metadata={'patterns_used': len(patterns)}
            )
            
        except Exception as e:
            return ParseResult(
                success=False, applications=[], confidence=0.0,
                strategy_used='custom_bilstein_parser', errors=[str(e)], metadata={}
            )
    
    def _parse_structured_data(self, url: str, part_number: str, soup: BeautifulSoup, 
                              vendor_config: Optional[VendorConfig]) -> ParseResult:
        """Parse structured data (JSON-LD, microdata, etc.)"""
        applications = []
        errors = []
        
        try:
            # Look for JSON-LD structured data
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    # Extract vehicle compatibility data
                    apps = self._extract_vehicles_from_structured_data(data)
                    applications.extend(apps)
                except json.JSONDecodeError:
                    continue
            
            # Look for microdata
            microdata_elements = soup.find_all(attrs={'itemtype': True})
            for element in microdata_elements:
                if 'vehicle' in element.get('itemtype', '').lower():
                    apps = self._extract_vehicles_from_microdata(element)
                    applications.extend(apps)
            
            confidence = min(0.98, len(applications) * 0.25) if applications else 0.0
            
            return ParseResult(
                success=len(applications) > 0,
                applications=applications,
                confidence=confidence,
                strategy_used='structured_data',
                errors=errors,
                metadata={'json_ld_count': len(json_scripts), 'microdata_count': len(microdata_elements)}
            )
            
        except Exception as e:
            return ParseResult(
                success=False, applications=[], confidence=0.0,
                strategy_used='structured_data', errors=[str(e)], metadata={}
            )
    
    def _parse_table_data(self, url: str, part_number: str, soup: BeautifulSoup, 
                         vendor_config: Optional[VendorConfig]) -> ParseResult:
        """Enhanced table parser supporting all car brands"""
        applications = []
        errors = []
        
        try:
            # Find all tables
            tables = soup.find_all('table')
            
            # Get all supported brand names for detection
            all_brands = brand_registry.get_all_supported_brands()
            brand_pattern = re.compile('|'.join(re.escape(brand) for brand in all_brands), re.IGNORECASE)
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:  # Need at least year, make, model
                        row_text = ' '.join(cell.get_text(strip=True) for cell in cells)
                        
                        # Check if row contains vehicle information
                        if re.search(r'\b\d{4}\b', row_text) and brand_pattern.search(row_text):
                            # Extract vehicle information from row
                            app = self._extract_vehicle_from_table_row(cells, all_brands)
                            if app:
                                applications.append(app)
            
            # Remove duplicates
            applications = self._remove_duplicate_applications(applications)
            
            confidence = min(0.85, len(applications) * 0.18) if applications else 0.0
            
            return ParseResult(
                success=len(applications) > 0,
                applications=applications,
                confidence=confidence,
                strategy_used='table_parser',
                errors=errors,
                metadata={'tables_processed': len(tables), 'brands_supported': len(all_brands)}
            )
            
        except Exception as e:
            return ParseResult(
                success=False, applications=[], confidence=0.0,
                strategy_used='table_parser', errors=[str(e)], metadata={}
            )
    
    def _parse_list_data(self, url: str, part_number: str, soup: BeautifulSoup, 
                        vendor_config: Optional[VendorConfig]) -> ParseResult:
        """Parse vehicle data from HTML lists"""
        applications = []
        errors = []
        
        try:
            # Find lists that might contain vehicle information
            lists = soup.find_all(['ul', 'ol'])
            
            for list_elem in lists:
                list_items = list_elem.find_all('li')
                for item in list_items:
                    text = item.get_text(strip=True)
                    # Check if item looks like vehicle application
                    if re.search(r'\b\d{4}\b', text) and len(text) > 10:
                        app = self._parse_single_vehicle_text(text)
                        if app:
                            applications.append(app)
            
            confidence = min(0.80, len(applications) * 0.15) if applications else 0.0
            
            return ParseResult(
                success=len(applications) > 0,
                applications=applications,
                confidence=confidence,
                strategy_used='list_parser',
                errors=errors,
                metadata={'lists_processed': len(lists)}
            )
            
        except Exception as e:
            return ParseResult(
                success=False, applications=[], confidence=0.0,
                strategy_used='list_parser', errors=[str(e)], metadata={}
            )
    
    def _parse_text_content(self, url: str, part_number: str, soup: BeautifulSoup, 
                           vendor_config: Optional[VendorConfig]) -> ParseResult:
        """Parse vehicle data from raw text content"""
        applications = []
        errors = []
        
        try:
            # Get all text content
            text_content = soup.get_text()
            
            # Use vendor-specific patterns if available
            if vendor_config:
                patterns = brand_registry.get_text_patterns(vendor_config.brand_names[0].upper().replace(' ', '_'))
            else:
                # Generic patterns for all brands
                all_brands = brand_registry.get_all_supported_brands()
                brand_regex = '|'.join(re.escape(brand) for brand in all_brands)
                patterns = [
                    re.compile(rf'(\d{{4}}(?:-\d{{4}})?)\s+({brand_regex})\s+([A-Za-z0-9\-\s]+)', re.IGNORECASE),
                    re.compile(rf'({brand_regex})\s+([A-Za-z0-9\-\s]+)\s+(\d{{4}}(?:-\d{{4}})?)', re.IGNORECASE)
                ]
            
            # Apply patterns to extract vehicles
            for pattern in patterns:
                matches = pattern.findall(text_content)
                for match in matches:
                    app = self._create_application_from_match(match)
                    if app:
                        applications.append(app)
            
            # Remove duplicates
            applications = self._remove_duplicate_applications(applications)
            
            confidence = min(0.70, len(applications) * 0.12) if applications else 0.0
            
            return ParseResult(
                success=len(applications) > 0,
                applications=applications,
                confidence=confidence,
                strategy_used='text_extraction',
                errors=errors,
                metadata={'patterns_used': len(patterns), 'text_length': len(text_content)}
            )
            
        except Exception as e:
            return ParseResult(
                success=False, applications=[], confidence=0.0,
                strategy_used='text_extraction', errors=[str(e)], metadata={}
            )
    
    def _parse_ml_enhanced(self, url: str, part_number: str, soup: BeautifulSoup, 
                          vendor_config: Optional[VendorConfig]) -> ParseResult:
        """Machine learning enhanced parsing (placeholder for future ML implementation)"""
        # This is a placeholder for future ML implementation
        # For now, use heuristic-based enhanced parsing
        
        applications = []
        errors = []
        
        try:
            # Use multiple heuristics combined
            text_content = soup.get_text()
            
            # Heuristic 1: Look for year-make-model patterns with higher recall
            vehicle_pattern = re.compile(
                r'(?:^|\s)(\d{4})(?:\s*[-–—]\s*(\d{4}))?\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+([A-Za-z0-9][A-Za-z0-9\s\-]*?)(?=\s*\d{4}|\s*$|[.,;])', 
                re.MULTILINE | re.IGNORECASE
            )
            
            matches = vehicle_pattern.findall(text_content)
            
            # Filter and score matches
            scored_matches = []
            all_brands = set(brand.upper() for brand in brand_registry.get_all_supported_brands())
            
            for match in matches:
                year_start, year_end, make, model = match
                make_upper = make.upper().strip()
                
                # Score based on brand recognition
                score = 0.5  # Base score
                if make_upper in all_brands:
                    score += 0.3
                if any(brand in make_upper for brand in all_brands):
                    score += 0.1
                if 1990 <= int(year_start) <= 2025:  # Reasonable year range
                    score += 0.2
                
                if score >= 0.7:  # Threshold for acceptance
                    scored_matches.append((match, score))
            
            # Convert high-scoring matches to applications
            for match, score in scored_matches:
                year_start, year_end, make, model = match
                app = VehicleApplication(
                    year_start=int(year_start),
                    year_end=int(year_end) if year_end else int(year_start),
                    make=make.strip(),
                    model=model.strip()
                )
                applications.append(app)
            
            # Remove duplicates
            applications = self._remove_duplicate_applications(applications)
            
            # Confidence based on scoring
            avg_score = sum(score for _, score in scored_matches) / len(scored_matches) if scored_matches else 0
            confidence = min(0.75, avg_score * len(applications) * 0.1)
            
            return ParseResult(
                success=len(applications) > 0,
                applications=applications,
                confidence=confidence,
                strategy_used='machine_learning',
                errors=errors,
                metadata={'scored_matches': len(scored_matches), 'avg_score': avg_score}
            )
            
        except Exception as e:
            return ParseResult(
                success=False, applications=[], confidence=0.0,
                strategy_used='machine_learning', errors=[str(e)], metadata={}
            )
    
    def _parse_fallback_heuristic(self, url: str, part_number: str, soup: BeautifulSoup, 
                                 vendor_config: Optional[VendorConfig]) -> ParseResult:
        """Last resort heuristic parsing"""
        applications = []
        errors = []
        
        try:
            # Extract all text and try very permissive patterns
            text_content = soup.get_text()
            
            # Look for any 4-digit numbers followed by text that might be vehicles
            loose_pattern = re.compile(r'(\d{4})\s+([A-Za-z][A-Za-z\s]{3,30})', re.IGNORECASE)
            matches = loose_pattern.findall(text_content)
            
            all_brands = set(brand.lower() for brand in brand_registry.get_all_supported_brands())
            
            for year_str, text in matches:
                year = int(year_str)
                if 1990 <= year <= 2030:  # Reasonable year range
                    words = text.strip().split()
                    if len(words) >= 2:
                        potential_make = words[0].lower()
                        if any(potential_make in brand for brand in all_brands) or any(brand in potential_make for brand in all_brands):
                            app = VehicleApplication(
                                year_start=year,
                                year_end=year,
                                make=words[0],
                                model=' '.join(words[1:3]) if len(words) > 1 else words[1] if len(words) > 1 else 'Unknown'
                            )
                            applications.append(app)
            
            # Very low confidence for heuristic results
            confidence = min(0.50, len(applications) * 0.08) if applications else 0.0
            
            return ParseResult(
                success=len(applications) > 0,
                applications=applications,
                confidence=confidence,
                strategy_used='fallback_heuristic',
                errors=errors,
                metadata={'loose_matches': len(matches)}
            )
            
        except Exception as e:
            return ParseResult(
                success=False, applications=[], confidence=0.0,
                strategy_used='fallback_heuristic', errors=[str(e)], metadata={}
            )
    
    def _parse_concatenated_vehicle_text(self, text: str, vendor_config: Optional[VendorConfig]) -> List[VehicleApplication]:
        """Enhanced concatenated text parsing using vendor-specific patterns"""
        applications = []
        
        try:
            # Use vendor-specific patterns if available
            if vendor_config:
                vehicle_patterns = brand_registry.get_vehicle_patterns(vendor_config.brand_names[0].upper().replace(' ', '_'))
                if 'concatenated' in vehicle_patterns:
                    pattern = vehicle_patterns['concatenated']
                    potential_vehicles = pattern.findall(text)
                else:
                    # Fallback to generic pattern
                    potential_vehicles = re.findall(r'(\d{4}(?:-\d{4})?\s+[A-Z][a-zA-Z\s]+?(?=\d{4}|$))', text)
            else:
                # Generic concatenated pattern
                potential_vehicles = re.findall(r'(\d{4}(?:-\d{4})?\s+[A-Z][a-zA-Z\s]+?(?=\d{4}|$))', text)
            
            for vehicle_text in potential_vehicles:
                vehicle_text = vehicle_text.strip()
                if len(vehicle_text) > 8:  # Must have at least year + make
                    app = self._parse_single_vehicle_text(vehicle_text)
                    if app:
                        applications.append(app)
                        
        except Exception as e:
            self.logger.error(f"Error parsing concatenated text: {e}")
        
        return applications
    
    def _parse_single_vehicle_text(self, text: str) -> Optional[VehicleApplication]:
        """Parse a single vehicle application from text"""
        try:
            # Clean the text
            text = re.sub(r'\s*\(.*?\)', '', text)  # Remove parenthetical content
            text = text.strip()
            
            # Extract year(s) - single year or range
            year_match = re.match(r'(\d{4})(?:[-–—](\d{4}))?\s+', text)
            if not year_match:
                return None
                
            year_start = int(year_match.group(1))
            year_end = int(year_match.group(2)) if year_match.group(2) else year_start
            
            # Remove year from text
            remaining_text = text[year_match.end():].strip()
            
            # Extract make and model
            words = remaining_text.split()
            if len(words) < 2:
                return None
                
            make = words[0]
            model = words[1]
            
            # Everything else is trim
            trim = ' '.join(words[2:]) if len(words) > 2 else None
            
            # Extract engine information
            engine_match = re.search(r'(\d+\.?\d*L(?:\s*V\d+)?|\d+\.?\d*\s*Turbo)', text, re.I)
            engine = engine_match.group(1).strip() if engine_match else None
            
            return VehicleApplication(
                year_start=year_start,
                year_end=year_end,
                make=make,
                model=model,
                trim=trim,
                engine=engine
            )
            
        except Exception as e:
            return None
    
    def _extract_vehicles_from_structured_data(self, data: Dict[str, Any]) -> List[VehicleApplication]:
        """Extract vehicle applications from JSON-LD structured data"""
        applications = []
        
        # This would be implemented based on common structured data schemas
        # for automotive parts (schema.org/Vehicle, schema.org/Product, etc.)
        
        return applications
    
    def _extract_vehicles_from_microdata(self, element) -> List[VehicleApplication]:
        """Extract vehicle applications from microdata"""
        applications = []
        
        # This would be implemented based on microdata parsing
        
        return applications
    
    def _extract_vehicle_from_table_row(self, cells, all_brands: List[str]) -> Optional[VehicleApplication]:
        """Extract vehicle application from table row cells"""
        try:
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            
            # Find year, make, model in cells
            year = None
            make = None
            model = None
            
            brand_set = set(brand.upper() for brand in all_brands)
            
            for i, text in enumerate(cell_texts):
                # Look for year
                year_match = re.search(r'\b(\d{4})\b', text)
                if year_match and not year:
                    year = int(year_match.group(1))
                
                # Look for make
                text_upper = text.upper()
                if not make and any(brand in text_upper for brand in brand_set):
                    make = text
                
                # Model is typically after make
                if make and not model and i > 0 and text not in make:
                    model = text
            
            if year and make and model:
                return VehicleApplication(
                    year_start=year,
                    year_end=year,
                    make=make,
                    model=model
                )
            
        except Exception:
            pass
        
        return None
    
    def _create_application_from_match(self, match: Tuple) -> Optional[VehicleApplication]:
        """Create VehicleApplication from regex match"""
        try:
            if len(match) == 3:
                # Pattern: year, make, model
                year_str, make, model = match
                year_range = re.match(r'(\d{4})(?:-(\d{4}))?', year_str)
                if year_range:
                    year_start = int(year_range.group(1))
                    year_end = int(year_range.group(2)) if year_range.group(2) else year_start
                    
                    return VehicleApplication(
                        year_start=year_start,
                        year_end=year_end,
                        make=make.strip(),
                        model=model.strip()
                    )
        except Exception:
            pass
        
        return None
    
    def _remove_duplicate_applications(self, applications: List[VehicleApplication]) -> List[VehicleApplication]:
        """Remove duplicate vehicle applications"""
        seen = set()
        unique_applications = []
        
        for app in applications:
            # Create a key for deduplication
            key = (app.year_start, app.year_end, 
                  app.make.upper() if app.make else None,
                  app.model.upper() if app.model else None)
            
            if key not in seen:
                seen.add(key)
                unique_applications.append(app)
        
        return unique_applications
    
    def _update_stats(self, strategy: str, result: ParseResult, vendor_key: Optional[str]):
        """Update parsing statistics"""
        self.stats['total_attempts'] += 1
        
        if result.success:
            self.stats['successful_parses'] += 1
        
        if strategy not in self.stats['strategy_usage']:
            self.stats['strategy_usage'][strategy] = {'attempts': 0, 'successes': 0}
        
        self.stats['strategy_usage'][strategy]['attempts'] += 1
        if result.success:
            self.stats['strategy_usage'][strategy]['successes'] += 1
        
        if vendor_key:
            if vendor_key not in self.stats['vendor_success_rates']:
                self.stats['vendor_success_rates'][vendor_key] = {'attempts': 0, 'successes': 0}
            
            self.stats['vendor_success_rates'][vendor_key]['attempts'] += 1
            if result.success:
                self.stats['vendor_success_rates'][vendor_key]['successes'] += 1
        
        self.stats['confidence_scores'].append(result.confidence)
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load cached applications"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading cache: {e}")
        
        return {}
    
    def _save_cache(self):
        """Save cached applications"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving cache: {e}")
    
    def _serialize_applications(self, applications: List[VehicleApplication]) -> List[Dict[str, Any]]:
        """Serialize applications for caching"""
        return [
            {
                'year_start': app.year_start,
                'year_end': app.year_end,
                'make': app.make,
                'model': app.model,
                'trim': app.trim,
                'engine': app.engine,
                'position': app.position,
                'notes': app.notes
            }
            for app in applications
        ]
    
    def _deserialize_applications(self, data: List[Dict[str, Any]]) -> List[VehicleApplication]:
        """Deserialize applications from cache"""
        return [
            VehicleApplication(
                year_start=item.get('year_start'),
                year_end=item.get('year_end'),
                make=item.get('make'),
                model=item.get('model'),
                trim=item.get('trim'),
                engine=item.get('engine'),
                position=item.get('position'),
                notes=item.get('notes')
            )
            for item in data
        ]
    
    def get_parsing_statistics(self) -> Dict[str, Any]:
        """Get parsing performance statistics"""
        stats = self.stats.copy()
        
        # Calculate success rates
        if stats['total_attempts'] > 0:
            stats['overall_success_rate'] = stats['successful_parses'] / stats['total_attempts']
        else:
            stats['overall_success_rate'] = 0.0
        
        # Calculate average confidence
        if stats['confidence_scores']:
            stats['average_confidence'] = sum(stats['confidence_scores']) / len(stats['confidence_scores'])
        else:
            stats['average_confidence'] = 0.0
        
        return stats