"""
booking_tools.py
LangChain Tool Layer for Hotel Booking Management Assistant.
Implements the controlled API layer required by Hackathon Item 6 and Item 7:
- search_rooms
- check_availability
- create_booking
- get_booking
- list_customer_bookings
- cancel_booking (enforcing 24h cutoff rule)
- get_hotel_policy_info (PDF RAG integration)
"""
import json
from typing import Optional
from langchain_core.tools import tool
import hotel_db
import rag_hotel_policy


@tool
def search_rooms(
    city: Optional[str] = None,
    check_in_date: Optional[str] = None,
    check_out_date: Optional[str] = None,
    number_of_guests: int = 1,
    room_type: Optional[str] = None,
    max_price: Optional[float] = None,
) -> str:
    """
    Search for available hotel rooms across all hotels or in a specific city for given check-in and check-out dates.
    Dates must be in 'YYYY-MM-DD' format.
    Checks real-time availability and excludes rooms with conflicting bookings or inactive status.
    """
    try:
        results = hotel_db.search_rooms(
            city=city,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            number_of_guests=number_of_guests,
            room_type=room_type,
            max_price=max_price,
        )
        location_desc = f"in {city}" if city else "across all hotels"
        date_desc = f" ({check_in_date} to {check_out_date})" if (check_in_date and check_out_date) else ""
        if not results:
            return f"No rooms available {location_desc} for {number_of_guests} guest(s){date_desc}. Please refer to our website for other information."

        lines = [f"Found {len(results)} available room(s) {location_desc}{date_desc}:"]
        for r in results:
            city_str = f", {r.get('city')}" if r.get('city') else ""
            lines.append(
                f"- Hotel: {r['hotel_name']}{city_str} (Hotel ID: {r['hotel_id']}) | "
                f"Room {r['room_number']} (Room ID: {r['room_id']}) - {r['room_type']} | "
                f"Capacity: {r['capacity']} guests | Price: Rs. {r['price_per_night']:.2f}/night | "
                f"Amenities: {r['amenities']}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching rooms: {str(e)}"


@tool
def check_room_availability(
    room_id: int,
    check_in_date: str,
    check_out_date: str,
) -> str:
    """
    Check if a specific room (by room_id) is available for dates (YYYY-MM-DD).
    Verifies room is active and does not have overlapping confirmed bookings.
    """
    try:
        res = hotel_db.check_room_availability(
            room_id=room_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
        )
        if res["available"]:
            return (
                f"Room ID {room_id} ({res['room_type']} at {res['hotel_name']}) is AVAILABLE "
                f"from {check_in_date} to {check_out_date}. Rate: Rs. {res['price_per_night']:.2f}/night."
            )
        else:
            return f"Room ID {room_id} is NOT available: {res['reason']}"
    except Exception as e:
        return f"Error checking availability: {str(e)}"


@tool
def create_booking(
    customer_id: int,
    hotel_id: int,
    room_id: int,
    check_in_date: str,
    check_out_date: str,
    number_of_guests: int = 1,
) -> str:
    """
    Creates and confirms a hotel booking for a customer.
    Dates must be in 'YYYY-MM-DD' format.
    Calculates total cost, prevents overlapping bookings, and assigns a confirmed Booking ID.
    """
    try:
        res = hotel_db.create_booking(
            customer_id=customer_id,
            hotel_id=hotel_id,
            room_id=room_id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            number_of_guests=number_of_guests,
        )
        if res["success"]:
            return (
                f"Booking CONFIRMED successfully!\n"
                f"- Booking ID: {res['booking_id']}\n"
                f"- Hotel: {res['hotel_name']} (Hotel ID: {res['hotel_id']})\n"
                f"- Room: #{res['room_number']} ({res['room_type']}, Room ID: {res['room_id']})\n"
                f"- Dates: {res['check_in_date']} to {res['check_out_date']} ({res['nights']} night(s))\n"
                f"- Guests: {res['number_of_guests']}\n"
                f"- Total Amount: Rs. {res['total_amount']:.2f}\n"
                f"- Status: {res['booking_status']}\n"
                f"- Booking Time: {res['booking_date']}"
            )
        else:
            return f"Failed to create booking: {res['error']}"
    except Exception as e:
        return f"Error creating booking: {str(e)}"


@tool
def get_booking_details(booking_id: str) -> str:
    """
    Retrieve current details and status for a specific booking ID (e.g. 'BK-1001').
    """
    try:
        b = hotel_db.get_booking(booking_id)
        if not b:
            return f"Booking '{booking_id}' was not found in the records. Please refer to our website for other information."
        return (
            f"Booking Details for {b['booking_id']}:\n"
            f"- Customer: {b['customer_name']} (ID: {b['customer_id']})\n"
            f"- Hotel: {b['hotel_name']}, {b['city']}\n"
            f"- Room: #{b['room_number']} ({b['room_type']})\n"
            f"- Check-in: {b['check_in_date']} | Check-out: {b['check_out_date']}\n"
            f"- Guests: {b['number_of_guests']}\n"
            f"- Total Amount: Rs. {b['total_amount']:.2f}\n"
            f"- Status: {b['booking_status']}\n"
            f"- Booked On: {b['booking_date']}"
        )
    except Exception as e:
        return f"Error retrieving booking: {str(e)}"


@tool
def list_customer_bookings(customer_id: int) -> str:
    """
    List all past, upcoming, and cancelled bookings for a customer by customer_id.
    """
    try:
        bookings = hotel_db.list_customer_bookings(customer_id)
        if not bookings:
            return f"No bookings found for customer ID {customer_id}."
        lines = [f"Found {len(bookings)} booking(s) for Customer ID {customer_id}:"]
        for b in bookings:
            lines.append(
                f"- [{b['booking_status']}] Booking ID: {b['booking_id']} | "
                f"Hotel: {b['hotel_name']} ({b['city']}) | Room: #{b['room_number']} ({b['room_type']}) | "
                f"Dates: {b['check_in_date']} to {b['check_out_date']} | Amount: Rs. {b['total_amount']:.2f}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing customer bookings: {str(e)}"


@tool
def cancel_booking(booking_id: str, customer_id: Optional[int] = None) -> str:
    """
    Cancel an existing hotel booking or submit a cancellation request.
    Enforces the 24-hour rule:
    - Direct cancellation if more than 24 hours prior to check-in.
    - If within 24 hours of check-in, submits a formal cancellation request for review.
    """
    try:
        res = hotel_db.cancel_booking(booking_id=booking_id, customer_id=customer_id)
        if res["success"]:
            return f"Result: {res['message']}"
        else:
            return f"Cancellation could not be processed: {res['error']}"
    except Exception as e:
        return f"Error cancelling booking: {str(e)}"


@tool
def get_hotel_policy_info(question: str, hotel_id: Optional[int] = None) -> str:
    """
    Answers questions regarding hotel policies, check-in/out times, Wi-Fi, dining,
    parking, cancellation fees, and amenities strictly from official PDF documents.
    If hotel_id is specified (1 for Mumbai Grand Palace, 2 for Delhi Royal Orchid), retrieves that hotel's policy.
    """
    try:
        return rag_hotel_policy.answer_policy_question(query=question, hotel_id=hotel_id)
    except Exception as e:
        return f"Error consulting hotel policy: {str(e)}"


@tool
def get_hotel_contact_info(hotel_name_or_city: Optional[str] = None) -> str:
    """
    Retrieves the official front desk phone number, email address, and physical location
    for hotel properties (Grand Palace Hotel Mumbai, Royal Orchid Residency Delhi, Silicon Oasis Suites Bangalore).
    """
    try:
        hotels = hotel_db.get_hotel_contact_info(city_or_name=hotel_name_or_city)
        if not hotels:
            return "No contact records found for the requested hotel. Please refer to our website for other information."
        lines = ["Official Hotel Front Desk & Contact Directory:"]
        for h in hotels:
            lines.append(
                f"- {h['name']} ({h['city']}):\n"
                f"  - Phone: {h['contact_number']}\n"
                f"  - Email: {h['email']}\n"
                f"  - Address: {h['address']}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error retrieving contact info: {str(e)}"


@tool
def remember_user_preference(key: str, value: str, customer_id: int = 3) -> str:
    """
    Saves a persistent personal fact, preference, dietary need, or favorite item for the user
    (e.g., key="room preference", value="high floor", or key="bed preference", value="king size").
    This information is permanently remembered across new chats and sessions via Mem0.
    """
    try:
        from hotel_memory import memory_manager
        memory_manager.save_preference(key=key, value=value, customer_id=customer_id)
        return f"Successfully saved memory: {key} = {value}. I will remember this across all chats!"
    except Exception as e:
        return f"Error saving memory: {str(e)}"


@tool
def get_user_memories(customer_id: int = 3) -> str:
    """
    Retrieves all persistent memories, preferences, and personal details saved for the user via Mem0.
    """
    try:
        from hotel_memory import memory_manager
        profile = memory_manager.get_guest_profile_prompt(customer_id=customer_id)
        return f"Stored Guest Memories & Preferences (Mem0):\n{profile}"
    except Exception as e:
        return f"Error retrieving memories: {str(e)}"


ALL_TOOLS = [
    search_rooms,
    check_room_availability,
    create_booking,
    get_booking_details,
    list_customer_bookings,
    cancel_booking,
    get_hotel_policy_info,
    get_hotel_contact_info,
    remember_user_preference,
    get_user_memories,
]

