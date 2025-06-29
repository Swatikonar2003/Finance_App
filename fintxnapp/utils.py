from io import BytesIO
from datetime import datetime
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
import os
from django.core.mail import EmailMessage
from django.conf import settings


#--------------PDF generation functions--------------#

ICON_PATH = os.path.join(os.path.dirname(__file__), "icons")

def draw_icon(p, name, x, y, size=14):
    """Draws a small icon left of a section header."""
    icon_file = os.path.join(ICON_PATH, f"{name}.png")
    if os.path.exists(icon_file):
        p.drawImage(ImageReader(icon_file), x - size - 5, y - 4, width=size, height=size, mask='auto')

def generate_monthly_report_pdf(data):
    # Creates an in-memory binary stream to hold the PDF content.
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - inch

    # Logo
    logo_path = os.path.join(ICON_PATH, "logofin.png")
    if os.path.exists(logo_path):
        logo_width = 1.5 * inch
        logo_height = 0.6 * inch 
        p.drawImage(
            ImageReader(logo_path),
            width - logo_width - 0.5 * inch,  
            height - logo_height - 0.3 * inch,  
            width=logo_width,
            height=logo_height,
            preserveAspectRatio=True,
            mask='auto'
        )

    # Report Title
    p.setFont("Helvetica-Bold", 16)
    p.drawString(inch, y, "📊 Monthly Financial Report")
    y -= 25
    p.setFont("Helvetica", 11)
    p.drawString(inch, y, f"Month: {data['month']}")
    y -= 15
    p.drawString(inch, y, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 30

    # --- Summary Header ---
    def section(title):
        nonlocal y
        p.setFillColorRGB(0.9, 0.9, 0.9)
        p.rect(inch, y, width - 2 * inch, 20, fill=1)
        p.setFillColorRGB(0, 0, 0)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(inch + 10, y + 5, title)
        y -= 25

    def two_column(label, value):
        nonlocal y
        p.setFont("Helvetica", 10)
        p.drawString(inch, y, label)
        p.drawRightString(width - inch, y, str(value))
        y -= 15

    # --- Summary Section ---
    section("Summary")
    two_column("Total Credit", f"₹{data['total_credit']}")
    two_column("Total Debit", f"₹{data['total_debit']}")
    two_column("Balance", f"₹{data['balance']}")
    two_column("Transaction Count", data['transaction_count'])
    two_column("Avg Transaction Amount", f"₹{data['avg_transaction_amount']}")
    two_column("Savings Rate", f"{data['savings_rate']}%")
    y -= 10

    # --- Top Categories ---
    section("Top Categories")
    two_column("Top 3", ", ".join(data['top_categories']) or "N/A")
    y -= 10

    # --- Top Tags ---
    section("Top Tags")
    two_column("Top 3", ", ".join(data['top_tags']) or "N/A")
    y -= 10

    # --- Transactions ---
    section("Transactions")
    p.setFont("Helvetica-Bold", 10)
    p.drawString(inch, y, "Date")
    p.drawString(inch + 70, y, "Type")
    p.drawString(inch + 140, y, "Amount")
    p.drawString(inch + 220, y, "Category")
    p.drawString(inch + 350, y, "Tags")
    y -= 10
    p.line(inch, y, width - inch, y)
    y -= 12

    # --- Transaction Rows ---
    row_num = 0
    page_num = 1
    for txn in data["transactions"]:
        row_height = 16  # consistent height for all rows
        
        # Start a new page if nearing the bottom
        if y < inch + 40:
            # Footer and page number before new page
            p.setFont("Helvetica", 9)
            p.drawCentredString(width / 2, 0.5 * inch, f"Page {page_num}")
            p.drawString(inch, 0.5 * inch, "Powered by Trackmint")
            p.showPage()
            page_num += 1
            y = height - inch
            section("📄 Continued Transactions")
            # Redraw table headers
            p.setFont("Helvetica-Bold", 10)
            p.drawString(inch, y, "Date")
            p.drawString(inch + 70, y, "Type")
            p.drawString(inch + 140, y, "Amount")
            p.drawString(inch + 220, y, "Category")
            p.drawString(inch + 320, y, "Tags")
            y -= 10
            p.line(inch, y, width - inch, y)
            y -= row_height

        # Alternate row shading
        if row_num % 2 == 1:
            p.setFillColorRGB(0.95, 0.96, 1)  # light blueish gray
            p.rect(inch - 2, y - 2, width - 2 * inch + 4, 16, fill=1, stroke=0)
            p.setFillColorRGB(0, 0, 0)  # Reset to black text

        # Set font
        p.setFont("Helvetica", 9)

        # Draw transaction fields
        p.drawString(inch, y, txn['date'])
        p.drawString(inch + 70, y, txn['transaction_type'].capitalize())
        p.drawString(inch + 140, y, f"₹{txn['amount']}")
        p.drawString(inch + 220, y, txn['category'] or "-")
        p.drawString(inch + 320, y, ", ".join(txn['tags']))
        
        y -= row_height
        row_num += 1

    # Final page footer
    p.setFont("Helvetica", 9)
    p.drawCentredString(width / 2, 0.5 * inch, f"Page {page_num}")
    p.drawString(inch, 0.5 * inch, "Powered by Trackmint")
    p.save()
    buffer.seek(0)
    return buffer

#--------------email monthly report function--------------#
def send_monthly_report_email(user, month_str, pdf_buffer):
    subject = f"Your Monthly Finance Report - {month_str}"
    body = f"""
Hi {user.username},

Attached is your financial report for {month_str} 📊.

Thanks for using Trackmint!
"""
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email]
    )
    email.attach(f"report_{month_str}.pdf", pdf_buffer.read(), 'application/pdf')
    email.send()