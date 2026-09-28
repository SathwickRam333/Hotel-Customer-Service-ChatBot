"""
hotel_db.py
Database schema and transactional operations for Hotel Booking System.
Supports:
- User roles (Customer, Admin, Receptionist)
- Multi-hotel & room management
- Concurrency-safe room booking with date overlap checks
- Cancellation policy evaluation (24-hour cutoff rule)
"""
import sqlite3
import os
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "hotel_booking.db")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str = DB_PATH):
    conn = get_connection(db_path)
    cur = conn.cursor()

    # 1. Users / Customers table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('Admin', 'Receptionist', 'Customer'))
    )
    """)

    # 2. Hotels table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS hotels (
        hotel_id INTEGER PRIMARY KEY AUTOINCREMENT,
        organization_id TEXT DEFAULT 'ORG-1',
        name TEXT NOT NULL,
        address TEXT NOT NULL,
        city TEXT NOT NULL,
        contact_number TEXT,
        email TEXT,
        status TEXT DEFAULT 'Active' CHECK(status IN ('Active', 'Inactive'))
    )
    """)

    # 3. Rooms table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        room_id INTEGER PRIMARY KEY AUTOINCREMENT,
        hotel_id INTEGER NOT NULL,
        room_number TEXT NOT NULL,
        room_type TEXT NOT NULL,
        capacity INTEGER NOT NULL,
        price_per_night REAL NOT NULL,
        availability_status TEXT DEFAULT 'Active' CHECK(availability_status IN ('Active', 'Inactive')),
        description TEXT,
        amenities TEXT,
        FOREIGN KEY (hotel_id) REFERENCES hotels (hotel_id) ON DELETE CASCADE,
        UNIQUE(hotel_id, room_number)
    )
    """)

    # 4. Bookings table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        booking_id TEXT PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        organization_id TEXT DEFAULT 'ORG-1',
        hotel_id INTEGER NOT NULL,
        room_id INTEGER NOT NULL,
        check_in_date TEXT NOT NULL,
        check_out_date TEXT NOT NULL,
        number_of_guests INTEGER NOT NULL,
        booking_date TEXT NOT NULL,
        total_amount REAL NOT NULL,
        booking_status TEXT NOT NULL CHECK(booking_status IN ('CONFIRMED', 'CANCELLED', 'CANCELLATION_REQUESTED', 'COMPLETED')),
        FOREIGN KEY (customer_id) REFERENCES users (user_id),
        FOREIGN KEY (hotel_id) REFERENCES hotels (hotel_id),
        FOREIGN KEY (room_id) REFERENCES rooms (room_id)
    )
    """)

    # 5. Long-term User Memory table (persists user facts/preferences across chats)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_memories (
        memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        memory_key TEXT NOT NULL,
        memory_value TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES users (user_id),
        UNIQUE(customer_id, memory_key)
    )
    """)

    conn.commit()
    conn.close()


def _parse_date(d_str: str) -> date:
    """Parses date string in YYYY-MM-DD format."""
    return datetime.strptime(d_str.strip(), "%Y-%m-%d").date()


def get_hotel_contact_info(
    hotel_id: Optional[int] = None,
    city_or_name: Optional[str] = None,
    db_path: str = DB_PATH,
) -> List[Dict[str, Any]]:
    """
    Retrieves official contact information (front desk phone, email, address) for hotels.
    """
    conn = get_connection(db_path)
    cur = conn.cursor()
    query = "SELECT hotel_id, name, city, address, contact_number, email FROM hotels WHERE status = 'Active'"
    params: List[Any] = []
    if hotel_id:
        query += " AND hotel_id = ?"
        params.append(hotel_id)
    elif city_or_name:
        query += " AND (LOWER(city) LIKE ? OR LOWER(name) LIKE ?)"
        term = f"%{city_or_name.strip().lower()}%"
        params.extend([term, term])
    query += " ORDER BY hotel_id"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_rooms(
    city: Optional[str] = None,
    check_in_date: Optional[str] = None,
    check_out_date: Optional[str] = None,
    number_of_guests: int = 1,
    room_type: Optional[str] = None,
    max_price: Optional[float] = None,
    hotel_id: Optional[int] = None,
    db_path: str = DB_PATH,
) -> List[Dict[str, Any]]:
    """
    Search active rooms matching city, capacity, and availability across dates.
    Ensures rooms with overlapping confirmed bookings are excluded.
    """
    conn = get_connection(db_path)
    cur = conn.cursor()

    query = """
    SELECT r.room_id, r.hotel_id, h.name as hotel_name, h.city, h.address,
           r.room_number, r.room_type, r.capacity, r.price_per_night,
           r.description, r.amenities, r.availability_status
    FROM rooms r
    JOIN hotels h ON r.hotel_id = h.hotel_id
    WHERE r.availability_status = 'Active'
      AND h.status = 'Active'
      AND r.capacity >= ?
    """
    params: List[Any] = [number_of_guests]

    if city:
        query += " AND LOWER(h.city) LIKE ?"
        params.append(f"%{city.strip().lower()}%")

    if hotel_id:
        query += " AND r.hotel_id = ?"
        params.append(hotel_id)

    if room_type:
        query += " AND LOWER(r.room_type) LIKE ?"
        params.append(f"%{room_type.strip().lower()}%")

    if max_price:
        query += " AND r.price_per_night <= ?"
        params.append(max_price)

    # Filter out rooms with conflicting confirmed bookings if dates provided
    if check_in_date and check_out_date:
        query += """
        AND r.room_id NOT IN (
            SELECT b.room_id FROM bookings b
            WHERE b.booking_status = 'CONFIRMED'
              AND NOT (b.check_out_date <= ? OR b.check_in_date >= ?)
        )
        """
        params.extend([check_in_date.strip(), check_out_date.strip()])

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def check_room_availability(
    room_id: int,
    check_in_date: str,
    check_out_date: str,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Checks if a specific room is available for given dates.
    """
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute("""
    SELECT r.*, h.name as hotel_name, h.city
    FROM rooms r
    JOIN hotels h ON r.hotel_id = h.hotel_id
    WHERE r.room_id = ?
    """, (room_id,))
    room = cur.fetchone()

    if not room:
        conn.close()
        return {"available": False, "reason": f"Room ID {room_id} does not exist."}

    if room["availability_status"] != "Active":
        conn.close()
        return {"available": False, "reason": f"Room {room['room_number']} is currently inactive/under maintenance."}

    # Overlap check
    cur.execute("""
    SELECT booking_id, check_in_date, check_out_date
    FROM bookings
    WHERE room_id = ?
      AND booking_status = 'CONFIRMED'
      AND NOT (check_out_date <= ? OR check_in_date >= ?)
    """, (room_id, check_in_date.strip(), check_out_date.strip()))
    conflict = cur.fetchone()
    conn.close()

    if conflict:
        return {
            "available": False,
            "reason": f"Room is already booked from {conflict['check_in_date']} to {conflict['check_out_date']} (Booking: {conflict['booking_id']})."
        }

    return {
        "available": True,
        "room_id": room["room_id"],
        "hotel_id": room["hotel_id"],
        "hotel_name": room["hotel_name"],
        "room_number": room["room_number"],
        "room_type": room["room_type"],
        "price_per_night": room["price_per_night"],
        "capacity": room["capacity"],
    }


def get_rooms_with_availability(
    check_in_date: str,
    check_out_date: str,
    db_path: str = DB_PATH,
) -> List[Dict[str, Any]]:
    """
    Returns all rooms annotated with their live availability status for the given dates,
    explicitly embedding the evaluated check-in and check-out dates and existing reservation dates.
    """
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    SELECT r.room_id,
           h.name as hotel_name,
           r.room_number,
           r.room_type,
           ? as check_in_date,
           ? as check_out_date,
           CASE 
               WHEN r.availability_status != 'Active' THEN '⚪ INACTIVE (Maintenance)'
               WHEN EXISTS (
                   SELECT 1 FROM bookings b 
                   WHERE b.room_id = r.room_id 
                     AND b.booking_status = 'CONFIRMED'
                     AND NOT (b.check_out_date <= ? OR b.check_in_date >= ?)
               ) THEN '🔴 BOOKED (Conflict)'
               ELSE '🟢 AVAILABLE'
           END as availability_status,
           COALESCE(
               (
                   SELECT GROUP_CONCAT(b.check_in_date || ' to ' || b.check_out_date || ' (' || b.booking_id || ')', '; ')
                   FROM bookings b
                   WHERE b.room_id = r.room_id AND b.booking_status = 'CONFIRMED'
               ),
               'None (Open All Dates)'
           ) as confirmed_booked_dates,
           r.price_per_night,
           r.capacity,
           r.amenities
    FROM rooms r
    JOIN hotels h ON r.hotel_id = h.hotel_id
    ORDER BY r.hotel_id, r.room_number
    """, (check_in_date.strip(), check_out_date.strip(), check_in_date.strip(), check_out_date.strip()))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_booking(
    customer_id: int,
    hotel_id: int,
    room_id: int,
    check_in_date: str,
    check_out_date: str,
    number_of_guests: int,
    organization_id: str = "ORG-1",
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Creates a new booking with transactional locking and validation.
    Calculates total price based on number of nights.
    """
    d_in = _parse_date(check_in_date)
    d_out = _parse_date(check_out_date)

    if d_out <= d_in:
        return {"success": False, "error": "Check-out date must be strictly after check-in date."}

    nights = (d_out - d_in).days

    conn = get_connection(db_path)
    cur = conn.cursor()

    try:
        # Atomic check inside transaction
        cur.execute("BEGIN IMMEDIATE")

        cur.execute("""
        SELECT r.price_per_night, r.capacity, r.availability_status, h.name as hotel_name, r.room_number, r.room_type
        FROM rooms r
        JOIN hotels h ON r.hotel_id = h.hotel_id
        WHERE r.room_id = ? AND r.hotel_id = ?
        """, (room_id, hotel_id))
        room = cur.fetchone()

        if not room:
            conn.rollback()
            return {"success": False, "error": "Room not found in specified hotel."}

        if room["availability_status"] != "Active":
            conn.rollback()
            return {"success": False, "error": "Cannot book an inactive room."}

        if number_of_guests > room["capacity"]:
            conn.rollback()
            return {"success": False, "error": f"Room capacity is {room['capacity']}, but {number_of_guests} guests requested."}

        # Check conflicting bookings
        cur.execute("""
        SELECT booking_id FROM bookings
        WHERE room_id = ?
          AND booking_status = 'CONFIRMED'
          AND NOT (check_out_date <= ? OR check_in_date >= ?)
        """, (room_id, check_in_date.strip(), check_out_date.strip()))
        conflict = cur.fetchone()

        if conflict:
            conn.rollback()
            return {"success": False, "error": f"Room already booked by another reservation ({conflict['booking_id']}) for these dates."}

        # Generate Booking ID
        cur.execute("SELECT COUNT(*) FROM bookings")
        cnt = cur.fetchone()[0] + 1
        booking_id = f"BK-{cnt:04d}"

        total_amount = nights * room["price_per_night"]
        booking_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
        INSERT INTO bookings (
            booking_id, customer_id, organization_id, hotel_id, room_id,
            check_in_date, check_out_date, number_of_guests, booking_date,
            total_amount, booking_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED')
        """, (
            booking_id, customer_id, organization_id, hotel_id, room_id,
            check_in_date.strip(), check_out_date.strip(), number_of_guests,
            booking_date, total_amount
        ))

        conn.commit()

        return {
            "success": True,
            "booking_id": booking_id,
            "customer_id": customer_id,
            "hotel_id": hotel_id,
            "hotel_name": room["hotel_name"],
            "room_id": room_id,
            "room_number": room["room_number"],
            "room_type": room["room_type"],
            "check_in_date": check_in_date.strip(),
            "check_out_date": check_out_date.strip(),
            "nights": nights,
            "number_of_guests": number_of_guests,
            "total_amount": total_amount,
            "booking_status": "CONFIRMED",
            "booking_date": booking_date,
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_booking(booking_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieves full details of a specific booking."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    SELECT b.*, u.name as customer_name, u.email as customer_email,
           h.name as hotel_name, h.city, h.address as hotel_address,
           r.room_number, r.room_type, r.price_per_night
    FROM bookings b
    JOIN users u ON b.customer_id = u.user_id
    JOIN hotels h ON b.hotel_id = h.hotel_id
    JOIN rooms r ON b.room_id = r.room_id
    WHERE b.booking_id = ?
    """, (booking_id.strip(),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_customer_bookings(customer_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Lists all bookings for a given customer."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    SELECT b.*, h.name as hotel_name, h.city, r.room_number, r.room_type
    FROM bookings b
    JOIN hotels h ON b.hotel_id = h.hotel_id
    JOIN rooms r ON b.room_id = r.room_id
    WHERE b.customer_id = ?
    ORDER BY b.check_in_date DESC
    """, (customer_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cancel_booking(
    booking_id: str,
    customer_id: Optional[int] = None,
    reference_datetime: Optional[datetime] = None,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Evaluates 24-hour cancellation rule:
    - If > 24 hours / 1 day before check-in date (check-in at 14:00 standard or 00:00 date):
      Immediate direct cancellation -> status 'CANCELLED'.
    - If <= 24 hours before check-in date:
      Customer must submit cancellation request -> status 'CANCELLATION_REQUESTED'.
    """
    b = get_booking(booking_id, db_path=db_path)
    if not b:
        return {"success": False, "error": f"Booking {booking_id} not found."}

    if customer_id and b["customer_id"] != customer_id:
        return {"success": False, "error": "Unauthorized: This booking belongs to another customer."}

    if b["booking_status"] in ("CANCELLED", "CANCELLATION_REQUESTED"):
        return {
            "success": False,
            "error": f"Booking {booking_id} is already in status '{b['booking_status']}'."
        }

    now = reference_datetime or datetime.now()
    # Check-in timestamp: check_in_date at 14:00 (standard hotel check-in)
    check_in_dt = datetime.strptime(f"{b['check_in_date']} 14:00:00", "%Y-%m-%d %H:%M:%S")

    hours_remaining = (check_in_dt - now).total_seconds() / 3600.0

    conn = get_connection(db_path)
    cur = conn.cursor()

    if hours_remaining > 24.0:
        new_status = "CANCELLED"
        message = (
            f"Booking {booking_id} was successfully CANCELLED. "
            f"Direct cancellation permitted as request is {hours_remaining:.1f} hours prior to check-in."
        )
    else:
        new_status = "CANCELLATION_REQUESTED"
        message = (
            f"Direct cancellation deadline passed (less than 24 hours before check-in). "
            f"A Cancellation Request has been submitted to hotel management (Status: CANCELLATION_REQUESTED)."
        )

    cur.execute("""
    UPDATE bookings
    SET booking_status = ?
    WHERE booking_id = ?
    """, (new_status, booking_id))
    conn.commit()
    conn.close()

    return {
        "success": True,
        "booking_id": booking_id,
        "new_status": new_status,
        "hours_before_checkin": round(hours_remaining, 1),
        "message": message,
    }


# =====================================================================
# LONG-TERM USER MEMORY & PREFERENCE MANAGEMENT
# =====================================================================

def save_user_memory(customer_id: int, key: str, value: str, db_path: str = DB_PATH) -> bool:
    """
    Saves or updates a permanent personal detail, favorite item, or preference for a user.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO user_memories (customer_id, memory_key, memory_value, updated_at)
    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(customer_id, memory_key)
    DO UPDATE SET memory_value = excluded.memory_value, updated_at = CURRENT_TIMESTAMP
    """, (customer_id, key.strip().lower(), value.strip()))
    conn.commit()
    conn.close()
    return True


def get_user_memories(customer_id: int, db_path: str = DB_PATH) -> Dict[str, str]:
    """
    Retrieves all persistent long-term memories and preferences for a customer.
    """
    init_db(db_path)
    conn = get_connection(db_path)
    cur = conn.cursor()
    rows = cur.execute("""
    SELECT memory_key, memory_value
    FROM user_memories
    WHERE customer_id = ?
    ORDER BY updated_at ASC
    """, (customer_id,)).fetchall()
    conn.close()
    return {row["memory_key"]: row["memory_value"] for row in rows}


def delete_user_memory(customer_id: int, key: str, db_path: str = DB_PATH) -> bool:
    """
    Deletes a specific remembered key for a customer.
    """
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    DELETE FROM user_memories
    WHERE customer_id = ? AND memory_key = ?
    """, (customer_id, key.strip().lower()))
    conn.commit()
    conn.close()
    return True


def clear_user_memories(customer_id: int, db_path: str = DB_PATH) -> bool:
    """
    Clears all stored memories for a customer.
    """
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    DELETE FROM user_memories
    WHERE customer_id = ?
    """, (customer_id,))
    conn.commit()
    conn.close()
    return True
