# File: agents/image_agent.py

import os
import io
import json
import requests
import time
import re
from PIL import Image, ImageOps
from urllib.parse import urljoin, unquote, urlparse
from bs4 import BeautifulSoup
from serpapi import GoogleSearch 

# Import settings from the central config file
from config import (
    IMAGE_DOWNLOAD_PATH_CONFIG, MIN_ORIGINAL_IMAGE_WIDTH, MIN_ORIGINAL_IMAGE_HEIGHT,
    BG_COLOR_THRESHOLD, BG_BORDER_PERCENTAGE, BG_WHITE_PIXEL_PERCENTAGE,
    PART_NUMBER_COLUMN_SOURCE, BRAND_COLUMN_SOURCE, DESCRIPTION_COLUMN_EN_SOURCE
)

# Import monitoring system
from monitoring import OperationTimer, get_image_logger, LogContext

class ImageSourcingAgent:
    def __init__(self, serpapi_key):
        self.serpapi_key = serpapi_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        if not os.path.exists(IMAGE_DOWNLOAD_PATH_CONFIG):
            os.makedirs(IMAGE_DOWNLOAD_PATH_CONFIG)
        
        # Initialize brand registry with official domains and patterns
        self.brand_registry = self._initialize_brand_registry()
        
        # Part number cleaning patterns
        self.part_number_patterns = [
            r'[A-Z0-9\-]{3,}',  # Basic alphanumeric with dashes
            r'\b[A-Z]{1,3}[\-\s]*\d+[A-Z0-9\-]*\b',  # Brand prefix + numbers
            r'\b\d+[A-Z]+[\-\d]*\b'  # Numbers + letters pattern
        ]

    def _initialize_brand_registry(self):
        """Initialize comprehensive brand registry with official domains and authority scores"""
        return {
            # OEM Manufacturers (Tier 1 - Highest Authority)
            'FORD': {
                'domains': ['parts.ford.com', 'fordparts.com', 'ford.com', 'motorcraft.com', 'ford.oempartsonline.com'],
                'authority': 95,
                'search_patterns': ['site:parts.ford.com', 'site:fordparts.com', 'site:motorcraft.com', 'site:ford.oempartsonline.com']
            },
            'CHEVROLET': {
                'domains': ['gmpartsdirect.com', 'chevrolet.com', 'gmparts.com', 'acdelco.com'],
                'authority': 95,
                'search_patterns': ['site:gmpartsdirect.com', 'site:acdelco.com']
            },
            'GMC': {
                'domains': ['gmpartsdirect.com', 'gmc.com', 'gmparts.com', 'acdelco.com'],
                'authority': 95,
                'search_patterns': ['site:gmpartsdirect.com', 'site:acdelco.com']
            },
            'TOYOTA': {
                'domains': ['parts.toyota.com', 'toyota.com', 'denso.com', 'toyotapartsdeal.com'],
                'authority': 95,
                'search_patterns': ['site:parts.toyota.com', 'site:denso.com']
            },
            'HONDA': {
                'domains': ['parts.honda.com', 'honda.com', 'hondapartsnow.com'],
                'authority': 95,
                'search_patterns': ['site:parts.honda.com', 'site:hondapartsnow.com']
            },
            'NISSAN': {
                'domains': ['parts.nissanusa.com', 'nissan.com', 'nissanpartsdeal.com'],
                'authority': 95,
                'search_patterns': ['site:parts.nissanusa.com', 'site:nissanpartsdeal.com']
            },
            'BMW': {
                'domains': ['bmwparts.com', 'bmw.com', 'realoem.com', 'bmwpartsdeal.com'],
                'authority': 95,
                'search_patterns': ['site:bmwparts.com', 'site:realoem.com']
            },
            'MERCEDES BENZ': {
                'domains': ['mbparts.com', 'mercedes-benz.com', 'mercedespartscenter.com'],
                'authority': 95,
                'search_patterns': ['site:mbparts.com', 'site:mercedespartscenter.com']
            },
            'AUDI': {
                'domains': ['parts.audiusa.com', 'audi.com', 'audipartsdeal.com'],
                'authority': 95,
                'search_patterns': ['site:parts.audiusa.com', 'site:audipartsdeal.com']
            },
            'VOLKSWAGEN': {
                'domains': ['parts.vw.com', 'vw.com', 'vwparts.com'],
                'authority': 95,
                'search_patterns': ['site:parts.vw.com', 'site:vwparts.com']
            },
            'CHRYSLER': {
                'domains': ['moparpartsgiant.com', 'moparonlineparts.com', 'chrysler.com'],
                'authority': 95,
                'search_patterns': ['site:moparpartsgiant.com', 'site:moparonlineparts.com']
            },
            'DODGE': {
                'domains': ['moparpartsgiant.com', 'moparonlineparts.com', 'dodge.com'],
                'authority': 95,
                'search_patterns': ['site:moparpartsgiant.com', 'site:moparonlineparts.com']
            },
            'JEEP': {
                'domains': ['moparpartsgiant.com', 'moparonlineparts.com', 'jeep.com'],
                'authority': 95,
                'search_patterns': ['site:moparpartsgiant.com', 'site:moparonlineparts.com']
            },
            
            # Aftermarket Brands (Tier 2 - High Authority)
            'K&N': {
                'domains': ['knfilters.com', 'kandn.com'],
                'authority': 85,
                'search_patterns': ['site:knfilters.com']
            },
            'BILSTEIN': {
                'domains': ['bilstein.com', 'bilsteinus.com'],
                'authority': 85,
                'search_patterns': ['site:bilstein.com']
            },
            'BREMBO': {
                'domains': ['brembo.com', 'bremboparts.com'],
                'authority': 85,
                'search_patterns': ['site:brembo.com']
            },
            'BOSCH': {
                'domains': ['bosch.com', 'boschautomotiveparts.com'],
                'authority': 85,
                'search_patterns': ['site:boschautomotiveparts.com']
            },
            'MANN-FILTER': {
                'domains': ['mann-filter.com', 'mann-hummel.com'],
                'authority': 85,
                'search_patterns': ['site:mann-filter.com']
            },
            'MAHLE': {
                'domains': ['mahle-aftermarket.com', 'mahle.com'],
                'authority': 85,
                'search_patterns': ['site:mahle-aftermarket.com']
            }
        }

    def _is_white_background(self, image_bytes):
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            width, height = img.size
            if width < 10 or height < 10: return False
            border_w = min(int(width * BG_BORDER_PERCENTAGE), width // 4)
            border_h = min(int(height * BG_BORDER_PERCENTAGE), height // 4)
            
            border_pixels = []
            border_pixels.extend(img.crop((0, 0, width, border_h)).getdata())
            border_pixels.extend(img.crop((0, height - border_h, width, height)).getdata())
            border_pixels.extend(img.crop((0, border_h, border_w, height - border_h)).getdata())
            border_pixels.extend(img.crop((width - border_w, border_h, width, height - border_h)).getdata())

            if not border_pixels: return False
            
            white_pixel_count = sum(1 for r,g,b in border_pixels if r >= BG_COLOR_THRESHOLD and g >= BG_COLOR_THRESHOLD and b >= BG_COLOR_THRESHOLD)
            return (white_pixel_count / len(border_pixels)) >= BG_WHITE_PIXEL_PERCENTAGE
        except Exception:
            return False

    def _check_original_image_dimensions(self, image_bytes):
        try:
            img = Image.open(io.BytesIO(image_bytes))
            return img.width >= MIN_ORIGINAL_IMAGE_WIDTH and img.height >= MIN_ORIGINAL_IMAGE_HEIGHT
        except Exception:
            return False

    def _process_image_maintaining_aspect_ratio(self, image_bytes):
        try:
            img = Image.open(io.BytesIO(image_bytes))
            if img is None:
                return None
                
            img = ImageOps.exif_transpose(img)

            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Maintain original aspect ratio, just ensure minimum quality
            # Don't force specific dimensions - let the image keep its natural size
            # Only resize if the image is too small
            original_width, original_height = img.size
            
            # If image is too small, scale it up while maintaining aspect ratio
            min_width = 800
            min_height = 600
            
            if original_width < min_width or original_height < min_height:
                # Calculate scale factor to meet minimum dimensions
                scale_x = min_width / original_width if original_width < min_width else 1
                scale_y = min_height / original_height if original_height < min_height else 1
                scale_factor = max(scale_x, scale_y)
                
                new_width = int(original_width * scale_factor)
                new_height = int(original_height * scale_factor)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=90, optimize=True)
            return buffer.getvalue()
        except Exception as e:
            print(f"      Error processing image: {e}")
            return None
    
    def _download_and_save_image(self, image_url, product_sanitized_part_number, image_index, source_page_url, target_part_number=None, brand=None):
        try:
            abs_url = urljoin(source_page_url, image_url.strip())
            resp = self.session.get(abs_url, timeout=20, stream=True)
            resp.raise_for_status()
            original_image_bytes = resp.content

            # Enhanced validation pipeline
            validation_results = self._enhanced_image_validation(
                original_image_bytes, 
                target_part_number, 
                brand, 
                abs_url
            )
            
            if not validation_results['is_valid']:
                print(f"      REJECTED: {validation_results['rejection_reason']} for {product_sanitized_part_number}")
                return None
            
            processed_image_bytes = self._process_image_maintaining_aspect_ratio(original_image_bytes)
            if not processed_image_bytes: 
                print(f"      REJECTED: Image processing failed for {product_sanitized_part_number}")
                return None

            filename = f"image_{image_index}.jpg"
            product_folder = os.path.join(IMAGE_DOWNLOAD_PATH_CONFIG, product_sanitized_part_number)
            os.makedirs(product_folder, exist_ok=True)
            full_path = os.path.join(product_folder, filename)
            
            # Calculate comprehensive quality score
            quality_score = validation_results.get('quality_score', 0)
            authority_score = self._get_domain_authority(source_page_url, brand) if brand else 0
            
            with open(full_path, 'wb') as f:
                f.write(processed_image_bytes)
            
            print(f"      SUCCESS: Image saved (quality:{quality_score:.1f}/authority:{authority_score}): {os.path.join(product_sanitized_part_number, filename)}")
            return full_path
        except Exception as e:
            print(f"      ERROR downloading image: {e}")
            return None
    
    def _enhanced_image_validation(self, image_bytes, target_part_number, brand, image_url):
        """Enhanced image validation with multiple quality checks"""
        validation_result = {
            'is_valid': False,
            'rejection_reason': '',
            'quality_score': 0.0,
            'validation_details': {}
        }
        
        try:
            # 1. Basic dimension and format validation
            if not self._check_original_image_dimensions(image_bytes):
                validation_result['rejection_reason'] = 'Image too small'
                return validation_result
            
            # 2. Background validation
            if not self._is_white_background(image_bytes):
                validation_result['rejection_reason'] = 'Non-white background'
                return validation_result
            
            img = Image.open(io.BytesIO(image_bytes))
            validation_result['validation_details']['dimensions'] = f"{img.width}x{img.height}"
            
            quality_factors = []
            
            # 3. Image quality assessment
            quality_score = self._assess_image_quality(img)
            quality_factors.append(('image_quality', quality_score, 0.3))
            
            # 4. Brand logo detection
            brand_score = self._detect_brand_presence(img, brand) if brand else 0.5
            quality_factors.append(('brand_presence', brand_score, 0.2))
            
            # 5. Part number validation (OCR-based)
            part_number_score = self._validate_part_number_in_image(img, target_part_number) if target_part_number else 0.5
            quality_factors.append(('part_number_match', part_number_score, 0.2))
            
            # 6. Automotive part detection
            automotive_score = self._detect_automotive_part(img)
            quality_factors.append(('automotive_part', automotive_score, 0.2))
            
            # 7. Generic/stock image detection
            generic_score = 1.0 - self._detect_generic_image(img, image_url)
            quality_factors.append(('not_generic', generic_score, 0.1))
            
            # Calculate weighted quality score
            total_score = sum(score * weight for _, score, weight in quality_factors)
            validation_result['quality_score'] = total_score
            validation_result['validation_details']['quality_factors'] = quality_factors
            
            # Validation thresholds
            minimum_quality_threshold = 0.4  # Require at least 40% quality
            
            if total_score >= minimum_quality_threshold:
                validation_result['is_valid'] = True
            else:
                validation_result['rejection_reason'] = f'Quality score too low ({total_score:.2f} < {minimum_quality_threshold})'
                
                # Log detailed validation results for debugging
                print(f"        Quality breakdown:")
                for factor_name, score, weight in quality_factors:
                    print(f"          {factor_name}: {score:.2f} (weight: {weight})")
            
            return validation_result
            
        except Exception as e:
            validation_result['rejection_reason'] = f'Validation error: {e}'
            return validation_result
    
    def _assess_image_quality(self, img):
        """Assess overall image quality using various metrics"""
        try:
            # Convert to grayscale for analysis
            gray = img.convert('L')
            
            # Simple quality metrics without numpy dependency
            width, height = img.size
            
            # 1. Resolution score (higher resolution = better quality)
            resolution_score = min((width * height) / 1000000.0, 1.0)  # Normalize to 1MP
            
            # 2. Aspect ratio check (avoid extremely skewed images)
            aspect_ratio = width / height
            aspect_score = 1.0 if 0.5 <= aspect_ratio <= 2.0 else 0.5
            
            # 3. Basic image size validation
            size_score = 1.0 if width >= 400 and height >= 400 else 0.7
            
            # Combine quality factors
            quality_score = (resolution_score * 0.4 + aspect_score * 0.3 + size_score * 0.3)
            
            return min(quality_score, 1.0)
            
        except Exception:
            return 0.5  # Default moderate quality if assessment fails
    
    def _detect_brand_presence(self, img, brand):
        """Detect brand presence in image (simplified text detection)"""
        try:
            if not brand:
                return 0.5
            
            # For now, return moderate confidence
            # In a full implementation, you would:
            # 1. Use Tesseract OCR to extract text
            # 2. Search for brand name in extracted text
            # 3. Look for brand logos using template matching
            
            return 0.6  # Moderate confidence placeholder
            
        except Exception:
            return 0.5
    
    def _validate_part_number_in_image(self, img, target_part_number):
        """Validate if part number appears in the image"""
        try:
            if not target_part_number:
                return 0.5
            
            # Simplified implementation
            # In production, you would:
            # 1. Use OCR to extract all text from image
            # 2. Search for exact or partial part number matches
            # 3. Account for different fonts and orientations
            
            return 0.5  # Moderate confidence placeholder
            
        except Exception:
            return 0.5
    
    def _detect_automotive_part(self, img):
        """Detect if image contains automotive parts"""
        try:
            # Simplified automotive part detection based on common characteristics
            width, height = img.size
            
            # Automotive parts often have metallic colors or specific shapes
            # This is a basic implementation - production would use ML models
            
            # Check if image has good contrast (automotive parts usually do)
            extrema = img.convert('L').getextrema()
            contrast_ratio = (extrema[1] - extrema[0]) / 255.0
            
            # Higher contrast often indicates mechanical parts
            return min(contrast_ratio * 1.5, 1.0)
            
        except Exception:
            return 0.5
    
    def _detect_generic_image(self, img, image_url):
        """Detect if image is a generic/stock image"""
        try:
            generic_indicators = 0
            
            # Check URL for generic image indicators
            url_lower = image_url.lower()
            generic_url_patterns = [
                'placeholder', 'default', 'noimage', 'coming-soon',
                'stock', 'generic', 'sample', 'demo', 'thumbnail'
            ]
            
            for pattern in generic_url_patterns:
                if pattern in url_lower:
                    generic_indicators += 0.4
            
            # Check image dimensions for common stock image sizes
            width, height = img.size
            common_stock_sizes = [
                (300, 300), (400, 400), (500, 500),  # Square stock images
                (150, 150), (200, 200),  # Small thumbnails
                (800, 600), (1024, 768)  # Common stock ratios
            ]
            
            for stock_width, stock_height in common_stock_sizes:
                if width == stock_width and height == stock_height:
                    generic_indicators += 0.3
                    break
            
            # Very small images are often generic/placeholder
            if width < 200 or height < 200:
                generic_indicators += 0.2
            
            return min(generic_indicators, 1.0)
            
        except Exception:
            return 0.0  # If detection fails, assume not generic

    def _scrape_page_for_images(self, page_url, product_info, max_images_to_process):
        downloaded_paths = []
        part_number = product_info.get(PART_NUMBER_COLUMN_SOURCE, '')
        brand = product_info.get(BRAND_COLUMN_SOURCE, '')
        
        try:
            resp = self.session.get(page_url, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Extract all text from page for part number validation
            page_text = soup.get_text()
            found_part_numbers = self._extract_part_numbers_from_text(page_text)
            
            # Validate that the target part number appears on the page
            if not self._validate_part_number_match(found_part_numbers, part_number):
                print(f"      WARNING: Part number {part_number} not found on page {page_url}")
                # Still continue but with lower priority
            
            candidate_urls = set()

            # Look for Open Graph images first (usually high quality)
            og_image = soup.find("meta", property="og:image")
            if og_image and hasattr(og_image, 'get') and og_image.get("content"):
                candidate_urls.add(og_image["content"])
            
            # Look for Twitter Card images
            twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
            if twitter_image and hasattr(twitter_image, 'get') and twitter_image.get("content"):
                candidate_urls.add(twitter_image["content"])
            
            # Look for high-resolution images in img tags
            for img_tag in soup.find_all("img"):
                src = img_tag.get("src")
                alt_text = img_tag.get("alt", "")
                
                if src and not src.startswith("data:image"):
                    # Prefer larger images - check for size hints in attributes
                    width = img_tag.get("width")
                    height = img_tag.get("height")
                    
                    # If we have size info and it's small, skip it
                    if width and height:
                        try:
                            w, h = int(width), int(height)
                            if w < 300 or h < 300:  # Skip very small images
                                continue
                        except ValueError:
                            pass
                    
                    # Priority boost for images with part number in alt text or nearby text
                    img_priority = 0
                    if part_number.upper() in alt_text.upper():
                        img_priority = 10
                    elif any(pn in alt_text.upper() for pn in found_part_numbers):
                        img_priority = 5
                        
                    candidate_urls.add((src, img_priority))

            # Sort candidates by priority (higher priority first)
            sorted_candidates = sorted(candidate_urls, key=lambda x: x[1] if isinstance(x, tuple) else 0, reverse=True)
            
            for i, candidate in enumerate(sorted_candidates):
                if len(downloaded_paths) >= max_images_to_process: break
                
                img_url = candidate[0] if isinstance(candidate, tuple) else candidate
                path = self._download_and_save_image(img_url, product_info['sanitized_part_number'], i, page_url, part_number, brand)
                if path:
                    downloaded_paths.append(path)
                    
            return downloaded_paths
        except Exception as e:
            print(f"      Error scraping page {page_url}: {e}")
            return downloaded_paths

    def _perform_serpapi_search(self, query, search_type="images"):
        try:
            if search_type == "images":
                # Search specifically for large images
                params = {
                    "q": query, 
                    "api_key": self.serpapi_key, 
                    "num": 5, 
                    "engine": "google", 
                    "gl": "mx", 
                    "hl": "en",
                    "tbm": "isch",  # Image search
                    "tbs": "isz:l"  # Large images only
                }
            else:
                # Web search for official brand pages
                params = {
                    "q": query, 
                    "api_key": self.serpapi_key, 
                    "num": 3, 
                    "engine": "google", 
                    "gl": "mx", 
                    "hl": "en"
                }
            
            search = GoogleSearch(params)
            results = search.get_dict()
            
            if search_type == "images":
                # Extract image URLs from image search results
                image_results = results.get("images_results", [])
                return [res.get("original") for res in image_results if res.get("original")]
            else:
                # Extract web page URLs from web search results
                return [res.get("link") for res in results.get("organic_results", []) if res.get("link")]
        except Exception as e:
            print(f"    SerpApi Err for '{query}': {e}")
            return []

    def _get_domain_authority(self, url, brand):
        """Get domain authority score for a URL based on brand registry"""
        if not brand or not url:
            return 0
            
        parsed_url = urlparse(url.lower())
        domain = parsed_url.netloc.replace('www.', '')
        
        # Check exact brand match in registry
        brand_upper = brand.upper().strip()
        if brand_upper in self.brand_registry:
            brand_info = self.brand_registry[brand_upper]
            for official_domain in brand_info['domains']:
                if domain in official_domain.lower() or official_domain.lower() in domain:
                    return brand_info['authority']
        
        # Check for common official domain patterns
        brand_clean = re.sub(r'[^a-z0-9]', '', brand.lower())
        official_indicators = [
            f'{brand_clean}.com',
            f'{brand_clean}parts.com', 
            f'parts.{brand_clean}.com',
            f'{brand_clean}partsdirect.com'
        ]
        
        for indicator in official_indicators:
            if indicator in domain:
                return 75  # Medium-high authority for pattern matches
                
        return 0

    def _is_official_brand_site(self, url, brand):
        """Check if URL is from an official brand website with high authority"""
        return self._get_domain_authority(url, brand) >= 75

    def _extract_part_numbers_from_text(self, text):
        """Extract potential part numbers from text using regex patterns"""
        if not text:
            return []
            
        found_numbers = []
        text_upper = text.upper()
        
        for pattern in self.part_number_patterns:
            matches = re.findall(pattern, text_upper)
            found_numbers.extend(matches)
            
        # Clean and deduplicate
        cleaned = []
        for num in found_numbers:
            cleaned_num = re.sub(r'[^\w\-]', '', num).strip()
            if len(cleaned_num) >= 3 and cleaned_num not in cleaned:
                cleaned.append(cleaned_num)
                
        return cleaned

    def _validate_part_number_match(self, found_numbers, target_part_number):
        """Validate if any found part numbers match the target part number"""
        if not found_numbers or not target_part_number:
            return False
            
        target_clean = re.sub(r'[^\w\-]', '', target_part_number.upper()).strip()
        
        for found in found_numbers:
            found_clean = re.sub(r'[^\w\-]', '', found.upper()).strip()
            
            # Exact match
            if found_clean == target_clean:
                return True
                
            # Partial match (target contains found or vice versa)
            if len(found_clean) >= 4 and len(target_clean) >= 4:
                if found_clean in target_clean or target_clean in found_clean:
                    return True
                    
        return False

    def find_product_images(self, product_info, max_images_per_product=1):
        part_num = product_info.get(PART_NUMBER_COLUMN_SOURCE, '?')
        brand = product_info.get(BRAND_COLUMN_SOURCE, '').strip()
        name_en = product_info.get(DESCRIPTION_COLUMN_EN_SOURCE, '')
        
        with LogContext(self.logger, part_number=part_num, brand=brand):
            self.logger.info(f"Sourcing images for Part#: {part_num} (Brand: {brand})")
            
            with OperationTimer('image_agent', 'image_search', {'part_number': part_num, 'brand': brand}):
                
                all_found_paths = []
                processed_urls = set()
                
                # PHASE 1: Official Brand Website Search (Highest Priority)
                if brand and len(all_found_paths) < max_images_per_product:
                    self.logger.info(f"PHASE 1: Searching official {brand} websites")
            
            brand_upper = brand.upper().strip()
            official_queries = []
            
            # Use brand registry for targeted official searches
            if brand_upper in self.brand_registry:
                brand_info = self.brand_registry[brand_upper]
                for pattern in brand_info['search_patterns']:
                    official_queries.append(f'{pattern} "{part_num}"')
                    official_queries.append(f'{pattern} {part_num} product')
            else:
                # Fallback patterns for brands not in registry
                brand_clean = brand.lower().replace(' ', '')
                official_queries = [
                    f'site:{brand_clean}.com "{part_num}"',
                    f'site:{brand_clean}parts.com "{part_num}"',
                    f'site:parts.{brand_clean}.com "{part_num}"'
                ]
            
            for query in official_queries:
                if len(all_found_paths) >= max_images_per_product: break
                
                page_urls = self._perform_serpapi_search(query, "web")
                
                # Sort URLs by authority score (highest first)
                url_scores = [(url, self._get_domain_authority(url, brand)) for url in page_urls]
                url_scores.sort(key=lambda x: x[1], reverse=True)
                
                for url, authority in url_scores:
                    if len(all_found_paths) >= max_images_per_product: break
                    if url in processed_urls: continue
                    processed_urls.add(url)
                    
                    if authority >= 75:  # Only process high-authority sites
                        print(f"      Processing official site (authority {authority}): {url}")
                        paths = self._scrape_page_for_images(url, product_info, max_images_per_product - len(all_found_paths))
                        all_found_paths.extend(paths)
                        
                        # If we found images from an official source, prioritize those
                        if paths:
                            print(f"      SUCCESS: Found {len(paths)} image(s) from official source")
        
        # PHASE 2: Official Brand General Search (if Phase 1 insufficient)
        if len(all_found_paths) < max_images_per_product:
            print(f"    PHASE 2: General official brand search...")
            
            general_queries = [
                f'"{brand}" official website "{part_num}" product',
                f'"{brand}" parts catalog "{part_num}"',
                f'"{brand}" {part_num} specifications official'
            ]
            
            for query in general_queries:
                if len(all_found_paths) >= max_images_per_product: break
                
                page_urls = self._perform_serpapi_search(query, "web")
                
                for url in page_urls:
                    if len(all_found_paths) >= max_images_per_product: break
                    if url in processed_urls: continue
                    processed_urls.add(url)
                    
                    authority = self._get_domain_authority(url, brand)
                    if authority >= 75:
                        print(f"      Processing official site (authority {authority}): {url}")
                        paths = self._scrape_page_for_images(url, product_info, max_images_per_product - len(all_found_paths))
                        all_found_paths.extend(paths)
        
        # PHASE 3: Targeted Image Search (Only if no official images found)
        if len(all_found_paths) < max_images_per_product:
            print(f"    PHASE 3: Targeted image search (official sources only)...")
            
            # Only search for images from official domains
            brand_upper = brand.upper().strip()
            if brand_upper in self.brand_registry:
                brand_info = self.brand_registry[brand_upper]
                official_domains = " OR ".join([f"site:{domain}" for domain in brand_info['domains']])
                
                image_queries = [
                    f'({official_domains}) {part_num} product image',
                    f'({official_domains}) "{part_num}" white background'
                ]
                
                for query in image_queries:
                    if len(all_found_paths) >= max_images_per_product: break
                    
                    page_urls = self._perform_serpapi_search(query, "web")
                    
                    for url in page_urls:
                        if len(all_found_paths) >= max_images_per_product: break
                        if url in processed_urls: continue
                        processed_urls.add(url)
                        
                        if self._is_official_brand_site(url, brand):
                            paths = self._scrape_page_for_images(url, product_info, max_images_per_product - len(all_found_paths))
                            all_found_paths.extend(paths)
        
        # Final result reporting
        if not all_found_paths:
            print(f"    ❌ No official images found for Part#: {part_num}")
            print(f"    ⚠️  Recommendation: Manually source image from {brand} official website")
        else:
            print(f"    ✅ Image sourcing complete for {part_num}. Found {len(all_found_paths)} official image(s).")
            
        return all_found_paths