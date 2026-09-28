"""
generate_hotel_pdfs.py
Generates sample Hotel Policy & Information PDFs for:
1. Grand Palace Hotel (Mumbai) - hotel_id: 1
2. Royal Orchid Residency (Delhi) - hotel_id: 2

Includes clear sections:
- Check-in & Check-out Policies
- Cancellation & Refund Policy (24-hour cutoff rule)
- Wi-Fi & Internet Connectivity
- Dining & Complimentary Breakfast Timings
- Parking Facilities & Valet Service
- Amenities & House Rules
- FAQs and Contact Guidelines
"""
import os
from fpdf import FPDF


class HotelPolicyPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 10, self.title_str, border=False, align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 5, self.subtitle_str, border=False, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()} | Official Guest Policy Document", align="C")

    def chapter_title(self, title):
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(230, 240, 255)
        self.cell(0, 8, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def chapter_body(self, body):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 6, body)
        self.ln(4)


def create_mumbai_pdf(output_path: str):
    pdf = HotelPolicyPDF()
    pdf.title_str = "Grand Palace Hotel, Mumbai - Guest Policy & Guidelines"
    pdf.subtitle_str = "Colaba Causeway, Mumbai, Maharashtra | Contact: reservations.mumbai@grandpalace.com"
    pdf.add_page()

    pdf.chapter_title("1. Check-in and Check-out Rules")
    pdf.chapter_body(
        "Standard check-in time is 14:00 (2:00 PM) IST. "
        "Standard check-out time is 11:00 AM IST.\n"
        "Early check-in from 10:00 AM is subject to room availability upon arrival. "
        "Late check-out up to 2:00 PM is complimentary for Executive Suite guests upon prior request at reception. "
        "Valid government-issued photo ID (Passport, Aadhar Card, Voter ID, or Driving License) is mandatory for all adult guests at check-in."
    )

    pdf.chapter_title("2. Cancellation and Refund Policy")
    pdf.chapter_body(
        "Free direct cancellation is permitted up to 24 hours prior to standard check-in (14:00 on the arrival date). "
        "Full refund will be processed within 5-7 business days to the original payment method.\n"
        "If cancelled within 24 hours of check-in, direct automatic cancellation is disabled. Guests must submit a formal Cancellation Request "
        "via the portal or customer care. Late cancellations are subject to a fee equal to one night's room rate."
    )

    pdf.chapter_title("3. Wi-Fi and Connectivity")
    pdf.chapter_body(
        "Complimentary high-speed Wi-Fi (up to 100 Mbps) is available throughout the hotel property, including all guest rooms, lobby, and dining areas.\n"
        "Network Name (SSID): GrandPalace_Guest\n"
        "Login Process: Select room number and enter guest last name on the splash portal."
    )

    pdf.chapter_title("4. Dining & Breakfast Timings")
    pdf.chapter_body(
        "Complimentary buffet breakfast is served at 'The Spice Route' restaurant on the 1st floor from 07:00 AM to 10:30 AM daily.\n"
        "24-hour in-room dining is available by dialing extension 4 from your room telephone."
    )

    pdf.chapter_title("5. Parking Facilities")
    pdf.chapter_body(
        "Complimentary valet parking and secure basement car parking is available 24/7 for all registered hotel guests.\n"
        "Electric Vehicle (EV) fast-charging stations (Type 2 and CCS) are installed on Basement Level 2 and accessible free of charge."
    )

    pdf.chapter_title("6. Swimming Pool, Gym, and Spa Guidelines")
    pdf.chapter_body(
        "Infinity rooftop swimming pool is open from 06:00 AM to 09:00 PM. Proper swimwear is strictly required.\n"
        "The Fitness Center is open 24/7 for guest use with room keycard access.\n"
        "Ayurvedic Spa treatments are available from 09:00 AM to 08:00 PM by prior reservation."
    )

    pdf.chapter_title("7. House Rules & Pet Policy")
    pdf.chapter_body(
        "Grand Palace Hotel maintains a strict 100% smoke-free indoor environment. Designated smoking zones are located near the exterior garden.\n"
        "Pets are not allowed on the hotel premises, with the sole exception of certified guide/service dogs.\n"
        "Quiet hours are enforced from 10:00 PM to 07:00 AM."
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pdf.output(output_path)
    print(f"Generated Mumbai Hotel Policy PDF: {output_path}")


def create_delhi_pdf(output_path: str):
    pdf = HotelPolicyPDF()
    pdf.title_str = "Royal Orchid Residency, Delhi - Guest Policy & Directory"
    pdf.subtitle_str = "Connaught Place, Barakhamba Road, New Delhi | Contact: booking.delhi@royalorchid.com"
    pdf.add_page()

    pdf.chapter_title("1. Check-in and Check-out Rules")
    pdf.chapter_body(
        "Check-in time starts at 13:00 (1:00 PM) IST. "
        "Check-out time is strictly 12:00 PM (Noon) IST.\n"
        "Express check-in and luggage drop-off are available 24 hours at the concierge desk."
    )

    pdf.chapter_title("2. Cancellation Policy")
    pdf.chapter_body(
        "Direct cancellations are permitted up to 24 hours prior to the arrival date.\n"
        "Cancellations requested inside the 24-hour window must be submitted as a formal request to front desk management. "
        "Non-refundable promotional rates are not eligible for direct cancellation."
    )

    pdf.chapter_title("3. Wi-Fi & Business Center")
    pdf.chapter_body(
        "High-speed fiber Wi-Fi is complimentary for all guests.\n"
        "Network SSID: RoyalOrchid_CP\n"
        "Password: Provided on the keycard sleeve upon check-in.\n"
        "The 24-hour Business Center on the Mezzanine floor provides printing, scanning, and private conference booths."
    )

    pdf.chapter_title("4. Parking & Airport Shuttle")
    pdf.chapter_body(
        "Dedicated on-site parking is available for guests at Rs. 200 per day. Valet parking is available at the main porch.\n"
        "Airport pick-up and drop-off to Indira Gandhi International Airport (Terminal 1 & Terminal 3) is available upon request at Rs. 1,200 per sedan."
    )

    pdf.chapter_title("5. Dining & Room Service")
    pdf.chapter_body(
        "Breakfast is served from 06:30 AM to 10:00 AM at 'Dawat' multi-cuisine restaurant.\n"
        "Room service operates until 11:30 PM."
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pdf.output(output_path)
    print(f"Generated Delhi Hotel Policy PDF: {output_path}")


def main():
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    mumbai_pdf = os.path.join(data_dir, "Grand_Palace_Mumbai_Policy.pdf")
    delhi_pdf = os.path.join(data_dir, "Royal_Orchid_Delhi_Policy.pdf")

    create_mumbai_pdf(mumbai_pdf)
    create_delhi_pdf(delhi_pdf)


if __name__ == "__main__":
    main()
