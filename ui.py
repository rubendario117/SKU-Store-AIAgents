# File: ui.py

import streamlit as st
import pandas as pd
import os
import time
from io import StringIO
import sys

# Import the functions and classes from your existing project
from main import process_single_product, load_source_products
from agents.image_agent import ImageSourcingAgent
from agents.bigcommerce_agent import BigCommerceUploaderAgent
from agents.vehicle_application_agent import VehicleApplicationAgent
from config import MAX_CONCURRENT_WORKERS
from dotenv import load_dotenv

# Imports for text generation
from google.cloud import translate_v2 as translate
import google.generativeai as genai

# Helper class to redirect print statements to the UI
class StreamlitLog(StringIO):
    def __init__(self, container):
        super(StreamlitLog, self).__init__()
        self.container = container

    def write(self, s):
        super(StreamlitLog, self).write(s)
        # Use st.code for a terminal-like feel
        self.container.code(self.getvalue())

    def flush(self):
        pass # No-op for Streamlit

# --- Page Configuration ---
st.set_page_config(page_title="DPerformance Product Uploader", layout="wide")

# --- Header with Logo and Title ---
logo_path = "data/logo_transparente_dp_right_transparente_letras_blancas_high_resolution_1685600678__78108.webp"

# Create columns for a professional layout
col1, col2 = st.columns([1, 4])

with col1:
    # Check if the logo file exists before trying to display it
    if os.path.exists(logo_path):
        st.image(logo_path, width=150)
    else:
        st.warning("Logo file not found in /data folder.")

with col2:
    st.title("DPerformance AI Agent: Product Uploader")
    st.write("This interface runs the automated batch product upload to BigCommerce.")

# Add a divider for a clean look
st.markdown("---")


# --- Main Application Logic ---
if 'processing' not in st.session_state:
    st.session_state.processing = False

# --- Sidebar for Configuration ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Use session state to keep file data
    if 'source_file' not in st.session_state:
        st.session_state.source_file = None
    if 'skus_file' not in st.session_state:
        st.session_state.skus_file = None
    if 'descs_file' not in st.session_state:
        st.session_state.descs_file = None

    source_file_uploader = st.file_uploader("1. Upload Source Products Excel (`Partes...xlsx`)", type=['xlsx'])
    skus_file_uploader = st.file_uploader("2. Upload Existing SKUs CSV (`skus-...csv`)", type=['csv'])
    descs_file_uploader = st.file_uploader("3. (Optional) Upload Existing Descriptions CSV", type=['csv'])

    if source_file_uploader:
        st.session_state.source_file = source_file_uploader
    if skus_file_uploader:
        st.session_state.skus_file = skus_file_uploader
    if descs_file_uploader:
        st.session_state.descs_file = descs_file_uploader

    batch_size = st.number_input("Batch Size to Process", min_value=1, max_value=100, value=5)

# --- Main Content Area ---
main_col1, main_col2 = st.columns([2, 1])

with main_col1:
    st.header("▶️ Run Agent")
    run_button = st.button("Start Batch Upload Process", disabled=st.session_state.processing)
    
    # Placeholder for the log output
    log_container = st.empty()
    log_container.code("Logs will appear here once the process starts...", language=None)

with main_col2:
    st.header("📋 Status")
    if st.session_state.source_file:
        st.success(f"Source file loaded: **{st.session_state.source_file.name}**")
    else:
        st.warning("Please upload the source products Excel file.")

    if st.session_state.skus_file:
        st.success(f"SKUs file loaded: **{st.session_state.skus_file.name}**")
    else:
        st.warning("Please upload the existing SKUs CSV file.")

    if st.session_state.descs_file:
        st.info(f"Descriptions file loaded: **{st.session_state.descs_file.name}**")
    else:
        st.info("Optional descriptions file not loaded.")


# --- Execution Logic ---
if run_button:
    if not st.session_state.source_file or not st.session_state.skus_file:
        st.error("Error: Please upload both the Source Products and Existing SKUs files before running.")
    else:
        st.session_state.processing = True
        # ===================================================================
        # --- START: THIS IS THE CORRECTED LINE ---
        # ===================================================================
        st.rerun() # Rerun to disable the button
        # ===================================================================
        # --- END: THIS IS THE CORRECTED LINE ---
        # ===================================================================


if st.session_state.processing:
    with st.spinner('Agents are running... Please wait.'):
        # Redirect stdout to our custom logger
        original_stdout = sys.stdout
        sys.stdout = StreamlitLog(log_container)

        try:
            # --- Initialize Agents (similar to main.py) ---
            load_dotenv()
            SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
            GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
            STORE_HASH = os.getenv("BIGCOMMERCE_STORE_HASH")
            ACCESS_TOKEN = os.getenv("BIGCOMMERCE_ACCESS_TOKEN")
            GCP_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            
            if not GCP_CREDENTIALS_PATH or not os.path.exists(GCP_CREDENTIALS_PATH):
                raise FileNotFoundError(f"GCP credentials not found at {GCP_CREDENTIALS_PATH}")

            translate_client = translate.Client.from_service_account_json(GCP_CREDENTIALS_PATH)
            genai.configure(api_key=GEMINI_API_KEY)
            gemini_model = genai.GenerativeModel('models/gemini-1.5-flash-latest')

            agents = {
                'image': ImageSourcingAgent(SERPAPI_API_KEY),
                'bigcommerce': BigCommerceUploaderAgent(STORE_HASH, ACCESS_TOKEN),
                'vehicle_app': VehicleApplicationAgent(),
                'translate': translate_client, 'gemini': gemini_model,
                'existing_skus': set(), 'existing_descs': {}
            }
            print("✅ All API clients and agents initialized.")

            # --- Load data from uploaded files ---
            all_source_products = pd.read_excel(st.session_state.source_file).to_dict('records')
            df_skus = pd.read_csv(st.session_state.skus_file)
            agents['existing_skus'] = set(df_skus.iloc[:, 0].dropna().astype(str))
            
            if st.session_state.descs_file:
                df_descs = pd.read_csv(st.session_state.descs_file)
                agents['existing_descs'] = pd.Series(df_descs.iloc[:, 1].values, index=df_descs.iloc[:, 0].astype(str)).to_dict()

            new_products = [p for p in all_source_products if p.get('Part#') and p.get('Part#') not in agents['existing_skus']]
            batch_to_process = new_products[:batch_size]
            print(f"Found {len(new_products)} new products. Processing batch of {len(batch_to_process)}.")

            # --- Sequential Execution for UI Logging ---
            final_log = []
            for i, product in enumerate(batch_to_process):
                print(f"\n--- Processing Item {i+1}/{len(batch_to_process)} ---")
                # Add necessary keys for the processing function
                product['original_excel_row'] = all_source_products.index(product) + 2
                product['sanitized_part_number'] = product.get('Part#')
                final_log.append(process_single_product(product, agents))

            print("\n--- ✅ BATCH PROCESSING COMPLETE ---")
            st.success("Batch process completed successfully!")
            
            # Save log files
            log_filename = f"batch_upload_log_{time.strftime('%Y%m%d_%H%M%S')}"
            log_df = pd.DataFrame(final_log)
            # Create an in-memory file for download
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                log_df.to_excel(writer, index=False, sheet_name='Log')
            excel_data = output.getvalue()

            st.download_button(
                 label="⬇️ Download Log File (Excel)",
                 data=excel_data,
                 file_name=f'{log_filename}.xlsx',
                 mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
             )

        except Exception as e:
            print(f"\n--- ❌ CRITICAL ERROR ---")
            print(str(e))
            st.error(f"A critical error occurred: {e}")
        
        finally:
            # Restore stdout
            sys.stdout = original_stdout
            st.session_state.processing = False
            st.rerun() # Rerun one last time to re-enable the button