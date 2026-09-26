"""Generate sample docs in ../samples: native PDF invoice, scanned-image invoice, receipt, PO, contract."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent.parent / "samples"
OUT.mkdir(exist_ok=True)

INVOICE = """TAX INVOICE
Nimbus Traders Pvt Ltd
GSTIN: 36ABCDE1234F1Z5
billing@nimbustraders.in  +91 98765 43210
Invoice No: INV-2041
Invoice Date: 12/08/2026
Due Date: 11/09/2026
Bill To: Orbit Tech Solutions
Description Qty Rate Amount
Laptop stand 2 1500.00 3000.00
Wireless mouse 4 750.00 3000.00
Cloud hosting 1 4000.00 4000.00
Subtotal: 10000.00
GST: 1800.00
Grand Total: Rs 11800.00"""

BAD_INVOICE = """INVOICE
Vertex Logistics
Invoice No: INV-3307
Invoice Date: 05/09/2026
Due Date: 01/09/2026
Bill To: Sunrise Foods
Freight charges 3 2000.00 6500.00
Subtotal: 6500.00
Tax: 1170.00
Total Amount Due: $ 7800.00"""

RECEIPT = """Sunrise Cafe
Sales Receipt
14 Sep 2026 09:42
Cashier: Meera
Filter coffee 2 60.00 120.00
Masala dosa 1 110.00 110.00
Total: 230.00
Paid by UPI
Thank you for your purchase!"""

PO = """PURCHASE ORDER
PO Number: PO-55120
Order Date: 2026-09-01
Vendor: Tata Supplies
Ship To: Orbit Tech Warehouse, Hyderabad
Office chair 10 4500.00 45000.00
A4 paper 20 250.00 5000.00
Total: 50000.00"""

CONTRACT = """SERVICE AGREEMENT
This Agreement is made between Orbit Tech Solutions (hereinafter "Client") and Nimbus Traders Pvt Ltd (hereinafter "Provider").
Effective Date: 01/10/2026
1. Term. This agreement shall have a term of 12 months.
2. Termination. Either party may terminate with 30 days written notice.
3. Governing Law. This agreement is governed by the laws of India.
IN WITNESS WHEREOF the parties have signed."""


def pdf(name, text):
    c = canvas.Canvas(str(OUT / name), pagesize=A4)
    y = 800
    for line in text.splitlines():
        c.drawString(50, y, line)
        y -= 18
    c.save()


FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",          # macOS
    "/Library/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",                             # Windows
    "DejaVuSans.ttf",                                         # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def load_font(size=28):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def png(name, text):
    font = load_font(28)
    lines = text.splitlines()
    img = Image.new("RGB", (1400, 60 + 44 * len(lines)), "white")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        d.text((40, 30 + 44 * i), line, fill="black", font=font)
    img = img.rotate(0.6, expand=True, fillcolor="white")  # slight skew like a scan
    img.save(OUT / name)


if __name__ == "__main__":
    pdf("invoice_native.pdf", INVOICE)
    png("invoice_scanned.png", INVOICE)
    pdf("invoice_with_errors.pdf", BAD_INVOICE)
    png("receipt_scanned.png", RECEIPT)
    pdf("purchase_order.pdf", PO)
    pdf("service_agreement.pdf", CONTRACT)
    print("Samples written to", OUT)
