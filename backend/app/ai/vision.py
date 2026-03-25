"""Vision module for Jarvis/Ultron - Claude's vision capabilities.

This module provides image and document analysis using Claude's multimodal
capabilities. It supports screenshots, documents, and general image analysis.

Features:
- Screenshot analysis and UI understanding
- Document/PDF image analysis
- General image analysis with custom prompts
- Screen description for accessibility
"""

from __future__ import annotations

import base64
import io
import logging
import mimetypes
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from anthropic import AsyncAnthropic

from app.core.config import settings

logger = logging.getLogger(__name__)


# Supported image formats for Claude vision
SUPPORTED_IMAGE_TYPES = {
    "image/jpeg": "jpeg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}

# Maximum image size in bytes (20MB limit for Claude)
MAX_IMAGE_SIZE = 20 * 1024 * 1024


# ============ VISION TOOLS DEFINITIONS ============

VISION_TOOLS = [
    {
        "name": "analyze_image",
        "description": "Analyze any image using Claude's vision capabilities. Can describe contents, extract text, identify objects, analyze UI elements, and more. Supports JPEG, PNG, GIF, and WebP formats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_base64": {
                    "type": "string",
                    "description": "Base64 encoded image data (without data URL prefix)"
                },
                "image_url": {
                    "type": "string",
                    "description": "URL of the image to analyze (alternative to base64)"
                },
                "prompt": {
                    "type": "string",
                    "description": "What to analyze or look for in the image. Be specific about what information you need."
                },
                "media_type": {
                    "type": "string",
                    "enum": ["image/jpeg", "image/png", "image/gif", "image/webp"],
                    "description": "MIME type of the image (required for base64 images)"
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "analyze_screenshot",
        "description": "Take a screenshot of the current screen and analyze it. Useful for understanding what's on the user's screen, providing UI guidance, or troubleshooting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "What to analyze or look for in the screenshot. Default: describe what's visible on screen."
                },
                "display": {
                    "type": "integer",
                    "description": "Display number to capture (for multi-monitor setups). Default: main display."
                }
            },
            "required": []
        }
    },
    {
        "name": "analyze_document",
        "description": "Analyze an image of a document (scanned PDF page, photo of document, receipt, etc.). Extracts text, structure, and key information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the document image file"
                },
                "document_type": {
                    "type": "string",
                    "enum": ["receipt", "invoice", "form", "letter", "id_card", "business_card", "contract", "other"],
                    "description": "Type of document for optimized extraction"
                },
                "extract_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific fields to extract (e.g., ['total', 'date', 'vendor'] for receipts)"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "describe_screen",
        "description": "Take a screenshot and provide a comprehensive description of what's visible. Useful for accessibility, documentation, or understanding current context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "detail_level": {
                    "type": "string",
                    "enum": ["brief", "normal", "detailed"],
                    "description": "How detailed the description should be. Default: normal."
                },
                "focus_area": {
                    "type": "string",
                    "description": "Specific area or element to focus on (e.g., 'toolbar', 'main content', 'sidebar')"
                }
            },
            "required": []
        }
    },
    {
        "name": "compare_images",
        "description": "Compare two images and describe the differences. Useful for A/B testing, version comparison, or change detection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image1_base64": {
                    "type": "string",
                    "description": "Base64 encoded first image"
                },
                "image2_base64": {
                    "type": "string",
                    "description": "Base64 encoded second image"
                },
                "image1_path": {
                    "type": "string",
                    "description": "Path to first image (alternative to base64)"
                },
                "image2_path": {
                    "type": "string",
                    "description": "Path to second image (alternative to base64)"
                },
                "comparison_focus": {
                    "type": "string",
                    "description": "What aspects to compare (e.g., 'layout', 'colors', 'text content', 'UI elements')"
                }
            },
            "required": []
        }
    },
    {
        "name": "extract_text_from_image",
        "description": "Extract all text visible in an image using OCR-like capabilities. Returns structured text content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "image_base64": {
                    "type": "string",
                    "description": "Base64 encoded image data"
                },
                "image_path": {
                    "type": "string",
                    "description": "Path to the image file (alternative to base64)"
                },
                "media_type": {
                    "type": "string",
                    "enum": ["image/jpeg", "image/png", "image/gif", "image/webp"],
                    "description": "MIME type of the image"
                },
                "preserve_formatting": {
                    "type": "boolean",
                    "description": "Try to preserve the original text layout and formatting"
                }
            },
            "required": []
        }
    },
]


class VisionAnalyzer:
    """Handles image analysis using Claude's vision capabilities."""

    # Model with vision support
    VISION_MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 4096

    def __init__(self, client: Optional[AsyncAnthropic] = None):
        """Initialize the vision analyzer.

        Args:
            client: Optional Anthropic client. Creates one if not provided.
        """
        self.client = client or AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def analyze_image(
        self,
        image_data: Union[bytes, str],
        prompt: str,
        media_type: str = "image/png",
    ) -> Dict[str, Any]:
        """Analyze any image with a custom prompt.

        Args:
            image_data: Image as bytes or base64 string
            prompt: What to analyze in the image
            media_type: MIME type of the image

        Returns:
            Analysis result with description and extracted information
        """
        if media_type not in SUPPORTED_IMAGE_TYPES:
            return {
                "success": False,
                "error": f"Unsupported image type: {media_type}. Supported: {list(SUPPORTED_IMAGE_TYPES.keys())}"
            }

        # Convert bytes to base64 if needed
        if isinstance(image_data, bytes):
            if len(image_data) > MAX_IMAGE_SIZE:
                return {
                    "success": False,
                    "error": f"Image too large ({len(image_data)} bytes). Maximum: {MAX_IMAGE_SIZE} bytes"
                }
            image_base64 = base64.standard_b64encode(image_data).decode("utf-8")
        else:
            # Assume already base64 encoded
            image_base64 = image_data
            # Remove data URL prefix if present
            if image_base64.startswith("data:"):
                image_base64 = image_base64.split(",", 1)[1]

        try:
            response = await self.client.messages.create(
                model=self.VISION_MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_base64,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )

            # Extract text response
            analysis = ""
            for block in response.content:
                if block.type == "text":
                    analysis += block.text

            return {
                "success": True,
                "analysis": analysis,
                "model": self.VISION_MODEL,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            }

        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return {
                "success": False,
                "error": f"Analysis failed: {str(e)}"
            }

    async def analyze_image_url(
        self,
        image_url: str,
        prompt: str,
    ) -> Dict[str, Any]:
        """Analyze an image from a URL.

        Args:
            image_url: URL of the image to analyze
            prompt: What to analyze in the image

        Returns:
            Analysis result
        """
        try:
            response = await self.client.messages.create(
                model=self.VISION_MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "url",
                                    "url": image_url,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )

            analysis = ""
            for block in response.content:
                if block.type == "text":
                    analysis += block.text

            return {
                "success": True,
                "analysis": analysis,
                "model": self.VISION_MODEL,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            }

        except Exception as e:
            logger.error(f"Image URL analysis failed: {e}")
            return {
                "success": False,
                "error": f"Analysis failed: {str(e)}"
            }

    async def analyze_screenshot(
        self,
        prompt: Optional[str] = None,
        display: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Take and analyze a screenshot of the current screen.

        Args:
            prompt: What to look for (default: general description)
            display: Display number for multi-monitor setups

        Returns:
            Screenshot analysis result
        """
        # Take screenshot using platform-specific method
        screenshot_data = await self._capture_screenshot(display)

        if screenshot_data is None:
            return {
                "success": False,
                "error": "Failed to capture screenshot. Make sure screen capture is enabled."
            }

        # Default prompt if not provided
        if not prompt:
            prompt = (
                "Describe what's visible on this screen. Include:\n"
                "1. The main application or window visible\n"
                "2. Key UI elements and their state\n"
                "3. Any important text or information displayed\n"
                "4. The overall context of what the user might be doing"
            )

        return await self.analyze_image(
            image_data=screenshot_data,
            prompt=prompt,
            media_type="image/png",
        )

    async def analyze_document(
        self,
        file_path: str,
        document_type: str = "other",
        extract_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Analyze a document image and extract information.

        Args:
            file_path: Path to the document image
            document_type: Type of document for optimized extraction
            extract_fields: Specific fields to extract

        Returns:
            Document analysis with extracted data
        """
        path = Path(file_path).expanduser().resolve()

        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }

        # Determine media type
        media_type, _ = mimetypes.guess_type(str(path))
        if media_type not in SUPPORTED_IMAGE_TYPES:
            return {
                "success": False,
                "error": f"Unsupported file type: {media_type}"
            }

        # Read the file
        try:
            with open(path, "rb") as f:
                image_data = f.read()
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to read file: {str(e)}"
            }

        # Build extraction prompt based on document type
        prompt = self._build_document_prompt(document_type, extract_fields)

        result = await self.analyze_image(
            image_data=image_data,
            prompt=prompt,
            media_type=media_type,
        )

        if result["success"]:
            result["document_type"] = document_type
            result["file_path"] = str(path)

        return result

    async def describe_screen(
        self,
        detail_level: str = "normal",
        focus_area: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Provide a comprehensive screen description.

        Args:
            detail_level: How detailed (brief, normal, detailed)
            focus_area: Specific area to focus on

        Returns:
            Screen description
        """
        # Build appropriate prompt based on detail level
        if detail_level == "brief":
            prompt = (
                "Provide a brief, one-paragraph summary of what's visible on this screen. "
                "Focus on the main application and primary content."
            )
        elif detail_level == "detailed":
            prompt = (
                "Provide a detailed description of this screen, including:\n"
                "1. Application name and window title\n"
                "2. Menu bar and toolbar contents\n"
                "3. Main content area details\n"
                "4. Sidebar or panel contents\n"
                "5. Status bar information\n"
                "6. Any dialogs or popups\n"
                "7. Visible text content\n"
                "8. Color scheme and visual design\n"
                "9. Any notifications or alerts"
            )
        else:  # normal
            prompt = (
                "Describe what's on this screen:\n"
                "1. What application is open\n"
                "2. What the user appears to be doing\n"
                "3. Key information visible\n"
                "4. Any notable UI elements or state"
            )

        if focus_area:
            prompt += f"\n\nFocus especially on: {focus_area}"

        return await self.analyze_screenshot(prompt=prompt)

    async def compare_images(
        self,
        image1_data: Union[bytes, str],
        image2_data: Union[bytes, str],
        comparison_focus: Optional[str] = None,
        media_type: str = "image/png",
    ) -> Dict[str, Any]:
        """Compare two images and describe differences.

        Args:
            image1_data: First image as bytes or base64
            image2_data: Second image as bytes or base64
            comparison_focus: What aspects to compare
            media_type: MIME type of the images

        Returns:
            Comparison results
        """
        # Convert to base64 if needed
        def to_base64(data):
            if isinstance(data, bytes):
                return base64.standard_b64encode(data).decode("utf-8")
            if data.startswith("data:"):
                return data.split(",", 1)[1]
            return data

        image1_b64 = to_base64(image1_data)
        image2_b64 = to_base64(image2_data)

        prompt = "Compare these two images and describe:\n"
        prompt += "1. Key differences between them\n"
        prompt += "2. What has changed from the first to the second\n"
        prompt += "3. What remains the same\n"

        if comparison_focus:
            prompt += f"\nFocus specifically on: {comparison_focus}"

        try:
            response = await self.client.messages.create(
                model=self.VISION_MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "First image (before):",
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image1_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": "Second image (after):",
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image2_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            )

            analysis = ""
            for block in response.content:
                if block.type == "text":
                    analysis += block.text

            return {
                "success": True,
                "comparison": analysis,
                "model": self.VISION_MODEL,
            }

        except Exception as e:
            logger.error(f"Image comparison failed: {e}")
            return {
                "success": False,
                "error": f"Comparison failed: {str(e)}"
            }

    async def extract_text(
        self,
        image_data: Union[bytes, str],
        media_type: str = "image/png",
        preserve_formatting: bool = False,
    ) -> Dict[str, Any]:
        """Extract all text from an image.

        Args:
            image_data: Image as bytes or base64
            media_type: MIME type of the image
            preserve_formatting: Whether to preserve layout

        Returns:
            Extracted text content
        """
        if preserve_formatting:
            prompt = (
                "Extract all text visible in this image. "
                "Preserve the original layout, formatting, and structure as much as possible. "
                "Use appropriate spacing, line breaks, and indentation to match the original. "
                "If there are tables, recreate them using text formatting. "
                "Include any headers, labels, or UI text."
            )
        else:
            prompt = (
                "Extract all text visible in this image. "
                "List the text content in a clear, readable format. "
                "Group related text together and use appropriate labels if helpful. "
                "Include headers, body text, labels, buttons, and any other visible text."
            )

        result = await self.analyze_image(
            image_data=image_data,
            prompt=prompt,
            media_type=media_type,
        )

        if result["success"]:
            result["extracted_text"] = result.pop("analysis")

        return result

    # ============ Private Helper Methods ============

    async def _capture_screenshot(self, display: Optional[int] = None) -> Optional[bytes]:
        """Capture a screenshot using platform-specific methods.

        Args:
            display: Display number for multi-monitor setups

        Returns:
            Screenshot as PNG bytes, or None if failed
        """
        import platform

        system = platform.system()

        try:
            if system == "Darwin":  # macOS
                return await self._capture_screenshot_macos(display)
            elif system == "Linux":
                return await self._capture_screenshot_linux(display)
            elif system == "Windows":
                return await self._capture_screenshot_windows(display)
            else:
                logger.warning(f"Unsupported platform for screenshots: {system}")
                return None
        except Exception as e:
            logger.error(f"Screenshot capture failed: {e}")
            return None

    async def _capture_screenshot_macos(self, display: Optional[int] = None) -> Optional[bytes]:
        """Capture screenshot on macOS using screencapture."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            cmd = ["screencapture", "-x"]  # -x for silent (no sound)
            if display is not None:
                cmd.extend(["-D", str(display)])
            cmd.append(tmp_path)

            result = subprocess.run(cmd, capture_output=True, timeout=10)

            if result.returncode != 0:
                logger.error(f"screencapture failed: {result.stderr.decode()}")
                return None

            with open(tmp_path, "rb") as f:
                return f.read()

        finally:
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

    async def _capture_screenshot_linux(self, display: Optional[int] = None) -> Optional[bytes]:
        """Capture screenshot on Linux using various methods."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Try gnome-screenshot first
            result = subprocess.run(
                ["gnome-screenshot", "-f", tmp_path],
                capture_output=True,
                timeout=10
            )

            if result.returncode != 0:
                # Try scrot as fallback
                result = subprocess.run(
                    ["scrot", tmp_path],
                    capture_output=True,
                    timeout=10
                )

            if result.returncode != 0:
                # Try import (ImageMagick) as last resort
                result = subprocess.run(
                    ["import", "-window", "root", tmp_path],
                    capture_output=True,
                    timeout=10
                )

            if result.returncode != 0:
                logger.error("No screenshot tool available on Linux")
                return None

            with open(tmp_path, "rb") as f:
                return f.read()

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _capture_screenshot_windows(self, display: Optional[int] = None) -> Optional[bytes]:
        """Capture screenshot on Windows using PowerShell."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Use PowerShell to capture screen
            ps_script = f'''
            Add-Type -AssemblyName System.Windows.Forms
            $screen = [System.Windows.Forms.Screen]::PrimaryScreen
            $bitmap = New-Object System.Drawing.Bitmap($screen.Bounds.Width, $screen.Bounds.Height)
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $graphics.CopyFromScreen($screen.Bounds.Location, [System.Drawing.Point]::Empty, $screen.Bounds.Size)
            $bitmap.Save("{tmp_path}")
            '''

            result = subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.error(f"PowerShell screenshot failed: {result.stderr.decode()}")
                return None

            with open(tmp_path, "rb") as f:
                return f.read()

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _build_document_prompt(
        self,
        document_type: str,
        extract_fields: Optional[List[str]] = None,
    ) -> str:
        """Build an optimized prompt for document extraction.

        Args:
            document_type: Type of document
            extract_fields: Specific fields to extract

        Returns:
            Extraction prompt
        """
        base_prompts = {
            "receipt": (
                "Analyze this receipt and extract:\n"
                "1. Store/Merchant name\n"
                "2. Date and time\n"
                "3. All line items with prices\n"
                "4. Subtotal, tax, and total\n"
                "5. Payment method\n"
                "6. Any other relevant information"
            ),
            "invoice": (
                "Analyze this invoice and extract:\n"
                "1. Invoice number and date\n"
                "2. Sender/Company information\n"
                "3. Recipient/Bill-to information\n"
                "4. Line items with descriptions and amounts\n"
                "5. Subtotal, taxes, discounts, and total\n"
                "6. Payment terms and due date\n"
                "7. Bank/payment details if present"
            ),
            "form": (
                "Analyze this form and extract:\n"
                "1. Form title/type\n"
                "2. All field labels and their values\n"
                "3. Any checkboxes or selections\n"
                "4. Signatures if present\n"
                "5. Dates and reference numbers"
            ),
            "letter": (
                "Analyze this letter and extract:\n"
                "1. Sender information\n"
                "2. Recipient information\n"
                "3. Date\n"
                "4. Subject/reference\n"
                "5. Full body text\n"
                "6. Signature and signatory name"
            ),
            "id_card": (
                "Analyze this ID card and extract:\n"
                "1. Card type (driver's license, passport, etc.)\n"
                "2. Name\n"
                "3. Date of birth\n"
                "4. ID/License number\n"
                "5. Expiration date\n"
                "6. Address if present\n"
                "7. Any other visible information\n"
                "Note: Handle this data with privacy in mind."
            ),
            "business_card": (
                "Analyze this business card and extract:\n"
                "1. Name and title\n"
                "2. Company name\n"
                "3. Phone number(s)\n"
                "4. Email address\n"
                "5. Physical address\n"
                "6. Website\n"
                "7. Social media handles"
            ),
            "contract": (
                "Analyze this contract and extract:\n"
                "1. Contract title and type\n"
                "2. Parties involved\n"
                "3. Effective date and term\n"
                "4. Key terms and conditions\n"
                "5. Financial terms if applicable\n"
                "6. Signatures and dates"
            ),
            "other": (
                "Analyze this document and extract:\n"
                "1. Document type/title\n"
                "2. All visible text content\n"
                "3. Key information and data points\n"
                "4. Any tables or structured data\n"
                "5. Names, dates, and numbers\n"
                "6. Overall purpose of the document"
            ),
        }

        prompt = base_prompts.get(document_type, base_prompts["other"])

        if extract_fields:
            prompt += f"\n\nSpecifically, make sure to extract these fields: {', '.join(extract_fields)}"

        prompt += "\n\nProvide the extracted information in a clear, structured format."

        return prompt


# ============ Module-level convenience functions ============

# Singleton analyzer instance
_analyzer: Optional[VisionAnalyzer] = None


def get_vision_analyzer() -> VisionAnalyzer:
    """Get or create the singleton vision analyzer."""
    global _analyzer
    if _analyzer is None:
        _analyzer = VisionAnalyzer()
    return _analyzer


async def analyze_image(
    image_data: Union[bytes, str],
    prompt: str,
    media_type: str = "image/png",
) -> Dict[str, Any]:
    """Analyze any image with a custom prompt.

    Args:
        image_data: Image as bytes or base64 string
        prompt: What to analyze in the image
        media_type: MIME type of the image

    Returns:
        Analysis result
    """
    analyzer = get_vision_analyzer()
    return await analyzer.analyze_image(image_data, prompt, media_type)


async def analyze_screenshot(
    prompt: Optional[str] = None,
    display: Optional[int] = None,
) -> Dict[str, Any]:
    """Take and analyze a screenshot.

    Args:
        prompt: What to look for (default: general description)
        display: Display number for multi-monitor setups

    Returns:
        Screenshot analysis result
    """
    analyzer = get_vision_analyzer()
    return await analyzer.analyze_screenshot(prompt, display)


async def analyze_document(
    file_path: str,
    document_type: str = "other",
    extract_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Analyze a document image.

    Args:
        file_path: Path to the document image
        document_type: Type of document
        extract_fields: Specific fields to extract

    Returns:
        Document analysis with extracted data
    """
    analyzer = get_vision_analyzer()
    return await analyzer.analyze_document(file_path, document_type, extract_fields)


async def describe_screen(
    detail_level: str = "normal",
    focus_area: Optional[str] = None,
) -> Dict[str, Any]:
    """Describe what's currently visible on screen.

    Args:
        detail_level: How detailed (brief, normal, detailed)
        focus_area: Specific area to focus on

    Returns:
        Screen description
    """
    analyzer = get_vision_analyzer()
    return await analyzer.describe_screen(detail_level, focus_area)
