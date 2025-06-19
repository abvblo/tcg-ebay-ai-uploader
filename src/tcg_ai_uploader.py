#!/usr/bin/env python3
"""
TCG eBay AI Batch Uploader
Updated for folder structure and pathlib support
"""

import pandas as pd
import requests
import json
import os
import glob
import re
from pathlib import Path
import base64
from datetime import datetime
from google.cloud import vision
from card_recognizer import CardRecognizer

class TCGAIUploader:
    def __init__(self, config_file='config.json'):
        """Initialize the AI uploader with configuration"""
        base_path = Path(__file__).resolve().parents[1]
        config_path = base_path / "config" / config_file

        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.imgur_client_id = self.config['imgur_client_id']
        self.scans_folder = base_path / self.config['scans_folder']
        self.card_recognizer = CardRecognizer(self.config)

        # Set up Google Vision client
        creds_path = base_path / self.config['google_credentials_path']
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "/Users/mateoallen/Library/CloudStorage/GoogleDrive-abovebelow.gg@gmail.com/My Drive/Project Folders/TCG eBay Batch Uploader/config/google-credentials.json"
        print(f"🔐 Using credentials from: {os.environ['GOOGLE_APPLICATION_CREDENTIALS']}")
        self.vision_client = vision.ImageAnnotatorClient()

    def find_images(self):
        """Find and sort image files in the scans folder"""
        print(f"🖼️  Scanning for images in: {self.scans_folder}")
        image_files = sorted(self.scans_folder.glob("*.jpg")) + \
                      sorted(self.scans_folder.glob("*.jpeg")) + \
                      sorted(self.scans_folder.glob("*.png"))

        if not image_files:
            print("❌ No images found.")
        else:
            print(f"✅ Found {len(image_files)} image(s).")
        return image_files

    def extract_text_from_image(self, image_path):
        """Use Google Vision API to extract text from card image"""
        print(f"🔍 Analyzing: {image_path.name}")
        try:
            with open(image_path, 'rb') as image_file:
                content = image_file.read()

            image = vision.Image(content=content)
            response = self.vision_client.text_detection(image=image)

            if response.error.message:
                raise Exception(f"Vision API error: {response.error.message}")

            texts = response.text_annotations
            if texts:
                full_text = texts[0].description
                print(f"   📝 Extracted text: {full_text[:100]}...")
                return full_text
            else:
                print("⚠️  No text found in image")
                return ""

        except Exception as e:
            print(f"❌ Error analyzing image: {e}")
            return ""

    def recognize_card_from_text(self, extracted_text, image_path):
        print("🃏 Identifying card from extracted text...")
        card_data = self.card_recognizer.identify_card(extracted_text, image_path)
        if card_data:
            print(f"✅ Identified: {card_data['name']} from {card_data['set_name']}")
        return card_data

    def upload_to_imgur(self, image_path):
        """Upload a single image to Imgur and return the URL"""
        print(f"📤 Uploading: {image_path.name}")
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode()

            headers = {'Authorization': f'Client-ID {self.imgur_client_id}'}
            data = {'image': image_data, 'type': 'base64'}

            response = requests.post('https://api.imgur.com/3/image', headers=headers, data=data)
            if response.status_code == 200:
                return response.json()['data']['link']
            else:
                print(f"❌ Upload failed: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Error uploading: {e}")
            return None

    def generate_title(self, card_data):
        parts = [
            card_data['name'],
            card_data.get('number', ''),
            card_data.get('set_name', ''),
            card_data.get('finish', 'Normal'),
            self.condition_to_abbreviation(card_data.get('condition', 'Near Mint'))
        ]
        title = ' | '.join([p for p in parts if p])
        return title[:80]

    def condition_to_abbreviation(self, condition):
        return {
            'Near Mint': 'NM',
            'Lightly Played': 'LP',
            'Moderately Played': 'MP',
            'Heavily Played': 'HP',
            'Damaged': 'DMG'
        }.get(condition, 'NM')

    def create_ebay_listings(self, card_data_list):
        listings = []
        for i, card_data in enumerate(card_data_list, 1):
            row = {
                'SKU': f"{card_data['name'].replace(' ', '')}_{card_data.get('number', '')}_{i}",
                'Title': self.generate_title(card_data),
                'Condition': self.map_condition_to_ebay(card_data['condition']),
                'Price': card_data.get('market_price', 5.00),
                'Quantity': 1,
                'Picture URL 1': card_data.get('image_url', ''),
                'Card Name': card_data['name'],
                'Card Number': card_data.get('number', ''),
                'Set': card_data.get('set_name', ''),
                'Finish': card_data.get('finish', ''),
                'Language': card_data.get('language', ''),
                'Rarity': card_data.get('rarity', ''),
                'Game': card_data.get('game', '')
            }
            listings.append(row)
        return pd.DataFrame(listings)

    def map_condition_to_ebay(self, condition):
        return self.config['condition_mapping'].get(condition, 'LIKE_NEW')

    def save_output_csv(self, df, output_file='ai_output.csv'):
        output_path = Path(__file__).resolve().parents[1] / 'data' / output_file
        df.to_csv(output_path, index=False)
        print(f"✅ Saved {len(df)} listings to {output_path}")
        return True

    def run_ai_batch_process(self, output_file='ai_output.csv'):
        print("🚀 Starting AI Batch Process...\n")
        image_files = self.find_images()
        if not image_files:
            return False

        card_data_list = []
        for i, image_path in enumerate(image_files, 1):
            text = self.extract_text_from_image(image_path)
            if not text:
                continue

            card_data = self.recognize_card_from_text(text, image_path)
            if not card_data:
                continue

            card_data['condition'] = 'Near Mint'  # default for now
            card_data['image_url'] = self.upload_to_imgur(image_path)
            card_data['import_sequence'] = i
            card_data_list.append(card_data)

        if not card_data_list:
            print("❌ No cards processed successfully.")
            return False

        df = self.create_ebay_listings(card_data_list)
        self.save_output_csv(df, output_file)
        print("🎉 Done!")
        return True

def main():
    uploader = TCGAIUploader()
    output = input("Enter output filename (or press Enter for 'ai_output.csv'): ").strip()
    if not output:
        output = 'ai_output.csv'
    uploader.run_ai_batch_process(output)

if __name__ == "__main__":
    main()