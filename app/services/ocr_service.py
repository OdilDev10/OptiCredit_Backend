"""OCR service for voucher image processing using PaddleOCR."""

import asyncio
import logging
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

try:
    from paddleocr import PaddleOCR
except Exception as exc:  # pragma: no cover - import error path depends on host env
    PaddleOCR = Any  # type: ignore[misc,assignment]
    _paddle_import_error = exc
else:
    _paddle_import_error = None

from app.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

# Global OCR engine (initialized in lifespan)
ocr_engine: Optional[PaddleOCR] = None
ocr_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ocr_worker")


def initialize_ocr():
    """Initialize PaddleOCR engine (called in app lifespan)."""
    global ocr_engine
    if PaddleOCR is Any:
        raise RuntimeError(
            "OCR is required but PaddleOCR dependencies are not available. "
            f"Import error: {_paddle_import_error}"
        )

    logger.info("Initializing PaddleOCR engine...")
    ocr_engine = PaddleOCR(
        use_angle_cls=settings.ocr_use_angle_cls,
        lang=settings.ocr_lang,
    )
    logger.info("PaddleOCR initialized successfully")


def _extract_amount_dominican(text: str) -> Optional[Decimal]:
    """
    Extract monetary amount from Dominican voucher text.
    Looks for patterns like: $1,000.00, RD$ 1,000.00, etc.
    """
    # Common Dominican currency patterns
    patterns = [
        r"RD?\s*\$?\s*([\d,]+\.?\d*)",  # RD$ 1,000.00 or $ 1,000.00
        r"\$([\d,]+\.?\d*)",  # $1,000.00
        r"([\d,]+\.\d{2})",  # 1,000.00 (numeric pattern)
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Take the largest amount found (likely the transaction amount)
            amounts = []
            for match in matches:
                try:
                    # Remove commas and convert to Decimal
                    clean = match.replace(",", "")
                    amount = Decimal(clean)
                    if amount > 0:
                        amounts.append(amount)
                except:
                    continue
            if amounts:
                return max(amounts)

    return None


def _extract_date_dominican(text: str) -> Optional[datetime]:
    """
    Extract date from Dominican voucher text.
    Looks for patterns like: DD/MM/YYYY, DD-MM-YYYY, etc.
    """
    patterns = [
        r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",  # DD/MM/YYYY or DD-MM-YYYY
        r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",  # YYYY/MM/DD
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            for match in matches:
                try:
                    # Try DD/MM/YYYY first
                    day, month, year = int(match[0]), int(match[1]), int(match[2])
                    if day > 31 or month > 12:
                        # Try reversing for YYYY/MM/DD format
                        day, month, year = int(match[2]), int(match[1]), int(match[0])
                    if 1 <= day <= 31 and 1 <= month <= 12:
                        return datetime(year, month, day)
                except ValueError:
                    continue

    return None


def _extract_bank_reference(text: str) -> Optional[str]:
    """Extract bank transaction reference or authorization code."""
    # Common Dominican bank reference patterns
    patterns = [
        r"(?:ref|referencia|reference|autorizaci[ó]n|authorization|code)[:\s]+([A-Z0-9]{6,20})",
        r"#([A-Z0-9]{6,20})",  # # followed by code
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return matches[0]

    return None


def _process_ocr_result(image_path: str) -> dict:
    """Process image through PaddleOCR (runs in ThreadPoolExecutor)."""
    global ocr_engine

    if ocr_engine is None:
        raise AppException("OCR engine not initialized", code="OCR_NOT_READY")

    try:
        # Run OCR
        result = ocr_engine.ocr(image_path, cls=True)

        # Extract text from OCR result
        extracted_text = ""
        confidence_scores = []

        if result:
            for line in result:
                if line:
                    for word_info in line:
                        text = word_info[1]
                        confidence = word_info[2]
                        extracted_text += text + " "
                        confidence_scores.append(confidence)

        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0

        return {
            "raw_text": extracted_text.strip(),
            "confidence": float(avg_confidence),
            "raw_result": result,
        }
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        raise AppException(f"OCR processing failed: {str(e)}", code="OCR_PROCESS_ERROR")


async def process_voucher_image(image_path: str) -> dict:
    """
    Process voucher image asynchronously using PaddleOCR in ThreadPoolExecutor.
    Returns extracted payment data.
    """
    loop = asyncio.get_event_loop()

    try:
        # Run OCR in thread pool to avoid blocking
        ocr_result = await loop.run_in_executor(ocr_executor, _process_ocr_result, image_path)

        raw_text = ocr_result["raw_text"]
        confidence = ocr_result["confidence"]

        # Extract payment data
        amount = _extract_amount_dominican(raw_text)
        transaction_date = _extract_date_dominican(raw_text)
        bank_reference = _extract_bank_reference(raw_text)

        extraction_status = "success" if amount and transaction_date else "partial"
        if not amount and not transaction_date:
            extraction_status = "failed"

        return {
            "status": extraction_status,
            "raw_text": raw_text,
            "confidence": confidence,
            "extracted_data": {
                "amount": float(amount) if amount else None,
                "transaction_date": transaction_date.isoformat() if transaction_date else None,
                "bank_reference": bank_reference,
            },
            "processed_at": datetime.now().isoformat(),
        }
    except AppException:
        raise
    except Exception as e:
        logger.exception("Unexpected error in voucher processing")
        raise AppException(f"Voucher processing failed: {str(e)}", code="VOUCHER_PROCESS_ERROR")


def close_ocr():
    """Clean up OCR resources (called in app shutdown)."""
    global ocr_engine
    if ocr_executor:
        ocr_executor.shutdown(wait=True)
    logger.info("OCR engine shut down")


class OCRService:
    """Backward-compatible wrapper around the current OCR helpers."""

    async def extract_from_image(self, file_content: bytes) -> dict:
        """Process an uploaded image buffer and normalize the OCR payload."""
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                temp_file.write(file_content)
                temp_path = temp_file.name

            result = await process_voucher_image(temp_path)
            extracted = result.get("extracted_data", {})

            return {
                "extracted_text": result.get("raw_text"),
                "detected_amount": extracted.get("amount"),
                "detected_currency": "DOP" if extracted.get("amount") is not None else None,
                "detected_date": extracted.get("transaction_date"),
                "detected_reference": extracted.get("bank_reference"),
                "detected_bank_name": None,
                "confidence_score": result.get("confidence", 0.0),
                "appears_to_be_receipt": bool(result.get("raw_text")),
                "validation_summary": result.get("status"),
                "status": result.get("status", "failed"),
            }
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
