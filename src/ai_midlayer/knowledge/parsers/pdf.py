"""PDF parser with OCR support for scanned documents.

Features:
- Standard PDF text extraction (pypdf)
- Scanned PDF detection
- OCR fallback for scanned pages (DeepSeek-OCR)
- Image extraction from PDF

Usage:
    parser = PDFParser()
    doc = parser.parse("document.pdf")
    
    # With OCR for scanned PDFs
    from ai_midlayer.knowledge.ocr import OCRClient
    ocr = OCRClient(api_key="...", base_url="...")
    parser = PDFParser(ocr_client=ocr)
    doc = parser.parse("scanned.pdf")
"""

import io
import tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime

from ai_midlayer.knowledge.models import Document
from ai_midlayer.knowledge.parsers.base import BaseParser


class PDFParser(BaseParser):
    """PDF parser with OCR support.
    
    Automatically detects scanned PDFs and uses OCR when available.
    """
    
    # Minimum text per page to consider it a text PDF (not scanned)
    MIN_TEXT_PER_PAGE = 50
    
    # Supported extensions
    EXTENSIONS = {".pdf"}
    
    def __init__(
        self,
        ocr_client=None,
        ocr_all_pages: bool = False,
        use_markdown: bool = True,
    ):
        """Initialize PDF parser.
        
        Args:
            ocr_client: Optional OCRClient for scanned PDF support
            ocr_all_pages: If True, OCR all pages (not just scanned ones)
            use_markdown: If True, use markdown conversion for OCR
        """
        self.ocr_client = ocr_client
        self.ocr_all_pages = ocr_all_pages
        self.use_markdown = use_markdown
        
        # Check if pypdf is available
        try:
            import pypdf
            self._pypdf_available = True
        except ImportError:
            self._pypdf_available = False
    
    def supports(self, path: str | Path) -> bool:
        """Check if file is a PDF."""
        return Path(path).suffix.lower() in self.EXTENSIONS
    
    def parse(self, path: str | Path) -> Optional[Document]:
        """Parse PDF file.
        
        Flow:
        1. Try pypdf text extraction
        2. If text is sparse → detect as scanned
        3. If scanned and OCR available → OCR each page
        4. Combine results
        
        Args:
            path: Path to PDF file
            
        Returns:
            Document with extracted text
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")
        
        if not self._pypdf_available:
            # Fallback: try to read as binary and OCR if available
            if self.ocr_client:
                return self._parse_with_ocr_only(path)
            raise ImportError("pypdf is required for PDF parsing. Install with: pip install pypdf")
        
        import pypdf
        
        try:
            reader = pypdf.PdfReader(str(path))
            num_pages = len(reader.pages)
            
            # Extract text from all pages
            page_texts = []
            scanned_pages = []
            
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                page_texts.append(text)
                
                # Check if page is scanned (very little text)
                if len(text.strip()) < self.MIN_TEXT_PER_PAGE:
                    scanned_pages.append(i)
            
            # Determine if document is primarily scanned
            is_scanned = len(scanned_pages) > num_pages / 2
            
            # If scanned and OCR available, process scanned pages
            if (is_scanned or self.ocr_all_pages) and self.ocr_client:
                page_texts = self._ocr_pages(path, reader, scanned_pages if not self.ocr_all_pages else list(range(num_pages)))
            
            # Combine all page texts
            content = "\n\n---\n\n".join(
                f"## Page {i+1}\n\n{text}" 
                for i, text in enumerate(page_texts) 
                if text.strip()
            )
            
            # Create document
            doc = Document(
                file_name=path.name,
                file_type="pdf",
                content=content,
                source_path=str(path.absolute()),
                created_at=datetime.now(),
                metadata={
                    "num_pages": num_pages,
                    "is_scanned": is_scanned,
                    "ocr_pages": scanned_pages if self.ocr_client else [],
                },
            )
            
            return doc
            
        except Exception as e:
            # If parsing fails, try OCR-only approach
            if self.ocr_client:
                return self._parse_with_ocr_only(path)
            raise RuntimeError(f"Failed to parse PDF: {e}")
    
    def _ocr_pages(self, path: Path, reader, page_indices: list[int]) -> list[str]:
        """OCR specific pages of PDF.
        
        Args:
            path: PDF path
            reader: pypdf.PdfReader
            page_indices: Indices of pages to OCR
            
        Returns:
            List of page texts
        """
        import pypdf
        
        # Get existing texts
        page_texts = [page.extract_text() or "" for page in reader.pages]
        
        # Convert pages to images and OCR
        for i in page_indices:
            try:
                image_bytes = self._page_to_image(path, i)
                if image_bytes:
                    if self.use_markdown:
                        text = self.ocr_client.ocr_to_markdown_bytes(image_bytes)
                    else:
                        text = self.ocr_client.ocr_image_bytes(image_bytes)
                    page_texts[i] = text
            except Exception as e:
                # Keep original text on OCR failure
                print(f"OCR failed for page {i}: {e}")
        
        return page_texts
    
    def _page_to_image(self, path: Path, page_index: int) -> Optional[bytes]:
        """Convert PDF page to image bytes.
        
        Uses pdf2image if available, otherwise tries pypdf image extraction.
        """
        # Try pdf2image first (best quality)
        try:
            from pdf2image import convert_from_path
            
            images = convert_from_path(
                str(path),
                first_page=page_index + 1,
                last_page=page_index + 1,
                dpi=150,
            )
            
            if images:
                buffer = io.BytesIO()
                images[0].save(buffer, format="PNG")
                return buffer.getvalue()
        except ImportError:
            pass
        except Exception:
            pass
        
        # Fallback: try to extract embedded images from page
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            page = reader.pages[page_index]
            
            # Try to get images from page resources
            if "/XObject" in page["/Resources"]:
                x_objects = page["/Resources"]["/XObject"].get_object()
                for obj in x_objects.values():
                    if obj["/Subtype"] == "/Image":
                        data = obj.get_data()
                        return data
        except Exception:
            pass
        
        return None
    
    def _parse_with_ocr_only(self, path: Path) -> Document:
        """Parse PDF using only OCR (no pypdf).
        
        Converts entire PDF to images and OCRs each page.
        """
        try:
            from pdf2image import convert_from_path
            
            images = convert_from_path(str(path), dpi=150)
            
            page_texts = []
            for i, image in enumerate(images):
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                
                if self.use_markdown:
                    text = self.ocr_client.ocr_to_markdown_bytes(buffer.getvalue())
                else:
                    text = self.ocr_client.ocr_image_bytes(buffer.getvalue())
                
                page_texts.append(text)
            
            content = "\n\n---\n\n".join(
                f"## Page {i+1}\n\n{text}" 
                for i, text in enumerate(page_texts) 
                if text.strip()
            )
            
            return Document(
                file_name=path.name,
                file_type="pdf",
                content=content,
                source_path=str(path.absolute()),
                created_at=datetime.now(),
                metadata={
                    "num_pages": len(images),
                    "is_scanned": True,
                    "ocr_pages": list(range(len(images))),
                },
            )
            
        except ImportError:
            raise ImportError(
                "pdf2image is required for OCR-only PDF parsing. "
                "Install with: pip install pdf2image"
            )
    
    def is_scanned_pdf(self, path: str | Path) -> bool:
        """Check if PDF is a scanned document.
        
        Args:
            path: Path to PDF file
            
        Returns:
            True if PDF appears to be scanned
        """
        if not self._pypdf_available:
            return True  # Assume scanned if we can't check
        
        import pypdf
        
        try:
            reader = pypdf.PdfReader(str(path))
            total_text = 0
            
            for page in reader.pages:
                text = page.extract_text() or ""
                total_text += len(text.strip())
            
            avg_text_per_page = total_text / max(len(reader.pages), 1)
            return avg_text_per_page < self.MIN_TEXT_PER_PAGE
            
        except Exception:
            return True
    
    def extract_images(self, path: str | Path) -> list[bytes]:
        """Extract all images from PDF.
        
        Args:
            path: Path to PDF file
            
        Returns:
            List of image bytes
        """
        if not self._pypdf_available:
            return []
        
        import pypdf
        
        images = []
        try:
            reader = pypdf.PdfReader(str(path))
            
            for page in reader.pages:
                if "/XObject" not in page.get("/Resources", {}):
                    continue
                    
                x_objects = page["/Resources"]["/XObject"].get_object()
                for obj in x_objects.values():
                    if obj.get("/Subtype") == "/Image":
                        try:
                            data = obj.get_data()
                            images.append(data)
                        except Exception:
                            pass
        except Exception:
            pass
        
        return images
