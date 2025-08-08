# File: agents/bigcommerce_agent.py

import os
import json
import requests
import time
import re

# Import settings from the central config file
from config import (
    KNOWN_CAR_BRANDS_FOR_CATEGORIES, COCHES_CATEGORY_NAME, UNIVERSAL_CATEGORY_NAME,
    PART_NUMBER_COLUMN_SOURCE, BRAND_COLUMN_SOURCE, APPLICATION_COLUMN_SOURCE,
    PRICE_COLUMN_SOURCE, QTY_COLUMN_SOURCE, FIXED_WEIGHT_VALUE
)

# Import monitoring system
from monitoring import OperationTimer, get_bigcommerce_logger, LogContext

class BigCommerceUploaderAgent:
    def __init__(self, store_hash, access_token, client_id=None):
        self.store_hash = store_hash; self.access_token = access_token; self.client_id = client_id
        self.base_v3_url = f"https://api.bigcommerce.com/stores/{self.store_hash}/v3"
        self.standard_headers = {"X-Auth-Token":self.access_token,"Accept":"application/json","Content-Type":"application/json"}
        
        # Initialize monitoring
        self.logger = get_bigcommerce_logger()
        
        self.cache_file_path = "bc_api_cache.json"
        self.cache_max_age_seconds = 24 * 60 * 60 # 24 hours
        
        self.product_brand_name_to_id_map={}; self.newly_created_product_brands_log=[]
        self.all_store_categories_map_id_to_obj={}; self.all_store_categories_map_name_to_id={}
        self.car_brand_categories_map={}; self.newly_created_app_categories_log=[]
        self.coches_category_id=None; self.universal_category_id=None

        brands_pattern = '|'.join(re.escape(b) for b in KNOWN_CAR_BRANDS_FOR_CATEGORIES)
        self.car_brand_regex = re.compile(brands_pattern, re.IGNORECASE)

        if self._load_from_cache():
            print("BC Agent Initialized from local CACHE.")
        else:
            print("BC Agent Initializing from API: Fetching Brands & Categories...")
            self._initialize_product_brands()
            self._initialize_store_categories_and_maps()
            self._save_to_cache()
            print("BC Agent Initialization Complete. Data saved to local cache.")

    def _load_from_cache(self):
        try:
            if not os.path.exists(self.cache_file_path):
                print("  Cache file not found.")
                return False
            
            cache_age = time.time() - os.path.getmtime(self.cache_file_path)
            if cache_age > self.cache_max_age_seconds:
                print(f"  Cache file is too old ({int(cache_age/3600)} hours). Ignoring.")
                return False
            
            print(f"  Found recent cache file. Loading data...")
            with open(self.cache_file_path, 'r') as f:
                cached_data = json.load(f)
            
            self.product_brand_name_to_id_map = cached_data.get("product_brand_name_to_id_map", {})
            self.all_store_categories_map_id_to_obj = {int(k): v for k, v in cached_data.get("all_store_categories_map_id_to_obj", {}).items()}
            self.all_store_categories_map_name_to_id = cached_data.get("all_store_categories_map_name_to_id", {})
            self.car_brand_categories_map = cached_data.get("car_brand_categories_map", {})
            self.coches_category_id = cached_data.get("coches_category_id")
            self.universal_category_id = cached_data.get("universal_category_id")
            return True
        except Exception as e:
            print(f"  Error loading from cache: {e}. Will fetch from API.")
            return False

    def _save_to_cache(self):
        cache_data = {
            "product_brand_name_to_id_map": self.product_brand_name_to_id_map,
            "all_store_categories_map_id_to_obj": self.all_store_categories_map_id_to_obj,
            "all_store_categories_map_name_to_id": self.all_store_categories_map_name_to_id,
            "car_brand_categories_map": self.car_brand_categories_map,
            "coches_category_id": self.coches_category_id,
            "universal_category_id": self.universal_category_id
        }
        try:
            with open(self.cache_file_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
            print(f"  Agent data saved to cache file: {self.cache_file_path}")
        except Exception as e:
            print(f"  Error saving to cache: {e}")

    def _make_api_request(self, method, endpoint, payload=None, params=None, files=None):
        url=f"{self.base_v3_url}{endpoint}"; response_json={}; response_obj=None
        current_headers=self.standard_headers.copy()
        if files: current_headers.pop("Content-Type",None)
        try:
            if files: response_obj=requests.request(method,url,headers=current_headers,files=files,data=payload,params=params,timeout=60)
            else: response_obj=requests.request(method,url,headers=current_headers,json=payload,params=params,timeout=30)
            try: response_json=response_obj.json()
            except json.JSONDecodeError: response_json={"raw_text":response_obj.text,"_error_message":"Response not valid JSON."}
            response_obj.raise_for_status()
        except requests.exceptions.HTTPError as http_err:
            status_code=http_err.response.status_code if http_err.response else 'N/A'
            response_json={"error_type":"HTTPError","status_code":status_code,"title":response_json.get('title',f"HTTP Error {status_code}"),
                           "detail":response_json.get('detail',str(http_err)),"errors":response_json.get('errors',[]),
                           "response_text_snippet":http_err.response.text[:500] if http_err.response else 'N/A'}
        except requests.exceptions.RequestException as req_err: print(f"    ReqEx for {method} {url[:70]}: {req_err}"); response_json={"error_type":"RequestException","detail":str(req_err),"status_code":None}
        except Exception as e: print(f"    UnexpAPIerr {method} {url[:70]}: {e}"); response_json={"error_type":"UnexpectedException","detail":str(e),"status_code":None}
        return response_obj,response_json

    def _initialize_product_brands(self):
        print("  BC_Agent: Fetching product brands from API..."); current_url="/catalog/brands?limit=250"
        while current_url:
            resp_obj,data=self._make_api_request("GET",current_url)
            if resp_obj and resp_obj.status_code==200 and data and 'data' in data:
                for b in data['data']:
                    if b.get('name') and b.get('id'): self.product_brand_name_to_id_map[b['name'].strip().lower()]=b['id']
                next_l=data.get('meta',{}).get('pagination',{}).get('links',{}).get('next')
                current_url=next_l.replace(self.base_v3_url,"") if next_l else None
                if current_url: time.sleep(0.1)
            else: current_url=None
        print(f"  BC_Agent: Initialized {len(self.product_brand_name_to_id_map)} product brands.")

    def get_or_create_product_brand_id(self, brand_name_excel):
        if not brand_name_excel or not isinstance(brand_name_excel,str) or not brand_name_excel.strip(): return None
        bn_lower=brand_name_excel.strip().lower()
        if bn_lower in self.product_brand_name_to_id_map: return self.product_brand_name_to_id_map[bn_lower]
        
        print(f"    Product Brand '{brand_name_excel}' not found. Creating...")
        payload={"name":brand_name_excel.strip()}
        resp_obj,data=self._make_api_request("POST","/catalog/brands",payload=payload)
        
        if resp_obj and resp_obj.status_code in [200,201] and data.get('data',{}).get('id'):
            nb=data['data']; print(f"      SUCCESS: Created brand '{nb['name']}' (ID: {nb['id']})")
            self.product_brand_name_to_id_map[nb['name'].strip().lower()]=nb['id']
            self.newly_created_product_brands_log.append(nb)
            self._save_to_cache() # Re-save cache after change
            return nb['id']
        return None

    def _initialize_store_categories_and_maps(self):
        print("  BC_Agent: Fetching store categories from API..."); current_url="/catalog/categories?limit=250"
        temp_list=[]
        while current_url:
            resp_obj,data=self._make_api_request("GET",current_url)
            if resp_obj and resp_obj.status_code==200 and data and 'data' in data:
                temp_list.extend(data['data'])
                next_l=data.get('meta',{}).get('pagination',{}).get('links',{}).get('next')
                current_url=next_l.replace(self.base_v3_url,"") if next_l else None
                if current_url: time.sleep(0.1)
            else: current_url=None
        
        for cat in temp_list:
            self.all_store_categories_map_id_to_obj[cat['id']]=cat
            self.all_store_categories_map_name_to_id[cat['name'].strip().lower()]=cat['id']
            if cat['name'].strip().upper()==COCHES_CATEGORY_NAME.upper(): self.coches_category_id=cat['id']
            if cat['name'].strip().upper()==UNIVERSAL_CATEGORY_NAME.upper(): self.universal_category_id=cat['id']
        
        print(f"  BC_Agent: Initialized {len(self.all_store_categories_map_id_to_obj)} total categories.")
        
        if not self.coches_category_id: self._create_main_category_if_not_exists(COCHES_CATEGORY_NAME,"coches_category_id")
        else: print(f"    '{COCHES_CATEGORY_NAME}' found (ID: {self.coches_category_id})")
        if not self.universal_category_id: self._create_main_category_if_not_exists(UNIVERSAL_CATEGORY_NAME,"universal_category_id")
        else: print(f"    '{UNIVERSAL_CATEGORY_NAME}' found (ID: {self.universal_category_id})")
        
        if self.coches_category_id:
            for cid,cobj in self.all_store_categories_map_id_to_obj.items():
                if cobj.get('parent_id')==self.coches_category_id: self.car_brand_categories_map[cobj['name'].strip().lower()]=cid
            print(f"  BC_Agent: Found {len(self.car_brand_categories_map)} car brand subcats under '{COCHES_CATEGORY_NAME}'.")

    def _create_main_category_if_not_exists(self,cat_name,id_attr_name):
        print(f"    '{cat_name}' not found. Creating...")
        payload={"parent_id":0,"name":cat_name,"is_visible":True}
        resp_obj,data=self._make_api_request("POST","/catalog/categories",payload=payload)
        
        if resp_obj and resp_obj.status_code in [200,201] and data.get('data',{}).get('id'):
            nc=data['data']; setattr(self,id_attr_name,nc['id'])
            self.all_store_categories_map_id_to_obj[nc['id']]=nc
            self.all_store_categories_map_name_to_id[nc['name'].strip().lower()]=nc['id']
            self.newly_created_app_categories_log.append(nc)
            print(f"      SUCCESS: Created '{cat_name}' (ID: {getattr(self,id_attr_name)})")
            self._save_to_cache() # Re-save cache after change
        else: print(f"      FAILURE creating '{cat_name}'.")

    def get_category_ids_for_application(self, app_string):
        if not app_string or not isinstance(app_string, str) or not app_string.strip(): return []
        app_lower = app_string.strip().lower()
        final_cat_ids = set()
        if app_lower == "universal":
            if self.universal_category_id: final_cat_ids.add(self.universal_category_id)
            return list(final_cat_ids)
        
        found_brands = self.car_brand_regex.findall(app_string)
        if found_brands:
            for brand in set(found_brands):
                brand_lower = brand.strip().lower()
                if brand_lower in self.car_brand_categories_map: 
                    final_cat_ids.add(self.car_brand_categories_map[brand_lower])
                elif self.coches_category_id:
                    print(f"      Car brand cat '{brand}' not found under '{COCHES_CATEGORY_NAME}'. Creating...")
                    payload = {"parent_id": self.coches_category_id, "name": brand.strip(), "is_visible": True}
                    resp_obj, data = self._make_api_request("POST", "/catalog/categories", payload=payload)
                    if resp_obj and resp_obj.status_code in [200, 201] and data.get('data', {}).get('id'):
                        new_cat = data['data']
                        print(f"        SUCCESS: Created car brand cat '{new_cat['name']}' (ID: {new_cat['id']}).")
                        self.car_brand_categories_map[new_cat['name'].strip().lower()] = new_cat['id']
                        self.all_store_categories_map_id_to_obj[new_cat['id']] = new_cat
                        self.all_store_categories_map_name_to_id[new_cat['name'].strip().lower()] = new_cat['id']
                        self.newly_created_app_categories_log.append(new_cat)
                        final_cat_ids.add(new_cat['id'])
                        self._save_to_cache() # Re-save cache after change
        
        if final_cat_ids: return list(final_cat_ids)
        if self.universal_category_id: final_cat_ids.add(self.universal_category_id); return list(final_cat_ids)
        return []

    def create_product(self,product_data_dict,existing_skus_set):
        sku=product_data_dict.get(PART_NUMBER_COLUMN_SOURCE,"").strip()
        if not sku: 
            print(f"  Skip: No SKU (Row {product_data_dict.get('original_excel_row')}).")
            return None
        if sku in existing_skus_set: 
            print(f"  Skip: SKU '{sku}' exists in store export.")
            return None
        
        print(f"\nBC_Agent: Processing NEW SKU for creation: {sku}")
        product_name_for_bc = product_data_dict.get('Name_ES_for_BC', f"Product {sku}")
        if not product_name_for_bc.strip(): product_name_for_bc = f"Product {sku}"
        
        full_description_for_bc = product_data_dict.get('Final_Full_Description_ES_for_BC', "")
        pb_name=product_data_dict.get(BRAND_COLUMN_SOURCE,"").strip()
        bc_brand_id=self.get_or_create_product_brand_id(pb_name) if pb_name else None
        app_str=product_data_dict.get(APPLICATION_COLUMN_SOURCE,"").strip()
        bc_cat_ids=self.get_category_ids_for_application(app_str)
        
        if not bc_cat_ids: print(f"  WARN: No categories will be assigned to SKU {sku} from app '{app_str}'.")
        
        try:
            p_str=str(product_data_dict.get(PRICE_COLUMN_SOURCE,'0')).replace(',','')
            inv_str=str(product_data_dict.get(QTY_COLUMN_SOURCE,'0')).replace(',','')
            price=float(p_str) if p_str else 0.0
            inventory=int(inv_str) if inv_str else 0
        except ValueError as e: 
            print(f"  ERROR: Invalid number for price/qty for SKU {sku}: {e}. Skipping.")
            return None
            
        payload={
            "name":product_name_for_bc, "type":"physical", "sku":sku, 
            "description":full_description_for_bc, "weight":FIXED_WEIGHT_VALUE, 
            "price":price, "categories":bc_cat_ids, "availability":"available", 
            "inventory_level":inventory, "inventory_tracking":"product", "is_visible":True 
        }
        if bc_brand_id: payload["brand_id"]=bc_brand_id
        
        resp_obj,resp_json=self._make_api_request("POST","/catalog/products",payload=payload)
        stat_check=resp_obj.status_code if resp_obj else resp_json.get('status_code')
        
        if stat_check in [200,201]:
            cd=resp_json.get("data",{})
            print(f"  SUCCESS: Product '{cd.get('name')}' (ID: {cd.get('id')}, SKU: {sku}) created in BigCommerce.")
            return cd
        else:
            print(f"  FAILURE: Product creation for SKU: {sku} failed. Status: {stat_check}")
            if resp_json: print(f"    Error details: {json.dumps(resp_json,indent=2)}")
            return None

    def upload_product_image(self,product_id,image_file_path,is_thumbnail=False,image_alt_text="Product Image"):
        if not os.path.exists(image_file_path): 
            print(f"  ERROR: Image file not found: {image_file_path}")
            return None
        
        endpoint=f"/catalog/products/{product_id}/images"
        file_upload_headers = {"X-Auth-Token": self.access_token, "Accept": "application/json"}
        form_data_payload = {'is_thumbnail': str(is_thumbnail).lower(), 'description': image_alt_text[:255]}
        
        try:
            with open(image_file_path,'rb') as f_img:
                files_payload = {'image_file': (os.path.basename(image_file_path), f_img)}
                url = f"{self.base_v3_url}{endpoint}"
                response_obj = requests.post(url, headers=file_upload_headers, data=form_data_payload, files=files_payload, timeout=60)
                
                response_json = {}
                try: response_json = response_obj.json()
                except json.JSONDecodeError: response_json = {"raw_text": response_obj.text}
                response_obj.raise_for_status()

            udi=response_json.get("data",{})
            print(f"  SUCCESS: Image uploaded for product ID {product_id}. Image ID: {udi.get('id')}")
            return udi
        except requests.exceptions.HTTPError as http_err:
            print(f"    HTTP error during image upload for product {product_id}: {http_err.response.status_code}")
            if http_err.response is not None:
                try: print(f"    Error details: {json.dumps(http_err.response.json(), indent=2)}")
                except: print(f"    Raw error response: {http_err.response.text[:300]}")
            return None
        except Exception as e: 
            print(f"  Unexpected image upload error for product ID {product_id}: {e}")
            return None