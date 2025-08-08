# File: agents/vehicle_application_agent.py

import os
import re
import json
import time
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any

# Import settings from the central config file
from config import PART_NUMBER_COLUMN_SOURCE, BRAND_COLUMN_SOURCE

class VehicleApplication:
    """Standardized vehicle application data structure"""
    def __init__(self, year_start: int = None, year_end: int = None, make: str = None, 
                 model: str = None, trim: str = None, engine: str = None, 
                 position: str = None, notes: str = None):
        self.year_start = year_start
        self.year_end = year_end
        self.make = self._normalize_make(make) if make else None
        self.model = model.strip() if model else None
        self.trim = trim.strip() if trim else None
        self.engine = self._normalize_engine(engine) if engine else None
        self.position = position.strip() if position else None
        self.notes = notes.strip() if notes else None
    
    def _normalize_make(self, make: str) -> str:
        """Normalize vehicle make names"""
        if not make:
            return None
        
        make_upper = make.upper().strip()
        
        # Standardization mappings
        make_mappings = {
            'HONDA': 'Honda',
            'ACURA': 'Acura', 
            'TOYOTA': 'Toyota',
            'LEXUS': 'Lexus',
            'NISSAN': 'Nissan',
            'INFINITI': 'Infiniti',
            'FORD': 'Ford',
            'LINCOLN': 'Lincoln',
            'CHEVROLET': 'Chevrolet',
            'CHEVY': 'Chevrolet',
            'GMC': 'GMC',
            'CADILLAC': 'Cadillac',
            'DODGE': 'Dodge',
            'CHRYSLER': 'Chrysler',
            'JEEP': 'Jeep',
            'RAM': 'Ram',
            'BMW': 'BMW',
            'MERCEDES': 'Mercedes-Benz',
            'MERCEDES-BENZ': 'Mercedes-Benz',
            'AUDI': 'Audi',
            'VOLKSWAGEN': 'Volkswagen',
            'VW': 'Volkswagen',
            'VOLVO': 'Volvo',
            'SUBARU': 'Subaru',
            'MAZDA': 'Mazda',
            'MITSUBISHI': 'Mitsubishi',
            'HYUNDAI': 'Hyundai',
            'KIA': 'Kia',
            'SUZUKI': 'Suzuki'
        }
        
        return make_mappings.get(make_upper, make.title())
    
    def _normalize_engine(self, engine: str) -> str:
        """Normalize engine specifications"""
        if not engine:
            return None
            
        # Clean and standardize engine format
        engine = engine.strip()
        
        # Common patterns: "2.0L", "2.0 L", "2000cc", "V6", "2.0L Turbo"
        engine_pattern = r'(\d+\.?\d*)\s*[LlCc]+|\b(V\d+|I\d+|H\d+)\b'
        
        # Keep original if it matches common patterns, otherwise clean it
        if re.search(engine_pattern, engine):
            return engine
        else:
            return engine.replace('  ', ' ').strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'year_start': self.year_start,
            'year_end': self.year_end,
            'make': self.make,
            'model': self.model,
            'trim': self.trim,
            'engine': self.engine,
            'position': self.position,
            'notes': self.notes
        }
    
    def to_display_string(self) -> str:
        """Convert to human-readable string for HTML display"""
        parts = []
        
        # Year range
        if self.year_start and self.year_end:
            if self.year_start == self.year_end:
                parts.append(str(self.year_start))
            else:
                parts.append(f"{self.year_start}-{self.year_end}")
        elif self.year_start:
            parts.append(f"{self.year_start}+")
        
        # Make and Model
        if self.make:
            parts.append(self.make)
        if self.model:
            parts.append(self.model)
        
        # Trim
        if self.trim:
            parts.append(self.trim)
            
        # Engine
        if self.engine:
            parts.append(f"({self.engine})")
            
        # Position and Notes
        additional = []
        if self.position:
            additional.append(self.position)
        if self.notes:
            additional.append(self.notes)
            
        result = " ".join(parts)
        if additional:
            result += " - " + ", ".join(additional)
            
        return result

class BaseVehicleParser:
    """Base class for brand-specific vehicle application parsers"""
    
    def __init__(self, session: requests.Session):
        self.session = session
        
    def can_parse(self, url: str, brand: str) -> bool:
        """Check if this parser can handle the given URL/brand"""
        raise NotImplementedError
        
    def extract_applications(self, url: str, part_number: str, soup: BeautifulSoup) -> List[VehicleApplication]:
        """Extract vehicle applications from webpage"""
        raise NotImplementedError

class HawkPerformanceParser(BaseVehicleParser):
    """Parser for Hawk Performance brake pad applications"""
    
    def can_parse(self, url: str, brand: str) -> bool:
        brand_upper = brand.upper() if brand else ""
        return "hawkperformance.com" in url.lower() or "hawk" in brand_upper
    
    def extract_applications(self, url: str, part_number: str, soup: BeautifulSoup) -> List[VehicleApplication]:
        """Extract from Hawk Performance product pages"""
        applications = []
        
        try:
            # Strategy 1: Look for vehicle list sections
            vehicle_sections = soup.find_all(['ul', 'ol'], class_=lambda x: x and any(
                keyword in x.lower() for keyword in ['vehicle', 'fitment', 'application', 'compatibility']
            ))
            
            # Strategy 2: Look for sections with "this part is for" or similar text
            if not vehicle_sections:
                text_sections = soup.find_all(text=re.compile(r'this part is for|see all vehicles|vehicle applications', re.I))
                for text in text_sections:
                    parent = text.parent
                    if parent:
                        nearby_lists = parent.find_next_siblings(['ul', 'ol']) + parent.find_previous_siblings(['ul', 'ol'])
                        vehicle_sections.extend(nearby_lists)
            
            # Strategy 3: Look for any div/section with vehicle-like text
            if not vehicle_sections:
                vehicle_sections = soup.find_all(['div', 'section'], string=re.compile(r'\d{4}.*(?:Honda|Toyota|Ford|Chevrolet|BMW|Mercedes)', re.I))
            
            # Parse vehicle lists - FIXED: Handle concatenated vehicle text
            for section in vehicle_sections:
                if hasattr(section, 'find_all'):
                    list_items = section.find_all('li')
                    for item in list_items:
                        item_text = item.get_text(strip=True)
                        if item_text and len(item_text) > 10:
                            # CRITICAL FIX: Split concatenated vehicle applications
                            parsed_apps = self._parse_concatenated_vehicle_text(item_text)
                            applications.extend(parsed_apps)
                else:
                    # Handle direct text nodes
                    section_text = str(section).strip()
                    if len(section_text) > 20:
                        parsed_apps = self._parse_concatenated_vehicle_text(section_text)
                        applications.extend(parsed_apps)
                        
        except Exception as e:
            print(f"    Error parsing Hawk Performance applications: {e}")
            
        return applications
    
    def _parse_concatenated_vehicle_text(self, text: str) -> List[VehicleApplication]:
        """Parse concatenated vehicle application text that contains multiple vehicles"""
        applications = []
        
        try:
            # CRITICAL FIX: Split concatenated text into individual vehicle applications
            # Pattern: Year + Make + Model combination (e.g., "2019 Honda Civic", "2020 Acura ILX")
            vehicle_pattern = r'(\d{4}(?:-\d{4})?\s+[A-Z][a-zA-Z\s]+?(?=\d{4}|$))'
            
            # Split text by year patterns to separate individual vehicles
            potential_vehicles = re.split(r'(?=\d{4}(?:-\d{4})?\s+[A-Z])', text)
            
            for vehicle_text in potential_vehicles:
                vehicle_text = vehicle_text.strip()
                if len(vehicle_text) > 8:  # Must have at least year + make
                    # Try to parse individual vehicle
                    app = self._parse_single_vehicle_application(vehicle_text)
                    if app:
                        applications.append(app)
                        
            # Fallback: If splitting didn't work, try alternative approach
            if not applications and len(text) > 50:
                applications = self._parse_fallback_concatenated_text(text)
                
        except Exception as e:
            print(f"    Error parsing concatenated vehicle text: {e}")
            # Fallback to original method for single items
            app = self._parse_hawk_vehicle_text(text)
            if app:
                applications.append(app)
                
        return applications
    
    def _parse_single_vehicle_application(self, text: str) -> Optional[VehicleApplication]:
        """Parse a single, clean vehicle application text"""
        try:
            # Clean the text - remove common suffixes that cause issues
            text = re.sub(r'\s*(OE\s+Incl\..*?(?=\d{4}|$))', '', text)
            text = re.sub(r'\s*\(.*?\)', '', text)  # Remove parenthetical content temporarily
            text = text.strip()
            
            # Extract year(s) - single year or range
            year_match = re.match(r'(\d{4})(?:-(\d{4}))?\s+', text)
            if not year_match:
                return None
                
            year_start = int(year_match.group(1))
            year_end = int(year_match.group(2)) if year_match.group(2) else year_start
            
            # Remove year from text
            remaining_text = text[year_match.end():].strip()
            
            # Extract make and model - must have at least these two
            words = remaining_text.split()
            if len(words) < 2:
                return None
                
            make = words[0]
            model = words[1]
            
            # Everything else is trim (simplified for reliability)
            trim = " ".join(words[2:]) if len(words) > 2 else None
            
            # Basic engine extraction from original text (before cleaning)
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
            print(f"      Error parsing single vehicle '{text[:50]}...': {e}")
            return None
    
    def _parse_fallback_concatenated_text(self, text: str) -> List[VehicleApplication]:
        """Fallback parser for extremely problematic concatenated text"""
        applications = []
        
        try:
            # Find all year+make+model patterns in the text
            pattern = r'(\d{4})\s+([A-Z][a-zA-Z]+)\s+([A-Za-z0-9\-]+)'
            matches = re.findall(pattern, text)
            
            seen_combinations = set()
            for year, make, model in matches:
                # Avoid duplicates
                combo_key = f"{year}-{make}-{model}"
                if combo_key not in seen_combinations:
                    seen_combinations.add(combo_key)
                    
                    app = VehicleApplication(
                        year_start=int(year),
                        year_end=int(year),
                        make=make,
                        model=model,
                        trim=None,
                        engine=None
                    )
                    applications.append(app)
                    
        except Exception as e:
            print(f"    Error in fallback parser: {e}")
            
        return applications
    
    def _parse_hawk_vehicle_text(self, text: str) -> Optional[VehicleApplication]:
        """Parse individual vehicle application text from Hawk Performance"""
        try:
            # Common Hawk format: "2019 Honda Civic Si 2.0L Turbo"
            # Pattern: [Year(s)] [Make] [Model] [Trim] [Engine]
            
            # Extract year(s) - can be single year or range
            year_match = re.search(r'(\d{4})(?:-(\d{4}))?', text)
            year_start = int(year_match.group(1)) if year_match else None
            year_end = int(year_match.group(2)) if year_match and year_match.group(2) else year_start
            
            # Remove year from text for further parsing
            if year_match:
                remaining_text = text[year_match.end():].strip()
            else:
                remaining_text = text
            
            # Extract engine info (usually in parentheses or at the end)
            engine_match = re.search(r'(\d+\.?\d*L?\s*(?:V\d+|I\d+|Turbo|DOHC|SOHC|Hybrid)?)(?:\s|$)', remaining_text, re.I)
            engine = engine_match.group(1).strip() if engine_match else None
            
            # Remove engine from text
            if engine_match:
                remaining_text = remaining_text[:engine_match.start()] + remaining_text[engine_match.end():]
                remaining_text = remaining_text.strip()
            
            # Split remaining text into make, model, trim
            parts = remaining_text.split()
            if len(parts) >= 2:
                make = parts[0]
                model = parts[1]
                trim = " ".join(parts[2:]) if len(parts) > 2 else None
                
                return VehicleApplication(
                    year_start=year_start,
                    year_end=year_end,
                    make=make,
                    model=model,
                    trim=trim,
                    engine=engine
                )
                
        except Exception as e:
            print(f"      Error parsing vehicle text '{text}': {e}")
            
        return None

class BilsteinParser(BaseVehicleParser):
    """Parser for Bilstein shock/strut applications"""
    
    def can_parse(self, url: str, brand: str) -> bool:
        brand_upper = brand.upper() if brand else ""
        return "bilstein" in url.lower() or "bilstein" in brand_upper
    
    def extract_applications(self, url: str, part_number: str, soup: BeautifulSoup) -> List[VehicleApplication]:
        """Extract from Bilstein product pages"""
        applications = []
        
        try:
            # Look for fitment info sections
            fitment_sections = soup.find_all(['div', 'section'], class_=lambda x: x and any(
                keyword in x.lower() for keyword in ['fitment', 'compatibility', 'application', 'vehicle']
            ))
            
            # Also search by text content
            fitment_text = soup.find_all(text=re.compile(r'fitment|compatibility|years?|make|model', re.I))
            for text in fitment_text:
                parent = text.parent
                if parent and parent not in fitment_sections:
                    fitment_sections.append(parent)
            
            for section in fitment_sections:
                section_text = section.get_text()
                
                # Parse Bilstein format: "Years: 2005 – 2023, Make: TOYOTA, Model: Tacoma"
                year_match = re.search(r'years?:?\s*(\d{4})\s*[–-]\s*(\d{4})', section_text, re.I)
                make_match = re.search(r'make:?\s*([A-Za-z]+)', section_text, re.I)
                model_match = re.search(r'model:?\s*([A-Za-z0-9\s]+?)(?:\n|$|,)', section_text, re.I)
                
                if year_match and make_match and model_match:
                    applications.append(VehicleApplication(
                        year_start=int(year_match.group(1)),
                        year_end=int(year_match.group(2)),
                        make=make_match.group(1).strip(),
                        model=model_match.group(1).strip()
                    ))
                    
        except Exception as e:
            print(f"    Error parsing Bilstein applications: {e}")
            
        return applications

class GenericTableParser(BaseVehicleParser):
    """Generic parser for table-based vehicle applications"""
    
    def can_parse(self, url: str, brand: str) -> bool:
        # This is a fallback parser, so it can try to parse any brand
        return True
    
    def extract_applications(self, url: str, part_number: str, soup: BeautifulSoup) -> List[VehicleApplication]:
        """Extract from table-based fitment information"""
        applications = []
        
        try:
            # Look for tables with vehicle information
            tables = soup.find_all('table')
            
            for table in tables:
                # Check if table contains vehicle-related headers
                headers = table.find_all(['th', 'td'])
                header_text = " ".join([h.get_text().lower() for h in headers[:10]])  # First 10 cells
                
                if any(keyword in header_text for keyword in ['year', 'make', 'model', 'vehicle', 'fitment']):
                    rows = table.find_all('tr')[1:]  # Skip header row
                    
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 3:  # Minimum: year, make, model
                            cell_texts = [cell.get_text(strip=True) for cell in cells]
                            app = self._parse_table_row(cell_texts)
                            if app:
                                applications.append(app)
                                
        except Exception as e:
            print(f"    Error parsing table applications: {e}")
            
        return applications
    
    def _parse_table_row(self, cell_texts: List[str]) -> Optional[VehicleApplication]:
        """Parse a table row into vehicle application"""
        try:
            # Try to identify year, make, model from cell contents
            year_start = None
            year_end = None
            make = None
            model = None
            
            for cell in cell_texts:
                # Check for year patterns
                year_match = re.search(r'(\d{4})(?:-(\d{4}))?', cell)
                if year_match and not year_start:
                    year_start = int(year_match.group(1))
                    year_end = int(year_match.group(2)) if year_match.group(2) else year_start
                
                # Check for common make names
                elif any(make_name in cell.upper() for make_name in [
                    'HONDA', 'TOYOTA', 'FORD', 'CHEVROLET', 'NISSAN', 'BMW', 'MERCEDES'
                ]) and not make:
                    make = cell
                
                # Remaining text could be model
                elif len(cell) > 2 and not make and not model:
                    model = cell
            
            if year_start and make:
                return VehicleApplication(
                    year_start=year_start,
                    year_end=year_end,
                    make=make,
                    model=model
                )
                
        except Exception:
            pass
            
        return None

class VehicleApplicationAgent:
    """Main agent for extracting vehicle applications from official websites"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Initialize parsers in priority order
        self.parsers = [
            HawkPerformanceParser(self.session),
            BilsteinParser(self.session),
            GenericTableParser(self.session)  # Fallback parser
        ]
        
        # Cache for extracted applications
        self.cache_file = "vehicle_applications_cache.json"
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load cached vehicle applications"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def _save_cache(self):
        """Save vehicle applications cache"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: Could not save vehicle applications cache: {e}")
    
    def extract_applications_from_url(self, url: str, part_number: str, brand: str) -> List[VehicleApplication]:
        """Extract vehicle applications from a specific URL with enhanced error handling"""
        
        # Input validation
        if not url or not part_number or not brand:
            print(f"    Error: Missing required parameters (url={bool(url)}, part_number={bool(part_number)}, brand={bool(brand)})")
            return []
        
        # Check cache first
        cache_key = f"{url}:{part_number}"
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            # Check if cache is recent (less than 7 days old)
            if time.time() - cached_data['timestamp'] < 7 * 24 * 3600:
                print(f"    Using cached applications for {part_number}")
                try:
                    return [VehicleApplication(**app) for app in cached_data['applications']]
                except Exception as e:
                    print(f"    Error loading cached data: {e}. Will re-fetch.")
                    # Remove corrupted cache entry
                    del self.cache[cache_key]
        
        applications = []
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                print(f"    Fetching vehicle applications from: {url} (attempt {retry_count + 1}/{max_retries})")
                
                # Enhanced request with better error handling
                resp = self.session.get(
                    url, 
                    timeout=30,
                    allow_redirects=True,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive'
                    }
                )
                resp.raise_for_status()
                
                # Validate response content
                if len(resp.content) < 100:
                    raise ValueError(f"Response too short ({len(resp.content)} bytes)")
                
                # Check for common error pages
                content_lower = resp.text.lower()
                if any(error_indicator in content_lower for error_indicator in [
                    'page not found', '404 error', 'access denied', 'not available',
                    'temporarily unavailable', 'maintenance mode'
                ]):
                    raise ValueError("Page appears to be unavailable or in error state")
                
                soup = BeautifulSoup(resp.content, 'html.parser')
                
                # Validate parsed content
                if not soup or not soup.find():
                    raise ValueError("Failed to parse HTML content")
                
                # Try each parser in order with individual error handling
                parser_errors = []
                for parser in self.parsers:
                    if parser.can_parse(url, brand):
                        try:
                            print(f"    Using {parser.__class__.__name__}")
                            applications = parser.extract_applications(url, part_number, soup)
                            if applications:
                                print(f"    Successfully extracted {len(applications)} applications with {parser.__class__.__name__}")
                                break
                            else:
                                print(f"    {parser.__class__.__name__} found no applications")
                        except Exception as parser_error:
                            error_msg = f"{parser.__class__.__name__} failed: {parser_error}"
                            parser_errors.append(error_msg)
                            print(f"    {error_msg}")
                            continue
                
                # If we got applications, validate them
                if applications:
                    validated_applications = []
                    for app in applications:
                        if self._validate_application(app):
                            validated_applications.append(app)
                        else:
                            print(f"    Skipping invalid application: {app.to_display_string()}")
                    
                    applications = validated_applications
                    
                    if applications:
                        # Cache successful results
                        try:
                            self.cache[cache_key] = {
                                'timestamp': time.time(),
                                'applications': [app.to_dict() for app in applications],
                                'url': url,
                                'part_number': part_number,
                                'brand': brand,
                                'parser_used': next((p.__class__.__name__ for p in self.parsers 
                                                   if p.can_parse(url, brand) and applications), 'Unknown')
                            }
                            self._save_cache()
                            print(f"    Cached {len(applications)} validated applications")
                        except Exception as cache_error:
                            print(f"    Warning: Failed to cache results: {cache_error}")
                        
                        return applications
                
                # If no applications found, log parser errors
                if parser_errors:
                    print(f"    All parsers failed:")
                    for error in parser_errors:
                        print(f"      - {error}")
                
                print(f"    No vehicle applications found on attempt {retry_count + 1}")
                break  # Don't retry if parsing succeeded but found no applications
                
            except requests.exceptions.Timeout:
                retry_count += 1
                print(f"    Timeout on attempt {retry_count}. Retrying in {retry_count * 2} seconds...")
                if retry_count < max_retries:
                    time.sleep(retry_count * 2)  # Exponential backoff
                    
            except requests.exceptions.ConnectionError as e:
                retry_count += 1
                print(f"    Connection error on attempt {retry_count}: {e}")
                if retry_count < max_retries:
                    time.sleep(retry_count * 2)
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code in [429, 503, 502, 504]:  # Retryable errors
                    retry_count += 1
                    print(f"    HTTP {e.response.status_code} on attempt {retry_count}. Retrying...")
                    if retry_count < max_retries:
                        time.sleep(retry_count * 5)  # Longer wait for server errors
                else:
                    print(f"    Non-retryable HTTP error: {e}")
                    break
                    
            except Exception as e:
                print(f"    Unexpected error on attempt {retry_count + 1}: {e}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(retry_count)
        
        # Cache negative results to avoid repeated failures
        if not applications:
            try:
                self.cache[cache_key] = {
                    'timestamp': time.time(),
                    'applications': [],
                    'url': url,
                    'part_number': part_number,
                    'brand': brand,
                    'status': 'no_applications_found'
                }
                self._save_cache()
            except Exception:
                pass  # Don't fail if we can't cache negative results
        
        return applications
    
    def _validate_application(self, app: VehicleApplication) -> bool:
        """Validate a vehicle application for basic data quality"""
        try:
            # Must have year and make at minimum
            if not app.year_start or not app.make:
                return False
            
            # Year validation
            if app.year_start < 1900 or app.year_start > 2030:
                return False
                
            if app.year_end and (app.year_end < app.year_start or app.year_end > 2030):
                return False
            
            # Make validation - must be alphabetic
            if not app.make.replace(' ', '').replace('-', '').isalpha():
                return False
            
            # Model validation if present
            if app.model and len(app.model.strip()) < 1:
                return False
            
            return True
            
        except Exception:
            return False
    
    def find_and_extract_applications(self, product_info: Dict[str, str], 
                                     image_agent=None) -> List[VehicleApplication]:
        """Find official product pages and extract vehicle applications with enhanced error handling"""
        
        # Input validation
        if not product_info or not isinstance(product_info, dict):
            print(f"    Error: Invalid product_info parameter")
            return []
        
        part_number = product_info.get(PART_NUMBER_COLUMN_SOURCE, '').strip()
        brand = product_info.get(BRAND_COLUMN_SOURCE, '').strip()
        
        if not part_number or not brand:
            print(f"    Missing required data: part_number='{part_number}', brand='{brand}'")
            return []
        
        # Sanitize part number for URL construction
        safe_part_number = re.sub(r'[^a-zA-Z0-9\-_]', '', part_number.replace(' ', '-'))
        if not safe_part_number:
            print(f"    Error: Part number '{part_number}' cannot be sanitized for URL construction")
            return []
        
        print(f"  VEHICLE APP AGENT: Extracting applications for {brand} {part_number}")
        
        try:
            # Strategy 1: Use image agent's brand registry for official sites
            if image_agent and hasattr(image_agent, 'brand_registry'):
                brand_upper = brand.upper().strip()
                if brand_upper in image_agent.brand_registry:
                    brand_info = image_agent.brand_registry[brand_upper]
                    
                    print(f"    Found {brand_upper} in brand registry with {len(brand_info['domains'])} official domains")
                    
                    # Try official domains with multiple URL patterns
                    for domain in brand_info['domains']:
                        url_patterns = [
                            f"https://{domain}/product/{safe_part_number.lower()}",
                            f"https://{domain}/products/{safe_part_number.lower()}",
                            f"https://{domain}/parts/{safe_part_number.lower()}",
                            f"https://{domain}/catalog/{safe_part_number.lower()}",
                            f"https://www.{domain}/product/{safe_part_number.lower()}",
                            f"https://www.{domain}/products/{safe_part_number.lower()}",
                            f"https://www.{domain}/parts/{safe_part_number.lower()}"
                        ]
                        
                        for test_url in url_patterns:
                            try:
                                # Quick HEAD request to check if page exists
                                resp = self.session.head(test_url, timeout=10, allow_redirects=True)
                                if resp.status_code == 200:
                                    print(f"    Found potential product page: {test_url}")
                                    applications = self.extract_applications_from_url(test_url, part_number, brand)
                                    if applications:
                                        print(f"    SUCCESS: Found {len(applications)} applications from official site")
                                        return applications
                                    else:
                                        print(f"    Page found but no applications extracted")
                                        
                            except requests.exceptions.Timeout:
                                print(f"    Timeout checking: {test_url}")
                                continue
                            except requests.exceptions.ConnectionError:
                                print(f"    Connection error for: {test_url}")
                                continue
                            except Exception as e:
                                print(f"    Error checking {test_url}: {e}")
                                continue
                    
                    print(f"    No working product pages found for {part_number} on official {brand} domains")
                else:
                    print(f"    Brand '{brand_upper}' not found in brand registry")
            else:
                print(f"    No image agent or brand registry available")
            
            # Strategy 2: Fallback search using brand-specific search engines
            print(f"    Trying fallback search strategies for {brand} {part_number}")
            fallback_applications = self._try_fallback_search(brand, part_number)
            if fallback_applications:
                print(f"    SUCCESS: Found {len(fallback_applications)} applications from fallback search")
                return fallback_applications
            
        except Exception as e:
            print(f"    Unexpected error in vehicle application extraction: {e}")
            import traceback
            print(f"    Traceback: {traceback.format_exc()}")
        
        print(f"    No vehicle applications found for {brand} {part_number}")
        return []
    
    def _try_fallback_search(self, brand: str, part_number: str) -> List[VehicleApplication]:
        """Fallback search strategy when official sites don't work"""
        applications = []
        
        try:
            # Try common automotive parts website patterns
            fallback_domains = []
            
            brand_lower = brand.lower().replace(' ', '')
            common_patterns = [
                f"{brand_lower}.com",
                f"{brand_lower}parts.com",
                f"parts.{brand_lower}.com",
                f"{brand_lower}aftermarket.com"
            ]
            
            for pattern in common_patterns:
                try:
                    # Quick DNS lookup to see if domain exists (with timeout)
                    import socket
                    socket.setdefaulttimeout(2)  # 2 second timeout
                    socket.gethostbyname(pattern)
                    fallback_domains.append(pattern)
                except (socket.gaierror, socket.timeout):
                    continue
            
            if fallback_domains:
                print(f"    Found {len(fallback_domains)} potential fallback domains")
                
                # Try each fallback domain
                for domain in fallback_domains[:3]:  # Limit to 3 to avoid too many requests
                    safe_part = re.sub(r'[^a-zA-Z0-9\-_]', '', part_number.replace(' ', '-'))
                    test_url = f"https://{domain}/product/{safe_part.lower()}"
                    
                    try:
                        applications = self.extract_applications_from_url(test_url, part_number, brand)
                        if applications:
                            return applications
                    except Exception:
                        continue
            
        except Exception as e:
            print(f"    Error in fallback search: {e}")
        
        return applications