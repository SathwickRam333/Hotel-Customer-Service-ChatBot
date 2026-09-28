"""
seed_hotel.py
Populates hotel_booking.db with initial sample data:
- Users (Admin, Receptionist, Customers)
- Hotels (Mumbai, Delhi, Bangalore)
- Rooms (Standard, Deluxe, Executive Suite)
- Sample Bookings (for testing overlap checks & cancellation rules)
"""
import os
from datetime import datetime, timedelta
from hotel_db import init_db, get_connection, DB_PATH


def seed():
    # Remove existing DB for clean initialization
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print(f"Removed existing database at {DB_PATH}")
        except Exception:
            pass

    init_db(DB_PATH)
    conn = get_connection(DB_PATH)
    cur = conn.cursor()

    # 1. Seed Users
    users = [
        ("Hotel Admin", "admin@arohak.com", "admin123", "Admin"),
        ("Mumbai Receptionist", "frontdesk.mumbai@arohak.com", "recep123", "Receptionist"),
        ("Rahul Sharma", "rahul@example.com", "rahul123", "Customer"),
        ("Priya Patel", "priya@example.com", "priya123", "Customer"),
        ("Amit Verma", "amit@example.com", "amit123", "Customer"),
    ]
    cur.executemany("""
    INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)
    """, users)
    print(f"Seeded {len(users)} users.")

    # 2. Seed Hotels
    hotels = [
        (1, "ORG-1", "Grand Palace Hotel", "Colaba Causeway, Near Gateway of India", "Mumbai", "+91 22 6665 3366", "reservations.mumbai@grandpalace.com", "Active"),
        (2, "ORG-1", "Royal Orchid Residency", "Connaught Place, Barakhamba Road", "Delhi", "+91 11 4151 1234", "booking.delhi@royalorchid.com", "Active"),
        (3, "ORG-1", "Silicon Oasis Suites", "Indiranagar 100ft Road", "Bangalore", "+91 80 4055 8899", "stay@siliconoasis.com", "Active"),
    ]
    cur.executemany("""
    INSERT INTO hotels (hotel_id, organization_id, name, address, city, contact_number, email, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, hotels)
    print(f"Seeded {len(hotels)} hotels.")

    # 3. Seed Rooms
    # Room types: Standard Room, Deluxe Room, Executive Suite
    rooms = [
        # Mumbai - Grand Palace Hotel (hotel_id=1)
        (1, 1, "101", "Deluxe Room", 2, 4500.0, "Active", "Spacious room with king bed and city view", "Free Wi-Fi, King Bed, AC, Smart TV, Mini-bar, Coffee Maker"),
        (2, 1, "102", "Deluxe Room", 2, 4500.0, "Active", "Deluxe room with balcony and garden view", "Free Wi-Fi, King Bed, AC, Balcony, Safe, Tea Maker"),
        (3, 1, "201", "Executive Suite", 4, 8500.0, "Active", "Luxury suite with panoramic Arabian Sea view", "High-speed Wi-Fi, 2 King Beds, AC, Jacuzzi, Sea View, Lounge Access"),
        (4, 1, "202", "Standard Room", 2, 3200.0, "Active", "Cozy standard room for business travelers", "Free Wi-Fi, Queen Bed, AC, Work Desk"),
        (5, 1, "301", "Presidential Suite", 4, 15000.0, "Inactive", "Under annual renovation", "Private Terrace, Butler Service, Ocean View"),

        # Delhi - Royal Orchid Residency (hotel_id=2)
        (6, 2, "101", "Standard Room", 1, 2800.0, "Active", "Single executive room near Connaught Place", "Free Wi-Fi, Single Bed, AC, Work Desk"),
        (7, 2, "102", "Deluxe Room", 2, 4200.0, "Active", "Elegant deluxe room with modern heritage décor", "Free Wi-Fi, Queen Bed, AC, City View, Breakfast Included"),
        (8, 2, "201", "Executive Suite", 3, 7200.0, "Active", "Premium suite with separate living area", "High-speed Wi-Fi, King Bed + Sofa, AC, Bathtub, Airport Transfer"),

        # Bangalore - Silicon Oasis Suites (hotel_id=3)
        (9, 3, "101", "Studio Apartment", 2, 3800.0, "Active", "Modern studio with kitchenette", "High-speed Wi-Fi, Queen Bed, Kitchenette, AC, Work Desk"),
        (10, 3, "102", "Executive Suite", 3, 6500.0, "Active", "Tech-enabled suite in prime Indiranagar", "Ultra-fast Wi-Fi, Smart Home Controls, King Bed, AC, Coffee Station"),
    ]
    cur.executemany("""
    INSERT INTO rooms (room_id, hotel_id, room_number, room_type, capacity, price_per_night, availability_status, description, amenities)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rooms)
    print(f"Seeded {len(rooms)} rooms.")

    # 4. Seed Existing Bookings
    today = datetime.now().date()
    far_in = (today + timedelta(days=15)).strftime("%Y-%m-%d")
    far_out = (today + timedelta(days=18)).strftime("%Y-%m-%d")

    tomorrow_in = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_out = (today + timedelta(days=3)).strftime("%Y-%m-%d")

    bookings = [
        # Booking far in future (eligible for direct cancellation)
        ("BK-1001", 3, "ORG-1", 1, 1, far_in, far_out, 2, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 13500.0, "CONFIRMED"),
        # Booking imminent tomorrow (within 24 hours, tests cancellation request rule)
        ("BK-1002", 3, "ORG-1", 1, 2, tomorrow_in, tomorrow_out, 2, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 9000.0, "CONFIRMED"),
        # Booking in Delhi
        ("BK-1003", 4, "ORG-1", 2, 7, far_in, far_out, 2, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 12600.0, "CONFIRMED"),
    ]
    cur.executemany("""
    INSERT INTO bookings (booking_id, customer_id, organization_id, hotel_id, room_id, check_in_date, check_out_date, number_of_guests, booking_date, total_amount, booking_status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, bookings)
    print(f"Seeded {len(bookings)} sample bookings.")

    conn.commit()
    conn.close()
    print("Database seeding completed successfully.")


if __name__ == "__main__":
    seed()
