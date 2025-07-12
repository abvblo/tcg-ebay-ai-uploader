"""eBay EPS (Picture Services) Uploader with enhanced async image processing"""

import asyncio
import time
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiofiles
import aiohttp

from ..processing.async_image_processor import AsyncImageProcessor
from ..utils.logger import logger
from ..utils.rate_limiter import rate_limiter


class EbayEPSUploader:
    def __init__(self, ebay_config: dict, rate_limit: float = 0.15):
        self.config = ebay_config
        self.rate_limit = rate_limit  # Keep for backwards compatibility
        self.api_url = "https://api.ebay.com/ws/api.dll"
        self.endpoint_name = "ebay_eps"
        # Initialize async image processor for better performance
        self.image_processor = AsyncImageProcessor(max_dimension=1600, max_workers=4)

    async def upload_image(self, image_path: str, session: aiohttp.ClientSession) -> Optional[str]:
        """Upload image to eBay EPS"""
        try:
            # Optimize image
            image_data, content_type, file_ext = await self._optimize_image(image_path)

            # Create request
            timestamp = int(time.time() * 1000)
            base_filename = Path(image_path).stem
            filename = f"TCGCard_HQ_{timestamp}_{base_filename}{file_ext}"

            # Build XML payload
            xml_payload = self._build_xml_payload(filename)

            # Create multipart data
            boundary = f"----formdata-{timestamp}"
            body_bytes = self._build_multipart_body(
                xml_payload, image_data, filename, content_type, boundary
            )

            headers = self._build_headers(boundary)

            # Use adaptive rate limiting
            await rate_limiter.acquire(self.endpoint_name)

            # Upload
            async with session.post(self.api_url, headers=headers, data=body_bytes) as response:
                if response.status == 200:
                    response_text = await response.text()
                    url = self._extract_url_from_response(response_text)
                    if url:
                        rate_limiter.report_success(self.endpoint_name)
                    else:
                        rate_limiter.report_error(self.endpoint_name)
                    return url
                elif response.status == 429:
                    rate_limiter.report_error(self.endpoint_name, is_rate_limit_error=True)
                    logger.error(f"❌ eBay EPS rate limit: {response.status}")
                    return None
                else:
                    rate_limiter.report_error(self.endpoint_name)
                    logger.error(f"❌ eBay EPS HTTP Error: {response.status}")
                    return None

        except Exception as e:
            rate_limiter.report_error(self.endpoint_name)
            logger.error(f"❌ eBay EPS Upload Error: {e}")
            return None

    async def upload_batch(
        self, image_paths: List[str], session: aiohttp.ClientSession
    ) -> Dict[str, Optional[str]]:
        """Upload multiple images concurrently with batch processing"""
        # Process images in batches to avoid overwhelming the API
        batch_size = 10
        results = {}

        for i in range(0, len(image_paths), batch_size):
            batch = image_paths[i : i + batch_size]

            # Upload batch concurrently
            tasks = [self.upload_image(path, session) for path in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for path, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to upload {path}: {result}")
                    results[path] = None
                else:
                    results[path] = result

            # Add delay between batches to respect rate limits
            if i + batch_size < len(image_paths):
                await asyncio.sleep(1.0)

        return results

    async def _optimize_image(self, image_path: str) -> Tuple[bytes, str, str]:
        """Optimize image using async image processor for better performance"""
        # Use the async image processor instead of synchronous PIL operations
        return await self.image_processor.optimize_for_upload(image_path)

    def _build_xml_payload(self, filename: str) -> str:
        """Build XML payload for eBay EPS"""
        return f"""<?xml version="1.0" encoding="utf-8"?>
<UploadSiteHostedPicturesRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials>
    <eBayAuthToken>{self.config['token']}</eBayAuthToken>
  </RequesterCredentials>
  <PictureName>{filename}</PictureName>
  <ExtensionInDays>30</ExtensionInDays>
</UploadSiteHostedPicturesRequest>"""

    def _build_multipart_body(
        self, xml_payload: str, image_data: bytes, filename: str, content_type: str, boundary: str
    ) -> bytes:
        """Build multipart form data body"""
        body_parts = [
            f"--{boundary}",
            'Content-Disposition: form-data; name="XMLPayload"',
            "Content-Type: text/xml; charset=utf-8",
            "",
            xml_payload,
            f"--{boundary}",
            f'Content-Disposition: form-data; name="file"; filename="{filename}"',
            f"Content-Type: {content_type}",
            "",
        ]

        body_text = "\r\n".join(body_parts) + "\r\n"
        return body_text.encode("utf-8") + image_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    def _build_headers(self, boundary: str) -> dict:
        """Build request headers"""
        return {
            "X-EBAY-API-COMPATIBILITY-LEVEL": "1193",
            "X-EBAY-API-DEV-NAME": self.config["devid"],
            "X-EBAY-API-APP-NAME": self.config["appid"],
            "X-EBAY-API-CERT-NAME": self.config["certid"],
            "X-EBAY-API-CALL-NAME": "UploadSiteHostedPictures",
            "X-EBAY-API-SITEID": "0",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }

    def _extract_url_from_response(self, response_text: str) -> Optional[str]:
        """Extract image URL from eBay response"""
        try:
            root = ET.fromstring(response_text)
            ns = {"ebay": "urn:ebay:apis:eBLBaseComponents"}

            ack = root.find("ebay:Ack", ns)
            if ack is not None and ack.text == "Success":
                # Try FullURL first, then BaseURL
                full_url_elem = root.find(".//ebay:FullURL", ns)
                if full_url_elem is not None:
                    return full_url_elem.text

                base_url_elem = root.find(".//ebay:BaseURL", ns)
                if base_url_elem is not None:
                    return base_url_elem.text

            # Log errors if any
            errors = root.findall(".//ebay:LongMessage", ns)
            error_messages = [error.text for error in errors if error.text]
            if error_messages:
                logger.error(f"❌ eBay EPS Error: {'; '.join(error_messages)}")

            return None

        except Exception as e:
            logger.error(f"❌ Error parsing eBay response: {e}")
            return None
