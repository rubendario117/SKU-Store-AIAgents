# File: main.py

import os
import pandas as pd
import json
import time
import re
import concurrent.futures
from dotenv import load_dotenv

# Import our classes and config variables from other files
import config
from agents.image_agent import ImageSourcingAgent
from agents.bigcommerce_agent import BigCommerceUploaderAgent
from agents.vehicle_application_agent import VehicleApplicationAgent

# Import monitoring and logging
from monitoring import (
    performance_monitor, OperationTimer, 
    get_main_logger, LogContext
)

# Imports for text generation
from google.cloud import translate_v2 as translate
import google.generativeai as genai


def load_source_products(file_path):
    """Loads product data from the source Excel file."""
    try:
        df = pd.read_excel(file_path, dtype=str).fillna('')
        required_cols = [
            config.PART_NUMBER_COLUMN_SOURCE, config.BRAND_COLUMN_SOURCE, 
            config.APPLICATION_COLUMN_SOURCE, config.DESCRIPTION_COLUMN_EN_SOURCE,
            config.QTY_COLUMN_SOURCE, config.PRICE_COLUMN_SOURCE
        ]
        if not all(col in df.columns for col in required_cols):
            raise ValueError("A required column is missing in the source Excel file.")
        
        df['sanitized_part_number'] = df[config.PART_NUMBER_COLUMN_SOURCE]
        df['original_excel_row'] = df.index + 2
        return df.to_dict('records')
    except Exception as e:
        print(f"ERROR loading source Excel file: {e}")
        return []

def translate_text(text, client):
    """Translates text to Spanish using Google Translate."""
    if not client or not text or not isinstance(text, str): return ""
    try:
        result = client.translate(text, target_language='es', source_language='en')
        return result['translatedText']
    except Exception as e:
        print(f"  Name Translate Error for '{str(text)[:30]}...': {e}")
        return f"SPANISH_NAME_ERROR: {text}"

def generate_description(product_data, gemini_model, official_applications=None):
    """Generates a product description using Google Gemini with enhanced vehicle applications."""
    if not gemini_model: return "LLM model not available for description."
    
    name_es = product_data.get('Name_ES_for_BC', "este producto")
    brand = product_data.get(config.BRAND_COLUMN_SOURCE, "")
    sku = product_data.get(config.PART_NUMBER_COLUMN_SOURCE, "")
    app_context = product_data.get(config.APPLICATION_COLUMN_SOURCE, "")
    orig_en_desc = product_data.get(config.DESCRIPTION_COLUMN_EN_SOURCE, "")
    
    # Enhanced application context with official data
    enhanced_app_context = app_context
    if official_applications:
        official_apps_text = "; ".join([app.to_display_string() for app in official_applications[:10]])  # Limit to 10
        if official_apps_text:
            enhanced_app_context = f"Aplicaciones Oficiales: {official_apps_text}"
            if app_context:
                enhanced_app_context += f" | Aplicaciones Adicionales: {app_context}"

    prompt = f"""Eres un redactor experto de marketing para una tienda de refacciones de autos de alto rendimiento en México.
Tu tarea es generar un párrafo descriptivo principal, atractivo y detallado, en español, para el siguiente artículo.
NO listes explícitamente las 'Aplicaciones' o vehículos compatibles; enfócate en describir el producto, sus características, beneficios y la calidad de la marca.
El tono debe ser profesional y entusiasta. Usa de 2 a 4 frases. No incluyas el precio.

Información del Producto Base:
- Nombre del Producto (en español): {name_es}
- Marca: {brand}
- SKU (Número de Parte): {sku}
- Contexto de Aplicación General: {enhanced_app_context}
- Características/Nombre en Inglés (para referencia): {orig_en_desc}

Genera únicamente el párrafo descriptivo principal en español:
"""
    try:
        response = gemini_model.generate_content(prompt)
        gen_text = response.text.strip().replace('"', '')
        return re.sub(r'^\s*Descripción del Producto:\s*', '', gen_text, flags=re.IGNORECASE).strip()
    except Exception as e:
        return f"Error LLM desc: {str(e)}"

def merge_applications(official_apps, excel_apps):
    """Merge official and Excel applications, prioritizing official data"""
    if not official_apps and not excel_apps:
        return []
    
    # Convert Excel apps to display format
    excel_display = []
    if excel_apps:
        for app in excel_apps:
            app_clean = app.strip()
            if app_clean and len(app_clean) > 2:
                excel_display.append(app_clean)
    
    # Convert official apps to display format
    official_display = []
    if official_apps:
        official_display = [app.to_display_string() for app in official_apps]
    
    # Combine, prioritizing official data
    all_apps = official_display + excel_display
    
    # Remove duplicates while preserving order
    seen = set()
    unique_apps = []
    for app in all_apps:
        app_lower = app.lower()
        if app_lower not in seen:
            seen.add(app_lower)
            unique_apps.append(app)
    
    return unique_apps

def process_single_product(product_data, agents):
    """Encapsulates the entire pipeline for a single product."""
    sku = product_data.get(config.PART_NUMBER_COLUMN_SOURCE, "UNKNOWN_SKU")
    logger = get_main_logger()
    
    with LogContext(logger, sku=sku, row=product_data.get('original_excel_row', 'N/A')):
        logger.info(f"Starting to process SKU: {sku}")
        
        log_entry = {
            "source_sku": sku, 
            "source_row": product_data.get('original_excel_row', 'N/A'),
            "status": "Started", "bc_product_id": None, "images_sourced_paths": [],
            "images_uploaded_count": 0, "product_name_es": "", "description_source": "", 
            "notes": []
        }
    
        try:
            # Pipeline 1: Image Sourcing
            with OperationTimer('main', 'image_sourcing', {'sku': sku}):
                logger.info("Starting image sourcing pipeline")
                img_paths = agents['image'].find_product_images(product_data, max_images_per_product=1)
                product_data['processed_image_paths'] = img_paths
                log_entry['images_sourced_paths'] = img_paths
                if not img_paths: 
                    log_entry['notes'].append("No images sourced.")
                    logger.warning("No images sourced for product")
                else:
                    logger.success(f"Sourced {len(img_paths)} images")

            # Pipeline 2: Spanish Product Name
            with OperationTimer('main', 'translation', {'sku': sku}):
                logger.info("Starting product name translation")
                name_es = translate_text(product_data.get(config.DESCRIPTION_COLUMN_EN_SOURCE, ""), agents['translate'])
                product_data['Name_ES_for_BC'] = name_es
                log_entry['product_name_es'] = name_es
                if name_es and not name_es.startswith('SPANISH_NAME_ERROR'):
                    logger.success("Product name translated successfully")
                else:
                    logger.warning("Product name translation failed or had issues")

            # Pipeline 3: Vehicle Applications Extraction (NEW)
            official_applications = []
            if 'vehicle_app' in agents:
                with OperationTimer('main', 'vehicle_applications', {'sku': sku}):
                    try:
                        logger.info("Starting vehicle applications extraction")
                        official_applications = agents['vehicle_app'].find_and_extract_applications(
                            product_data, agents.get('image')
                        )
                        log_entry['official_applications_found'] = len(official_applications)
                        if official_applications:
                            logger.success(f"Found {len(official_applications)} official vehicle applications")
                        else:
                            logger.info("No official vehicle applications found")
                    except Exception as e:
                        logger.error(f"Vehicle application extraction failed: {e}")
                        log_entry['official_applications_found'] = 0

            # Pipeline 4: Enhanced Spanish Product Description
            with OperationTimer('main', 'description_generation', {'sku': sku}):
                logger.info("Starting product description generation")
                if sku in agents['existing_descs'] and agents['existing_descs'][sku].strip():
                    full_desc_es = agents['existing_descs'][sku]
                    log_entry['description_source'] = "ClientExport"
                    logger.info("Using existing description from client export")
                else:
                    gemini_paragraph = generate_description(product_data, agents['gemini'], official_applications)
                    
                    # Merge official and Excel applications
                    excel_apps = []
                    app_string = product_data.get(config.APPLICATION_COLUMN_SOURCE, "").strip()
                    if app_string:
                        excel_apps = [a.strip() for a in app_string.replace(';', '\n').splitlines() if a.strip()]
                    
                    merged_apps = merge_applications(official_applications, excel_apps)
                    
                    # Generate HTML for applications
                    app_html = ""
                    if merged_apps:
                        app_html = "<p><strong>Aplicaciones:</strong></p><ul>" + "".join(f"<li>{item}</li>" for item in merged_apps) + "</ul>"
                    
                    full_desc_es = f"<p>{gemini_paragraph}</p>{app_html}"
                    
                    if official_applications:
                        log_entry['description_source'] = "GeminiGenerated_Plus_OfficialApps_Plus_ExcelApps"
                    else:
                        log_entry['description_source'] = "GeminiGenerated_Plus_ExcelApps"
                    
                    logger.success(f"Generated description with {len(merged_apps)} applications")
                    
            product_data['Final_Full_Description_ES_for_BC'] = full_desc_es

            # Pipeline 5: BigCommerce Upload
            with OperationTimer('main', 'bigcommerce_upload', {'sku': sku}):
                logger.info("Starting BigCommerce product creation")
                created_prod = agents['bigcommerce'].create_product(product_data, agents['existing_skus'])
                if created_prod and created_prod.get('id'):
                    bc_id = created_prod['id']
                    log_entry['bc_product_id'] = bc_id
                    log_entry['status'] = "Product Created"
                    logger.success(f"Product created with ID: {bc_id}")
                    
                    if img_paths:
                        logger.info(f"Starting image upload for {len(img_paths)} images")
                        uploaded_count = 0
                        for i, path in enumerate(img_paths):
                            if agents['bigcommerce'].upload_product_image(bc_id, path, is_thumbnail=(i==0), image_alt_text=name_es):
                                uploaded_count += 1
                        log_entry['images_uploaded_count'] = uploaded_count
                        if uploaded_count > 0: 
                            log_entry['status'] += " + Images Uploaded"
                            logger.success(f"Uploaded {uploaded_count} images")
                        else:
                            logger.warning("No images were uploaded successfully")
                else:
                    log_entry['status'] = "Failed - Product Creation"
                    logger.error("Failed to create product in BigCommerce")

        except Exception as e:
            log_entry['status'] = "Failed - Pipeline Error"
            log_entry['notes'].append(f"Pipeline exception: {str(e)}")
            logger.error(f"Pipeline failed with exception: {e}", error_type=type(e).__name__)
        
        logger.info(f"Finished processing SKU: {sku} with Status: {log_entry['status']}")
        return log_entry


def main():
    """Main function to orchestrate the batch processing."""
    logger = get_main_logger()
    logger.info("Initializing Batch Upload to BigCommerce")
    
    load_dotenv()

    # --- Load Credentials ---
    SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    STORE_HASH = os.getenv("BIGCOMMERCE_STORE_HASH")
    ACCESS_TOKEN = os.getenv("BIGCOMMERCE_ACCESS_TOKEN")
    GCP_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") # Get path from .env

    # --- Initialize API Clients and Agents ---
    try:
        # --- THIS BLOCK IS THE FIX ---
        # 1. Check if the GCP credentials path exists
        if not GCP_CREDENTIALS_PATH or not os.path.exists(GCP_CREDENTIALS_PATH):
            raise FileNotFoundError(
                f"Google Cloud credentials file not found at path: '{GCP_CREDENTIALS_PATH}'. "
                "Please check the GOOGLE_APPLICATION_CREDENTIALS variable in your .env file."
            )
        
        # 2. Explicitly initialize the Translate client with the JSON file
        translate_client = translate.Client.from_service_account_json(GCP_CREDENTIALS_PATH)
        # --- END OF FIX ---
        
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
        
        agents = {
            'image': ImageSourcingAgent(SERPAPI_API_KEY),
            'bigcommerce': BigCommerceUploaderAgent(STORE_HASH, ACCESS_TOKEN),
            'vehicle_app': VehicleApplicationAgent(),
            'translate': translate_client,
            'gemini': gemini_model,
            'existing_skus': set(),
            'existing_descs': {}
        }
        logger.success("All API clients and agents initialized")
    except Exception as e:
        logger.critical(f"CRITICAL ERROR during initialization: {e}")
        return

    # --- Load Data for Processing ---
    try:
        df_skus = pd.read_csv(config.EXISTING_STORE_SKUS_CSV_PATH)
        agents['existing_skus'] = set(df_skus[config.SKU_COLUMN_STORE_EXPORT].dropna().astype(str))
        logger.info(f"Loaded {len(agents['existing_skus'])} existing SKUs")

        df_descs = pd.read_csv(config.EXISTING_DESCRIPTIONS_CSV_PATH)
        agents['existing_descs'] = pd.Series(
            df_descs[config.HTML_DESCRIPTION_COLUMN_EXISTING_DESC_EXPORT].values,
            index=df_descs[config.SKU_COLUMN_EXISTING_DESC_EXPORT].astype(str)
        ).to_dict()
        logger.info(f"Loaded {len(agents['existing_descs'])} existing descriptions")
    except Exception as e:
        logger.warning(f"Could not load data files: {e}")

    all_source_products = load_source_products(config.SOURCE_PRODUCTS_FILE_PATH)
    if not all_source_products: return

    new_products = [
        p for p in all_source_products 
        if p.get(config.PART_NUMBER_COLUMN_SOURCE) and 
           p.get(config.PART_NUMBER_COLUMN_SOURCE) not in agents['existing_skus']
    ]
    logger.info(f"Found {len(new_products)} NEW products to process")

    batch_to_process = new_products[:config.MAX_PRODUCTS_TO_PROCESS_IN_BATCH]
    if not batch_to_process:
        logger.info("No new products to process in this batch")
        return

    # --- Run Concurrent Processing ---
    logger.business(f"Starting CONCURRENT Batch Processing for {len(batch_to_process)} products")
    batch_log = []
    
    with OperationTimer('main', 'batch_processing', {'batch_size': len(batch_to_process)}):
        with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_WORKERS) as executor:
            future_to_product = {executor.submit(process_single_product, p, agents): p for p in batch_to_process}
            for future in concurrent.futures.as_completed(future_to_product):
                batch_log.append(future.result())

    # --- Save Logs ---
    logger.business("BATCH PROCESSING COMPLETE")
    
    # Calculate success metrics
    successful_products = sum(1 for entry in batch_log if 'Failed' not in entry.get('status', ''))
    success_rate = (successful_products / len(batch_log)) * 100 if batch_log else 0
    
    logger.performance(f"Batch completed with {successful_products}/{len(batch_log)} successful products ({success_rate:.1f}% success rate)")
    
    log_filename = f"batch_upload_log_{time.strftime('%Y%m%d_%H%M%S')}"
    
    with open(f"{log_filename}.json", 'w', encoding='utf-8') as f:
        json.dump(batch_log, f, ensure_ascii=False, indent=4)
    logger.info(f"Full batch log saved to {log_filename}.json")

    try:
        pd.DataFrame(batch_log).to_excel(f"{log_filename}.xlsx", index=False, engine='openpyxl')
        logger.info(f"Batch log also saved to {log_filename}.xlsx")
    except Exception as e:
        logger.error(f"Error saving log to Excel: {e}")

if __name__ == "__main__":
    main()