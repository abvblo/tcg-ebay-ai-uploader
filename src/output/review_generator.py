"""Generate HTML review file for manual verification"""

import os
from datetime import datetime
from pathlib import Path
from typing import List

from ..models import CardData
from ..utils.logger import logger


class ReviewGenerator:
    def __init__(self, output_folder: Path):
        self.output_folder = output_folder

    def generate_review_html(self, cards: List[CardData]) -> str:
        """Generate HTML file for visual review of identified cards"""
        # Filter cards that need review
        cards_to_review = [
            card
            for card in cards
            if card.review_flag != "OK"
            or any(term in card.name.lower() for term in [" v", " vmax", " gx", " ex", "break"])
        ]

        if not cards_to_review:
            logger.info("✅ No cards require manual review")
            return None

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>TCG Card Review</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .card-review {{ 
            background: white; 
            border: 2px solid #ddd; 
            border-radius: 10px; 
            padding: 20px; 
            margin-bottom: 30px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .card-images {{ display: flex; gap: 20px; margin-bottom: 20px; }}
        .card-image {{ 
            max-width: 300px; 
            border: 1px solid #ccc; 
            border-radius: 5px;
        }}
        .card-info {{ background: #f9f9f9; padding: 15px; border-radius: 5px; }}
        .card-title {{ font-size: 20px; font-weight: bold; margin-bottom: 10px; }}
        .confidence {{ 
            display: inline-block; 
            padding: 5px 10px; 
            border-radius: 5px; 
            font-weight: bold;
        }}
        .high-confidence {{ background: #d4edda; color: #155724; }}
        .medium-confidence {{ background: #fff3cd; color: #856404; }}
        .low-confidence {{ background: #f8d7da; color: #721c24; }}
        .review-flag {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 5px;
            margin-left: 10px;
            font-weight: bold;
        }}
        .flag-ok {{ background: #d4edda; color: #155724; }}
        .flag-review {{ background: #f8d7da; color: #721c24; }}
        .price-info {{ margin-top: 10px; font-size: 18px; }}
        .warning {{ 
            background: #fff3cd; 
            border: 1px solid #ffeeba;
            color: #856404;
            padding: 10px;
            margin-top: 10px;
            border-radius: 5px;
        }}
        h1 {{ color: #333; }}
        .summary {{ 
            background: white; 
            padding: 20px; 
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
    </style>
</head>
<body>
    <h1>🔍 TCG Card Identification Review</h1>
    <div class="summary">
        <h2>Summary</h2>
        <p>Total cards for review: <strong>{len(cards_to_review)}</strong></p>
        <p>Review the images below to verify the AI identification is correct.</p>
        <p>Pay special attention to cards marked with review flags.</p>
    </div>
"""

        for card in cards_to_review:
            confidence_pct = card.confidence * 100
            confidence_class = (
                "high-confidence"
                if confidence_pct >= 95
                else "medium-confidence" if confidence_pct >= 90 else "low-confidence"
            )

            review_class = "flag-ok" if card.review_flag == "OK" else "flag-review"

            html_content += f"""
    <div class="card-review">
        <div class="card-title">{card.name} - {card.set_name}</div>
        
        <div class="card-images">
"""

            # Add all images
            for idx, img_url in enumerate(card.image_urls[:2]):  # Show max 2 images
                html_content += f'            <img src="{img_url}" class="card-image" alt="Card image {idx+1}">\n'

            html_content += f"""
        </div>
        
        <div class="card-info">
            <p><strong>Identified as:</strong> {card.name}</p>
            <p><strong>Set:</strong> {card.set_name}</p>
            <p><strong>Number:</strong> {card.number}</p>
            <p><strong>Rarity:</strong> {card.rarity}</p>
            <p>
                <span class="confidence {confidence_class}">Confidence: {confidence_pct:.1f}%</span>
                <span class="review-flag {review_class}">Review: {card.review_flag}</span>
            </p>
            <p class="price-info">💰 Price: ${card.final_price:.2f} (Source: {card.price_source})</p>
"""

            # Add warnings for specific issues
            if card.review_flag == "HIGH_VALUE_VERIFY":
                html_content += """
            <div class="warning">
                ⚠️ High-value card type detected. Please verify this identification carefully.
            </div>
"""
            elif card.review_flag == "POSSIBLE_MISIDENTIFICATION":
                html_content += """
            <div class="warning">
                ⚠️ Possible misidentification detected based on card patterns.
            </div>
"""

            html_content += """
        </div>
    </div>
"""

        html_content += """
</body>
</html>
"""

        # Save HTML file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"card_review_{timestamp}.html"
        output_path = self.output_folder / filename

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"📋 Created review file: {output_path}")
        return str(output_path)
