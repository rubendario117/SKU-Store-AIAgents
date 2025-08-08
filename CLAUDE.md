# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
- **CLI batch processing**: `python main.py`
- **Web UI interface**: `streamlit run ui.py`

### Environment Setup
- Install dependencies: `pip install -r requirements.txt`
- Required environment variables in `.env`:
  - `SERPAPI_API_KEY` - For image search functionality
  - `GEMINI_API_KEY` - For product description generation
  - `BIGCOMMERCE_STORE_HASH` - BigCommerce store identifier
  - `BIGCOMMERCE_ACCESS_TOKEN` - BigCommerce API access token
  - `GOOGLE_APPLICATION_CREDENTIALS` - Path to GCP service account JSON file

## Architecture Overview

This is a **multi-agent e-commerce automation system** for bulk product upload to BigCommerce. The system processes automotive parts data from Excel files and automatically creates store products with images, translated descriptions, and proper categorization.

### Core Components

**Main Pipeline (`main.py`)**
- Orchestrates the entire product processing workflow
- Handles concurrent processing of multiple products using ThreadPoolExecutor
- Manages data loading from Excel/CSV files and logging of results

**Agent System (`agents/`)**
- `ImageSourcingAgent`: Advanced image sourcing with official brand website prioritization, part number validation, and white background filtering
- `VehicleApplicationAgent`: Extracts official vehicle applications from manufacturer websites with brand-specific parsers and data normalization
- `BigCommerceUploaderAgent`: Handles product creation, categorization, and image uploads to BigCommerce store

**Configuration (`config.py`)**
- Centralized settings for file paths, column mappings, image processing parameters
- Car brand categories and processing limits
- All agents reference this single config source

**Web Interface (`ui.py`)**
- Streamlit-based UI for non-technical users to run the automation
- File upload interface for Excel/CSV inputs
- Real-time processing logs and downloadable results

### Data Flow

1. **Input Processing**: Loads source products from Excel (`Partes (solo partes).xlsx`)
2. **Deduplication**: Filters against existing store SKUs to avoid duplicates
3. **Multi-Pipeline Processing** (per product):
   - **Official image sourcing**: 3-phase search prioritizing official brand websites with part number validation
   - Spanish translation of product names using Google Translate
   - **Vehicle applications extraction**: Official compatibility data from manufacturer websites with brand-specific parsers
   - **Enhanced description generation**: Google Gemini AI with official vehicle applications integrated
   - BigCommerce product creation with automatic categorization
   - Image upload and association

### Key Dependencies

- **pandas/openpyxl**: Excel data processing
- **google-cloud-translate**: Product name translation
- **google-generativeai**: AI-generated product descriptions
- **serpapi**: Image search and sourcing
- **Pillow**: Image processing and background detection
- **requests**: BigCommerce API integration
- **streamlit**: Web interface framework

### Data Directory Structure

- `data/`: Contains source Excel files and exported CSV files
- `product_images_batch_final/`: Downloaded and processed product images
- `secure_keys/`: API credentials and service account files
- Batch processing logs are saved as timestamped JSON/Excel files

### Processing Configuration

- Batch size controlled by `MAX_PRODUCTS_TO_PROCESS_IN_BATCH` (default: 1)
- Concurrent workers via `MAX_CONCURRENT_WORKERS` (default: 5)
- **Enhanced Image Sourcing**:
  - 3-phase official website prioritization system
  - Comprehensive brand registry with 95+ authority scoring for OEM sites (includes ford.oempartsonline.com for Ford parts)
  - Part number validation and matching on source pages
  - White background filtering and quality controls
  - Strict official-source-only policy to prevent incorrect product images
- **Vehicle Applications System**:
  - Brand-specific website parsers (Hawk Performance, Bilstein, Generic Table Parser)
  - Official compatibility data extraction from manufacturer websites
  - Data normalization with standardized vehicle format (Make, Model, Year, Trim, Engine)
  - Application merging system prioritizing official over Excel data
  - Caching system to minimize repeated website requests
- Automatic categorization based on car brand detection in product applications