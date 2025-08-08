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
        """Extract vehicle applications from a specific URL"""
        
        # Check cache first
        cache_key = f"{url}:{part_number}"
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            # Check if cache is recent (less than 7 days old)
            if time.time() - cached_data['timestamp'] < 7 * 24 * 3600:
                print(f"    Using cached applications for {part_number}")
                return [VehicleApplication(**app) for app in cached_data['applications']]
        
        applications = []
        
        try:
            print(f"    Fetching vehicle applications from: {url}")
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Try each parser in order
            for parser in self.parsers:
                if parser.can_parse(url, brand):
                    print(f"    Using {parser.__class__.__name__}")
                    applications = parser.extract_applications(url, part_number, soup)
                    if applications:
                        break
            
            # Cache results
            if applications:
                self.cache[cache_key] = {
                    'timestamp': time.time(),
                    'applications': [app.to_dict() for app in applications]
                }
                self._save_cache()
                print(f"    Extracted {len(applications)} vehicle applications")
            else:
                print(f"    No vehicle applications found")
                
        except Exception as e:
            print(f"    Error extracting applications from {url}: {e}")
        
        return applications
    
    def find_and_extract_applications(self, product_info: Dict[str, str], 
                                     image_agent=None) -> List[VehicleApplication]:
        """Find official product pages and extract vehicle applications"""
        
        part_number = product_info.get(PART_NUMBER_COLUMN_SOURCE, '')
        brand = product_info.get(BRAND_COLUMN_SOURCE, '')
        
        if not part_number or not brand:
            print(f"    Missing part number or brand for vehicle application extraction")
            return []
        
        print(f"  VEHICLE APP AGENT: Extracting applications for {brand} {part_number}")
        
        # If we have an image agent, use its official site detection
        if image_agent and hasattr(image_agent, 'brand_registry'):
            brand_upper = brand.upper().strip()
            if brand_upper in image_agent.brand_registry:
                brand_info = image_agent.brand_registry[brand_upper]
                
                # Try official domains first
                for domain in brand_info['domains']:
                    # Construct likely product page URLs
                    test_urls = [
                        f"https://{domain}/product/{part_number.lower()}",
                        f"https://{domain}/products/{part_number.lower()}",
                        f"https://{domain}/parts/{part_number.lower()}",
                        f"https://www.{domain}/product/{part_number.lower()}",
                        f"https://www.{domain}/products/{part_number.lower()}"
                    ]
                    
                    for test_url in test_urls:
                        try:
                            resp = self.session.head(test_url, timeout=10)
                            if resp.status_code == 200:
                                print(f"    Found product page: {test_url}")
                                applications = self.extract_applications_from_url(test_url, part_number, brand)
                                if applications:
                                    return applications
                        except:
                            continue
        
        print(f"    No official product pages found for {part_number}")
        return []