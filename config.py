# File: config.py

import os
from PIL import Image

# --- File Paths & Column Names ---
# Note: These paths are now relative to the project root directory
SOURCE_PRODUCTS_FILE_PATH = './data/Partes (solo partes).xlsx'
EXISTING_STORE_SKUS_CSV_PATH = './data/skus-2025-05-23.csv'
EXISTING_DESCRIPTIONS_CSV_PATH = './data/product_20250604_161952.csv'

# Column names from the source Excel file
PART_NUMBER_COLUMN_SOURCE = 'Part#' 
BRAND_COLUMN_SOURCE = 'Brand'       
APPLICATION_COLUMN_SOURCE = 'Application' 
DESCRIPTION_COLUMN_EN_SOURCE = 'Description'
QTY_COLUMN_SOURCE = 'Qty.'          
PRICE_COLUMN_SOURCE = 'Public'

# Column names from the BigCommerce export files
SKU_COLUMN_STORE_EXPORT = 'Product SKU'
SKU_COLUMN_EXISTING_DESC_EXPORT = 'sku'
HTML_DESCRIPTION_COLUMN_EXISTING_DESC_EXPORT = 'description'


# --- Image Agent Config ---
IMAGE_DOWNLOAD_PATH_CONFIG = "product_images_batch_final"
MIN_ORIGINAL_IMAGE_WIDTH = 300
MIN_ORIGINAL_IMAGE_HEIGHT = 300
BG_COLOR_THRESHOLD = 235
BG_BORDER_PERCENTAGE = 0.05
BG_WHITE_PIXEL_PERCENTAGE = 0.85
RESIZE_FILTER = Image.Resampling.LANCZOS


# --- Text Agent Config ---
GEMINI_MODEL_NAME = 'models/gemini-1.5-flash-latest'


# --- BigCommerce Agent Config ---
# The list is sorted by length (desc) to ensure longer names are matched first
KNOWN_CAR_BRANDS_FOR_CATEGORIES = sorted([
    "ABARTH", "ACURA", "ALFA ROMEO", "ASTON MARTIN", "AUDI", "BENTLEY", "BMW", 
    "BUICK", "CADILLAC", "CHEVROLET", "CHRYSLER", "CITROEN", "DODGE", 
    "FERRARI", "FIAT", "FORD", "GMC", "HONDA", "HUMMER", "HYUNDAI", 
    "INFINITI", "JAGUAR", "JEEP", "KIA", "LAMBORGHINI", "LAND ROVER", 
    "LEXUS", "LINCOLN", "LOTUS", "MASERATI", "MAZDA", "MCLAREN", 
    "MERCEDES BENZ", "MERCURY", "MINI", "MITSUBISHI", "NISSAN", 
    "OLDSMOBILE", "PEUGEOT", "PLYMOUTH", "PONTIAC", "PORSCHE", "RAM", 
    "RENAULT", "ROLLS ROYCE", "SAAB", "SATURN", "SCION", "SEAT", "SMART", 
    "SUBARU", "SUZUKI", "TESLA", "TOYOTA", "VOLKSWAGEN", "VOLVO"
], key=len, reverse=True)

COCHES_CATEGORY_NAME = "COCHES"
UNIVERSAL_CATEGORY_NAME = "UNIVERSAL"
FIXED_WEIGHT_VALUE = 4.0


# --- Main Orchestrator Config ---
MAX_PRODUCTS_TO_PROCESS_IN_BATCH = 1
MAX_CONCURRENT_WORKERS = 5 # Number of products to process in parallel