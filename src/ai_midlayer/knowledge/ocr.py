"""OCR client for image and document text extraction.

Supports:
- DeepSeek-OCR via OpenAI-compatible API
- Image OCR, document to markdown, image description
- PDF page image extraction and OCR

Usage:
    client = OCRClient(api_key="sk-xxx", base_url="https://www.dmxapi.cn/v1")
    text = client.ocr_image("scan.jpg")
    markdown = client.ocr_to_markdown("document.jpg")
"""

import base64
import os
from pathlib import Path
from typing import Optional

import httpx


class OCRPromptTemplate:
    """OCR prompt templates for DeepSeek-OCR."""
    
    # Basic OCR - no layout recognition
    FREE_OCR = "<image>\nFree OCR."
    
    # Document to Markdown with layout
    DOCUMENT_TO_MARKDOWN = "<image>\n<|grounding|>Convert the document to markdown."
    
    # General image OCR with grounding
    OCR_IMAGE = "<image>\n<|grounding|>OCR this image."
    
    # Parse figures and charts
    PARSE_FIGURE = "<image>\nParse the figure."
    
    # Detailed image description
    DESCRIBE_IMAGE = "<image>\nDescribe this image in detail."


class OCRClient:
    """Client for DeepSeek-OCR API.
    
    Uses OpenAI-compatible chat completions endpoint with vision support.
    """
    
    MODEL = "DeepSeek-OCR"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 120.0,
    ):
        """Initialize OCR client.
        
        Args:
            api_key: API key (defaults to MIDLAYER_OCR_API_KEY env var)
            base_url: API base URL (defaults to MIDLAYER_OCR_BASE_URL env var)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("MIDLAYER_OCR_API_KEY")
        self.base_url = (base_url or os.getenv("MIDLAYER_OCR_BASE_URL", "https://www.dmxapi.cn/v1")).rstrip("/")
        self.timeout = timeout
        
        if not self.api_key:
            raise ValueError("OCR API key is required. Set MIDLAYER_OCR_API_KEY or pass api_key.")
    
    def _encode_image(self, image_path: str | Path) -> str:
        """Encode image to base64 data URL."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        
        # Determine MIME type
        suffix = path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        mime_type = mime_types.get(suffix, "image/jpeg")
        
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        
        return f"data:{mime_type};base64,{data}"
    
    def _encode_image_bytes(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Encode image bytes to base64 data URL."""
        data = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{data}"
    
    def _call_api(self, image_url: str, prompt: str) -> str:
        """Call DeepSeek-OCR API.
        
        Args:
            image_url: Image URL or base64 data URL
            prompt: OCR prompt template
            
        Returns:
            OCR result text
        """
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": prompt,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                        }
                    ],
                }
            ],
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                
                data = response.json()
                return data["choices"][0]["message"]["content"]
                
        except httpx.HTTPError as e:
            raise RuntimeError(f"OCR API error: {e}")
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected OCR API response: {e}")
    
    def ocr_image(self, image_path: str | Path) -> str:
        """Extract text from image using basic OCR.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Extracted text
        """
        image_url = self._encode_image(image_path)
        return self._call_api(image_url, OCRPromptTemplate.FREE_OCR)
    
    def ocr_image_bytes(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Extract text from image bytes.
        
        Args:
            image_bytes: Image data
            mime_type: Image MIME type
            
        Returns:
            Extracted text
        """
        image_url = self._encode_image_bytes(image_bytes, mime_type)
        return self._call_api(image_url, OCRPromptTemplate.FREE_OCR)
    
    def ocr_to_markdown(self, image_path: str | Path) -> str:
        """Convert document image to Markdown.
        
        Best for: scanned documents, PDFs, structured text.
        Preserves layout, headings, lists, tables.
        
        Args:
            image_path: Path to document image
            
        Returns:
            Markdown formatted text
        """
        image_url = self._encode_image(image_path)
        return self._call_api(image_url, OCRPromptTemplate.DOCUMENT_TO_MARKDOWN)
    
    def ocr_to_markdown_bytes(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """Convert document image bytes to Markdown.
        
        Args:
            image_bytes: Image data
            mime_type: Image MIME type
            
        Returns:
            Markdown formatted text
        """
        image_url = self._encode_image_bytes(image_bytes, mime_type)
        return self._call_api(image_url, OCRPromptTemplate.DOCUMENT_TO_MARKDOWN)
    
    def parse_figure(self, image_path: str | Path) -> str:
        """Parse figure, chart, or diagram.
        
        Best for: charts, graphs, diagrams, tables.
        
        Args:
            image_path: Path to figure image
            
        Returns:
            Parsed content description
        """
        image_url = self._encode_image(image_path)
        return self._call_api(image_url, OCRPromptTemplate.PARSE_FIGURE)
    
    def describe_image(self, image_path: str | Path) -> str:
        """Get detailed image description.
        
        Best for: photos, illustrations, screenshots.
        
        Args:
            image_path: Path to image
            
        Returns:
            Detailed description
        """
        image_url = self._encode_image(image_path)
        return self._call_api(image_url, OCRPromptTemplate.DESCRIBE_IMAGE)


def get_ocr_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> OCRClient:
    """Get an OCR client, optionally from environment config.
    
    Args:
        api_key: API key override
        base_url: Base URL override
        
    Returns:
        Configured OCRClient instance.
    """
    return OCRClient(
        api_key=api_key or os.getenv("MIDLAYER_OCR_API_KEY"),
        base_url=base_url or os.getenv("MIDLAYER_OCR_BASE_URL", "https://www.dmxapi.cn/v1"),
    )
