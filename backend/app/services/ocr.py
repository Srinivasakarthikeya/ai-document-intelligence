"""Text extraction: native PDF text first, Tesseract OCR as fallback for scans/images."""
from pathlib import Path

import pdfplumber
import pytesseract
from PIL import Image, ImageOps, ImageFilter

MIN_NATIVE_CHARS = 40  # below this per page, treat the PDF page as scanned


def _preprocess(img: Image.Image) -> Image.Image:
    """Grayscale + autocontrast + light sharpen + upscale small images — cheap wins for Tesseract."""
    img = ImageOps.grayscale(img)
    if img.width < 1500:
        scale = 1500 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    return img.filter(ImageFilter.SHARPEN)


def ocr_image(img: Image.Image) -> str:
    return pytesseract.image_to_string(_preprocess(img), config="--oem 3 --psm 6")


def extract_text(path: str | Path) -> tuple[str, str]:
    """Returns (text, method) where method is native | ocr | hybrid | plain."""
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".txt":
        return path.read_text(errors="ignore"), "plain"

    if ext == ".pdf":
        pages, used_ocr, used_native = [], False, False
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if len(text.strip()) >= MIN_NATIVE_CHARS:
                    pages.append(text)
                    used_native = True
                else:
                    img = page.to_image(resolution=300).original
                    pages.append(ocr_image(img))
                    used_ocr = True
        method = "hybrid" if used_ocr and used_native else ("ocr" if used_ocr else "native")
        return "\n\n".join(pages), method

    with Image.open(path) as img:
        return ocr_image(img), "ocr"
