#!/usr/bin/env python3
"""
Validate downloaded images for quality and white background
"""

import os
import sys
from PIL import Image
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agents.image_agent import ImageSourcingAgent

def validate_downloaded_images():
    """Validate all downloaded images"""
    print("🧪 VALIDATING DOWNLOADED IMAGES")
    print("=" * 40)
    
    agent = ImageSourcingAgent(None)  # Just for the validation methods
    
    image_dirs = [
        "product_images_batch_final/33-2031-2",
        "product_images_batch_final/24-186728"
    ]
    
    for img_dir in image_dirs:
        if not os.path.exists(img_dir):
            print(f"❌ Directory not found: {img_dir}")
            continue
            
        print(f"\n📁 Checking {img_dir}:")
        
        for filename in os.listdir(img_dir):
            if filename.endswith('.jpg'):
                filepath = os.path.join(img_dir, filename)
                print(f"  🖼️  {filename}:")
                
                try:
                    # Load image
                    with open(filepath, 'rb') as f:
                        image_bytes = f.read()
                    
                    # Check dimensions
                    img = Image.open(io.BytesIO(image_bytes))
                    print(f"     Dimensions: {img.width}x{img.height}")
                    
                    # Check if meets minimum requirements
                    min_check = agent._check_original_image_dimensions(image_bytes)
                    print(f"     Min dimensions: {'✓' if min_check else '✗'}")
                    
                    # Check white background
                    white_bg = agent._is_white_background(image_bytes)
                    print(f"     White background: {'✓' if white_bg else '✗'}")
                    
                    # File size
                    size_kb = len(image_bytes) / 1024
                    print(f"     Size: {size_kb:.1f} KB")
                    
                    img.close()
                    
                except Exception as e:
                    print(f"     ❌ Error: {e}")

if __name__ == "__main__":
    validate_downloaded_images()