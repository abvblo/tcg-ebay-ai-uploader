"""eBay EPS (Picture Services) Uploader"""

import aiohttp
import asyncio
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageOps
from io import BytesIO
import aiofiles
from ..utils.logger import logger

class EbayEPSUploader:
    def __init__(self, ebay_config: dict, rate_limit: float = 0.15):
        self.config = ebay_config
        self.rate_limit = rate_limit
        self.api_url = "https://api.ebay.com/ws/api.dll"
    
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
            body_bytes = self._build_multipart_body(xml_payload, image_data, filename, 
                                                   content_type, boundary)
            
            headers = self._build_headers(boundary)
            
            # Rate limiting
            await asyncio.sleep(self.rate_limit)
            
            # Upload
            async with session.post(
                self.api_url,
                headers=headers,
                data=body_bytes
            ) as response:
                if response.status == 200:
                    response_text = await response.text()
                    return self._extract_url_from_response(response_text)
                else:
                    logger.error(f"❌ eBay EPS HTTP Error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ eBay EPS Upload Error: {e}")
            return None
    
    async def _optimize_image(self, image_path: str) -> Tuple[bytes, str, str]:
        """Optimize image for eBay EPS - PNG format for best quality"""
        try:
            async with aiofiles.open(image_path, 'rb') as f:
                image_data = await f.read()
            
            with Image.open(BytesIO(image_data)) as img:
                # Handle EXIF orientation
                img = ImageOps.exif_transpose(img)
                
                # Convert to appropriate mode
                if img.mode not in ('RGBA', 'RGB'):
                    if img.mode in ('P', 'LA'):
                        img = img.convert('RGBA')
                    else:
                        img = img.convert('RGB')
                
                # Scale if needed
                max_dimension = 1600
                width, height = img.size
                
                if width > max_dimension or height > max_dimension:
                    ratio = min(max_dimension / width, max_dimension / height)
                    new_width = int(width * ratio)
                    new_height = int(height * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save as PNG
                output = BytesIO()
                img.save(output, format='PNG', optimize=True)
                return output.getvalue(), 'image/png', '.png'
                
        except Exception as e:
            logger.warning(f"Could not optimize image: {e}, using original")
            async with aiofiles.open(image_path, 'rb') as f:
                data = await f.read()
            ext = Path(image_path).suffix.lower()
            content_type = 'image/png' if ext == '.png' else 'image/jpeg'
            return data, content_type, ext
    
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
    
    def _build_multipart_body(self, xml_payload: str, image_data: bytes, 
                             filename: str, content_type: str, boundary: str) -> bytes:
        """Build multipart form data body"""
        body_parts = [
            f'--{boundary}',
            'Content-Disposition: form-data; name="XMLPayload"',
            'Content-Type: text/xml; charset=utf-8',
            '',
            xml_payload,
            f'--{boundary}',
            f'Content-Disposition: form-data; name="file"; filename="{filename}"',
            f'Content-Type: {content_type}',
            '',
        ]
        
        body_text = '\r\n'.join(body_parts) + '\r\n'
        return body_text.encode('utf-8') + image_data + f'\r\n--{boundary}--\r\n'.encode('utf-8')
    
    def _build_headers(self, boundary: str) -> dict:
        """Build request headers"""
        return {
            "X-EBAY-API-COMPATIBILITY-LEVEL": "1193",
            "X-EBAY-API-DEV-NAME": self.config['devid'],
            "X-EBAY-API-APP-NAME": self.config['appid'],
            "X-EBAY-API-CERT-NAME": self.config['certid'],
            "X-EBAY-API-CALL-NAME": "UploadSiteHostedPictures",
            "X-EBAY-API-SITEID": "0",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
    
    def _extract_url_from_response(self, response_text: str) -> Optional[str]:
        """Extract image URL from eBay response"""
        try:
            root = ET.fromstring(response_text)
            ns = {'ebay': 'urn:ebay:apis:eBLBaseComponents'}
            
            ack = root.find('ebay:Ack', ns)
            if ack is not None and ack.text == 'Success':
                # Try FullURL first, then BaseURL
                full_url_elem = root.find('.//ebay:FullURL', ns)
                if full_url_elem is not None:
                    return full_url_elem.text
                
                base_url_elem = root.find('.//ebay:BaseURL', ns)
                if base_url_elem is not None:
                    return base_url_elem.text
            
            # Log errors if any
            errors = root.findall('.//ebay:LongMessage', ns)
            error_messages = [error.text for error in errors if error.text]
            if error_messages:
                logger.error(f"❌ eBay EPS Error: {'; '.join(error_messages)}")
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error parsing eBay response: {e}")
            return None