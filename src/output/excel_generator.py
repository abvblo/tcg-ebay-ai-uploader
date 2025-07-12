"""Excel file generation for eBay listings with batch processing and memory optimization"""

import asyncio
import gc
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from tqdm import tqdm

from ..api.openai_titles import OpenAITitleOptimizer
from ..config import Config
from ..models import CardData
from ..utils.logger import logger
from ..utils.metrics import MetricsTracker
from .ebay_formatter import EbayFormatter


class ExcelGenerator:
    """Generates Excel files for eBay listings with optimizations for large datasets"""

    def __init__(self, config: Config, metrics: Optional[MetricsTracker] = None):
        """Initialize with configuration and optional metrics tracker"""
        self.config = config
        self.output_folder = config.output_folder
        self.ebay_formatter = EbayFormatter(config)
        self.metrics = metrics or MetricsTracker()

        # Initialize OpenAI if available
        if config.openai_api_key:
            self.title_optimizer = OpenAITitleOptimizer(
                api_key=config.openai_api_key, rate_limit=self.config.processing.rate_limit_openai
            )
        else:
            self.title_optimizer = None
            logger.warning("OpenAI API key not found - title optimization disabled")

    async def create_excel(self, cards: List[CardData]) -> str:
        """Create Excel file with eBay listings including variation support"""
        start_time = datetime.now()

        # Optimize titles in batches
        logger.info("Optimizing listing titles...")
        optimized_titles = await self._optimize_titles_batch(cards)

        # Process cards in chunks to manage memory
        chunk_size = 100
        all_ebay_rows = []

        logger.info("Generating eBay listing data...")
        with tqdm(total=len(cards), desc="Processing cards") as pbar:
            for i in range(0, len(cards), chunk_size):
                chunk = cards[i : i + chunk_size]
                chunk_titles = optimized_titles[i : i + chunk_size]

                # Process chunk
                chunk_rows = []
                for j, (card, title) in enumerate(zip(chunk, chunk_titles)):
                    if card.is_variation_parent and card.variations:
                        # Process as variation parent
                        variation_rows = self._create_variation_listing(
                            card, title, len(all_ebay_rows) + len(chunk_rows)
                        )
                        chunk_rows.extend(variation_rows)
                    else:
                        # Process as single listing
                        chunk_rows.append(
                            self.ebay_formatter.format_card(
                                card, title, len(all_ebay_rows) + len(chunk_rows)
                            )
                        )

                # Add chunk results to main list
                all_ebay_rows.extend(chunk_rows)
                pbar.update(len(chunk))

                # Clear memory
                del chunk_rows
                if i + chunk_size < len(cards):
                    _ = gc.collect()

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tcg_listings_{timestamp}.xlsx"
        output_path = self.output_folder / filename

        # Write to Excel with optimized settings for large files
        logger.info(f"Writing {len(all_ebay_rows)} rows to Excel file...")
        self._write_to_excel(all_ebay_rows, output_path)

        # Log metrics
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Excel generation completed in {duration:.1f} seconds")

        if self.metrics:
            self.metrics.record_excel_generation(
                num_listings=len(cards), num_rows=len(all_ebay_rows), duration_seconds=duration
            )

        return str(output_path)

    async def _optimize_titles_batch(
        self, cards: List[CardData], batch_size: int = 20
    ) -> List[str]:
        """Optimize listing titles in batches"""
        if not self.title_optimizer:
            return [self._generate_fallback_title(card) for card in cards]

        all_titles = []
        card_dicts = [card.to_dict() for card in cards]

        # Process in batches to manage API rate limits
        for i in range(0, len(card_dicts), batch_size):
            batch = card_dicts[i : i + batch_size]
            try:
                batch_titles = await self.title_optimizer.optimize_titles(batch)
                all_titles.extend(batch_titles)

                # Log progress
                logger.debug(
                    f"Optimized titles for batch {i//batch_size + 1}/{(len(card_dicts)-1)//batch_size + 1}"
                )

                # Respect rate limiting
                if i + batch_size < len(card_dicts):
                    await asyncio.sleep(1)  # Small delay between batches

            except Exception as e:
                logger.error(f"Error optimizing titles for batch {i//batch_size + 1}: {e}")
                # Fall back to basic titles for failed batch
                fallback_titles = [
                    self._generate_fallback_title(card) for card in cards[i : i + batch_size]
                ]
                all_titles.extend(fallback_titles)

        return all_titles

    def _create_variation_listing(
        self, parent_card: CardData, title: str, start_index: int
    ) -> List[Dict[str, Any]]:
        """Create parent and child rows for a variation listing"""
        rows = []

        # Create parent row
        parent_row = self.ebay_formatter.format_card(parent_card, title, start_index)
        parent_row.update(
            {
                "*Relationship": "Parent",
                "*Quantity": "",
                "*StartPrice": "",
                "Variation Theme": "Copy Number",
                "CustomLabel": (
                    parent_card.variations[0]["custom_label"] if parent_card.variations else ""
                ),
            }
        )
        rows.append(parent_row)

        # Create child rows for each variation
        for i, variation in enumerate(parent_card.variations):
            child_row = self._create_variation_row(
                parent_card=parent_card,
                title=title,
                variation=variation,
                copy_number=i + 1,
                row_index=start_index + 1 + i,
            )
            rows.append(child_row)

        return rows

    def _create_variation_row(
        self,
        parent_card: CardData,
        title: str,
        variation: Dict[str, Any],
        copy_number: int,
        row_index: int,
    ) -> Dict[str, Any]:
        """Create a child row for a variation"""
        # Start with parent data and override specific fields
        row = self.ebay_formatter.format_card(parent_card, title, row_index)

        # Variation-specific fields
        row.update(
            {
                "*Action(SiteID=US|Country=US|Currency=USD|Version=1193)": "",
                "*Relationship": "Variation",
                "*VariationSpecifics": f"Copy Number=Copy #{copy_number}",
                "CustomLabel": variation.get("custom_label", ""),
                "*Title": "",  # Child rows don't need title
                "*Quantity": 1,
                "*StartPrice": parent_card.final_price,
                "C:Copy Number": f"Copy #{copy_number}",
            }
        )

        # Set variation images if available
        if variation.get("image_urls"):
            cache_busted_urls = [
                f"{url}?cb={i}" for i, url in enumerate(variation["image_urls"]) if url
            ]
            row["PicURL"] = "|".join(cache_busted_urls)

        # Clear fields that should be empty in child rows
        for field in [
            "*Category",
            "*ConditionID",
            "*Description",
            "*Format",
            "*Duration",
            "*Location",
            "PostalCode",
            "*DispatchTimeMax",
            "PaymentProfileName",
            "ShippingProfileName",
            "ReturnProfileName",
            "ConfidenceScore",
            "ReviewFlag",
            "PriceSource",
            "TCGPlayerLink",
            "ProcessingNotes",
        ]:
            row[field] = ""

        return row

    def _write_to_excel(self, rows: List[Dict[str, Any]], output_path: Path) -> None:
        """Write data to Excel with optimized settings"""
        # Convert to DataFrame with optimized dtypes
        df = pd.DataFrame(rows)

        # Optimize string columns
        for col in df.select_dtypes(include=["object"]).columns:
            df[col] = df[col].astype("string")

        # Write to Excel with optimized settings
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="eBay_Upload")

            # Apply formatting
            worksheet = writer.sheets["eBay_Upload"]
            self._apply_worksheet_formatting(worksheet, df)

    def _apply_worksheet_formatting(self, worksheet, df):
        """Apply formatting to the worksheet"""
        # Auto-size columns
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter

            # Find the maximum length of content in the column
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass

            # Set column width with some padding
            adjusted_width = (max_length + 2) * 1.1
            worksheet.column_dimensions[column_letter].width = min(adjusted_width, 50)  # Cap at 50

        # Freeze header row
        worksheet.freeze_panes = "A2"

        # Format header
        for cell in worksheet[1]:
            cell.style = "Headline 4"

    def _generate_fallback_title(self, card: CardData) -> str:
        """Generate a fallback title when optimization is not available"""
        parts = []

        # Game prefix
        game = card.game.lower()
        if "pokémon" in game or "pokemon" in game:
            parts.append("Pokémon")
        elif "magic" in game or "mtg" in game:
            parts.append("MTG")
        else:
            parts.append(card.game)

        # Card name
        parts.append(card.name)

        # Card number if available
        if card.number:
            parts.append(card.number)

        # Set name if available
        if card.set_name:
            parts.append(card.set_name)

        # Rarity (only if not common)
        if card.rarity and card.rarity.lower() not in ["common", "uncommon", "normal", "regular"]:
            parts.append(card.rarity)

        # Finish (only if not standard)
        if card.finish and card.finish.lower() not in [
            "normal",
            "regular",
            "standard",
            "non-holo",
            "non-foil",
        ]:
            parts.append(card.finish)

        # First unique characteristic (if any)
        if card.unique_characteristics and card.unique_characteristics[0].lower() != "unlimited":
            parts.append(card.unique_characteristics[0])

        # Condition and language
        parts.append("NM/LP")

        if card.language and card.language.lower() in ["japanese", "jp"]:
            parts.append("JP")

        # Join with spaces and limit length
        title = " ".join(str(part) for part in parts if part)
        return title[:80]  # eBay title length limit

    def _generate_variation_title(self, base_title: str, copy_num: int) -> str:
        """Generate a title for a variation"""
        # Keep the base title but indicate it's a variation
        return f"{base_title} - Copy {copy_num}"
