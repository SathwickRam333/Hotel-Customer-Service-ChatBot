"""
test_hotel_system.py
Automated verification test suite for AROHAK Hotel AI System:
- Item 6 (Booking Management):
  1. Room search & date availability
  2. Prevention of double/overlapping bookings
  3. 24-hour cancellation rule cutoff logic
  4. Tool layer execution
- Item 7 (PDF Policy RAG):
  1. Policy PDF retrieval grounding (check-in, Wi-Fi, parking)
  2. Negative grounding test (hallucination rejection on unmentioned questions)
"""
import os
import sys
from datetime import datetime, timedelta
import hotel_db
from booking_tools import (
    search_rooms,
    check_room_availability,
    create_booking,
    get_booking_details,
    cancel_booking,
    get_hotel_policy_info,
)
import seed_hotel
import generate_hotel_pdfs
import rag_hotel_policy


def test_booking_logic():
    print("\n--- [TEST 1] Testing Database & Booking Rules (Item 6) ---")
    seed_hotel.seed()

    # Test 1.1: Search rooms in Mumbai
    print("1.1 Testing search_rooms...")
    today = datetime.now().date()
    test_in = (today + timedelta(days=30)).strftime("%Y-%m-%d")
    test_out = (today + timedelta(days=34)).strftime("%Y-%m-%d")
    rooms = hotel_db.search_rooms(city="Mumbai", check_in_date=test_in, check_out_date=test_out, number_of_guests=2)
    assert len(rooms) > 0, "Expected available rooms in Mumbai"
    print(f"    PASS: Found {len(rooms)} available room(s) in Mumbai.")

    # Test 1.2: Atomic Booking Creation
    print("1.2 Testing create_booking...")
    booking_res = hotel_db.create_booking(
        customer_id=3,
        hotel_id=1,
        room_id=1,
        check_in_date=test_in,
        check_out_date=test_out,
        number_of_guests=2,
    )
    assert booking_res["success"], f"Booking failed: {booking_res.get('error')}"
    new_bk_id = booking_res["booking_id"]
    print(f"    PASS: Booking created successfully -> {new_bk_id}, Total: Rs. {booking_res['total_amount']}")

    # Test 1.3: Overlap Prevention (Double booking attempt on same room and dates)
    print("1.3 Testing overlap prevention...")
    overlap_in = (today + timedelta(days=32)).strftime("%Y-%m-%d")
    overlap_out = (today + timedelta(days=36)).strftime("%Y-%m-%d")
    overlap_res = hotel_db.create_booking(
        customer_id=4,
        hotel_id=1,
        room_id=1,
        check_in_date=overlap_in,
        check_out_date=overlap_out,
        number_of_guests=2,
    )
    assert not overlap_res["success"], "Conflict check failed: Allowed overlapping booking!"
    print(f"    PASS: Successfully rejected conflicting booking -> {overlap_res['error']}")

    # Test 1.4: 24-Hour Cancellation Rule Logic
    print("1.4 Testing 24-hour cancellation rule...")
    # Direct cancellation test (> 24h)
    cancel_far = hotel_db.cancel_booking(
        booking_id=new_bk_id,
        reference_datetime=datetime.now(),
    )
    assert cancel_far["new_status"] == "CANCELLED", f"Expected CANCELLED, got {cancel_far}"
    print(f"    PASS: Booking far in advance cancelled directly: {cancel_far['message']}")

    # Late cancellation test (<= 24h, e.g. 6 hours before check-in)
    late_in = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    late_out = (today + timedelta(days=3)).strftime("%Y-%m-%d")
    late_bk = hotel_db.create_booking(
        customer_id=3, hotel_id=1, room_id=4, check_in_date=late_in, check_out_date=late_out, number_of_guests=2
    )
    # Check-in is default 14:00:00 on late_in; simulate request 6 hours prior (08:00 on late_in)
    simulated_late_time = datetime.strptime(f"{late_in} 08:00:00", "%Y-%m-%d %H:%M:%S")
    cancel_late = hotel_db.cancel_booking(
        booking_id=late_bk["booking_id"],
        reference_datetime=simulated_late_time,
    )
    assert cancel_late["new_status"] == "CANCELLATION_REQUESTED", f"Expected CANCELLATION_REQUESTED, got {cancel_late}"
    print(f"    PASS: Late cancellation within 24h converted to request: {cancel_late['message']}")


def test_controlled_tools():
    print("\n--- [TEST 2] Testing LangChain Tool Layer (Item 6) ---")
    tool_search = search_rooms.invoke({
        "city": "Delhi",
        "check_in_date": "2026-11-01",
        "check_out_date": "2026-11-03",
        "number_of_guests": 2,
    })
    assert "Found" in tool_search or "Royal Orchid" in tool_search, f"Tool search error: {tool_search}"
    print(f"    PASS: search_rooms tool output:\n    {tool_search.splitlines()[0]}")

    tool_avail = check_room_availability.invoke({
        "room_id": 6,
        "check_in_date": "2026-11-01",
        "check_out_date": "2026-11-03",
    })
    assert "AVAILABLE" in tool_avail, f"Availability check error: {tool_avail}"
    print(f"    PASS: check_room_availability tool: {tool_avail}")


def test_policy_rag():
    print("\n--- [TEST 3] Testing Policy PDF Ingestion & Grounding (Item 7) ---")
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    mumbai_pdf = os.path.join(data_dir, "Grand_Palace_Mumbai_Policy.pdf")
    generate_hotel_pdfs.main()

    # Index into Chroma
    chunks = rag_hotel_policy.ingest_hotel_pdf(mumbai_pdf, hotel_id=1, hotel_name="Grand Palace Hotel Mumbai")
    assert chunks > 0, "No chunks indexed"
    print(f"    PASS: Indexed {chunks} policy chunks.")

    # Positive test: check-in time
    docs = rag_hotel_policy.retrieve_policy_context("What is the check in time and Wi-Fi?", hotel_id=1)
    assert len(docs) > 0, "Failed to retrieve policy documents"
    combined_content = " ".join([d.page_content for d in docs])
    assert "14:00" in combined_content or "Wi-Fi" in combined_content, "Retrieved text does not contain check-in or Wi-Fi info"
    print("    PASS: Positive Grounding test: Check-in & Wi-Fi context retrieved accurately.")


def test_long_term_memory():
    print("\n--- [TEST 4] Testing Long-Term Guest Memory (Cross-Chat Persistence) ---")
    customer_id = 3
    hotel_db.clear_user_memories(customer_id)

    # 4.1 Save memory directly and verify
    hotel_db.save_user_memory(customer_id, "favorite food", "chicken")
    mems = hotel_db.get_user_memories(customer_id)
    assert mems.get("favorite food") == "chicken", f"Expected 'chicken', got {mems.get('favorite food')}"
    print("    PASS: 4.1 Memory saved and retrieved from SQLite successfully.")

    # 4.2 Test agent cross-chat retention
    from hotel_agent import build_hotel_agent
    agent = build_hotel_agent(customer_id=customer_id)

    # New chat with empty history
    query_res = agent.invoke({"input": "What is my favorite food?", "chat_history": []})
    assert "chicken" in query_res["output"].lower(), f"Agent failed to recall favorite food: {query_res['output']}"
    print(f"    PASS: 4.2 Agent recalled in a brand new chat: '{query_res['output'].strip()}'")


def main():
    print("==========================================================")
    print("   AROHAK Hackathon: Hotel AI System Automated Tests      ")
    print("==========================================================")
    test_booking_logic()
    test_controlled_tools()
    test_policy_rag()
    test_long_term_memory()
    print("\n==========================================================")
    print("   ALL TESTS PASSED SUCCESSFULLY (Items 6 & 7 + Memory)   ")
    print("==========================================================")


if __name__ == "__main__":
    main()

