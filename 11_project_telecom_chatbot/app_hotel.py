"""
app_hotel.py
Streamlit Web Application for AROHAK Hotel Booking AI Assistant.
Implements:
- Item 6: AI Chatbot - Booking Management (20 Marks)
- Item 7: AI Chatbot - RAG Based on PDF (17 Marks)
"""
import os
import streamlit as st
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

import hotel_db
import rag_hotel_policy
from hotel_agent import build_hotel_agent
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

st.set_page_config(
    page_title="AROHAK AI Concierge | Hotel Booking & Policy RAG",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished, premium hotel concierge styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: #F8FAFC;
        margin-bottom: 1.5rem;
        border: 1px solid #334155;
    }
    .main-header h1 {
        color: #F8FAFC;
        font-size: 2rem;
        margin-bottom: 0.2rem;
    }
    .stChatMessage {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "customer_id" not in st.session_state:
    st.session_state.customer_id = 3  # Default to Rahul Sharma
if "selected_hotel_id" not in st.session_state:
    st.session_state.selected_hotel_id = 1
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# Sidebar: Controls, Hackathon Badges, and Live Setup
with st.sidebar:
    st.markdown("### 🏨 AROHAK Concierge")
    st.divider()

    # Customer Persona Switcher
    st.markdown("#### 👤 Active Customer")
    customer_options = {
        3: "Rahul Sharma (ID: 3, Existing Bookings: BK-1001, BK-1002)",
        4: "Priya Patel (ID: 4, Existing Booking: BK-1003)",
        5: "Amit Verma (ID: 5, New Customer)",
    }
    selected_cid = st.selectbox(
        "Simulate Logged-in User:",
        options=list(customer_options.keys()),
        format_func=lambda x: customer_options[x],
        index=0,
    )
    st.session_state.customer_id = selected_cid

    st.divider()

    # Hotel Focus
    st.markdown("#### 📍 Focused Hotel (for Policy RAG)")
    hotel_options = {
        1: "Grand Palace Hotel (Mumbai)",
        2: "Royal Orchid Residency (Delhi)",
        3: "Silicon Oasis Suites (Bangalore)",
    }
    st.session_state.selected_hotel_id = st.selectbox(
        "Target Hotel:",
        options=list(hotel_options.keys()),
        format_func=lambda x: hotel_options[x],
        index=0,
    )

    st.divider()

    # One-click Database Reset & Seed
    st.markdown("#### ⚙️ Data Initialization")
    col_seed, col_pdf = st.columns(2)
    with col_seed:
        if st.button("🌱 Reset & Seed DB", use_container_width=True):
            import seed_hotel
            seed_hotel.seed()
            st.success("Database re-seeded!")
            st.rerun()

    with col_pdf:
        if st.button("📄 Generate PDFs", use_container_width=True):
            import generate_hotel_pdfs
            generate_hotel_pdfs.main()
            st.success("Policy PDFs generated!")
            st.rerun()

    # Upload Custom Hotel Policy PDF
    st.markdown("#### 📤 Upload New Hotel Policy PDF")
    uploaded_pdf = st.file_uploader("Upload policy document (.pdf)", type=["pdf"])
    if uploaded_pdf is not None:
        if st.button("Index Uploaded PDF into RAG", use_container_width=True):
            save_dir = os.path.join(os.path.dirname(__file__), "data", "uploads")
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, uploaded_pdf.name)
            with open(save_path, "wb") as f:
                f.write(uploaded_pdf.getbuffer())
            n_chunks = rag_hotel_policy.ingest_hotel_pdf(
                save_path,
                hotel_id=st.session_state.selected_hotel_id,
                hotel_name=hotel_options[st.session_state.selected_hotel_id],
            )
            st.success(f"Indexed {n_chunks} chunks into ChromaDB!")

    st.divider()
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.rerun()


# Header Banner
st.markdown("""
<div class="main-header">
    <h1>🏨 AROHAK Concierge AI</h1>
    <p>AI-Powered Hotel Booking Engine & Strictly Grounded Policy RAG Assistant</p>
</div>
""", unsafe_allow_html=True)


# Tabs: Chat Assistant vs Live Database Inspection
tab_chat, tab_db, tab_policy = st.tabs(["💬 AI Concierge Chat", "📊 Live Database Records", "📜 Hotel Policies & Vector Store"])

with tab_chat:
    # Quick Sample Queries matching Hackathon Requirements
    st.markdown("**Sample Actions & Testing Queries:**")
    q_col1, q_col2, q_col3 = st.columns(3)
    with q_col1:
        if st.button("🔍 Search Mumbai (Sept 20-23, 2 guests)", use_container_width=True):
            st.session_state.pending_prompt = "I need a room in Mumbai for 2 people from 2026-09-20 to 2026-09-23."
        if st.button("📅 Show my current reservations", use_container_width=True):
            st.session_state.pending_prompt = "Can you show all my upcoming and past bookings?"

    with q_col2:
        if st.button("🛎️ Check-in time & Wi-Fi at Grand Palace", use_container_width=True):
            st.session_state.pending_prompt = "What is the check-in time and Wi-Fi policy at Grand Palace Hotel Mumbai?"
        if st.button("🚗 Parking & EV Charging in Mumbai", use_container_width=True):
            st.session_state.pending_prompt = "Is parking available at Grand Palace Mumbai, and do you have EV charging?"

    with q_col3:
        if st.button("❌ Cancel BK-1001 (>24h rule check)", use_container_width=True):
            st.session_state.pending_prompt = "Please cancel my booking BK-1001."
        if st.button("❓ Test Hallucination Rejection (Helicopter)", use_container_width=True):
            st.session_state.pending_prompt = "Does Grand Palace Hotel have a helicopter landing pad for guests?"

    st.divider()

    # Render Conversation Messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Handle user input
    user_input = st.chat_input("Ask about room availability, bookings, cancellation, or hotel policies…")
    if st.session_state.pending_prompt:
        user_input = st.session_state.pending_prompt
        st.session_state.pending_prompt = None

    if user_input:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Build Agent for current customer
        with st.chat_message("assistant"):
            agent_executor = build_hotel_agent(customer_id=st.session_state.customer_id)
            with st.spinner("AI Concierge is processing your request via backend tools..."):
                try:
                    response = agent_executor.invoke({
                        "input": user_input,
                        "chat_history": st.session_state.chat_history,
                    })
                    output_text = response.get("output", "")

                    st.markdown(output_text)

                    # Update history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": output_text,
                    })
                    st.session_state.chat_history.append(HumanMessage(content=user_input))
                    st.session_state.chat_history.append(AIMessage(content=output_text))

                except Exception as e:
                    err_msg = f"⚠️ An error occurred: {str(e)}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})


with tab_db:
    st.subheader("📊 Live SQLite Database Viewer (`hotel_booking.db`)")
    st.caption("Inspect live tables to verify real-time updates from AI bookings and cancellations.")

    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown("#### 📑 Bookings Table")
        conn = hotel_db.get_connection()
        bookings_df = conn.execute("""
        SELECT b.booking_id, u.name as customer, h.name as hotel, r.room_number,
               b.check_in_date, b.check_out_date, b.number_of_guests,
               b.total_amount, b.booking_status, b.booking_date
        FROM bookings b
        JOIN users u ON b.customer_id = u.user_id
        JOIN hotels h ON b.hotel_id = h.hotel_id
        JOIN rooms r ON b.room_id = r.room_id
        ORDER BY b.booking_date DESC
        """).fetchall()
        if bookings_df:
            import pandas as pd
            df = pd.DataFrame([dict(row) for row in bookings_df])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No bookings recorded.")

    with col2:
        st.markdown("#### 🏨 Hotels")
        hotels_df = conn.execute("SELECT hotel_id, name, city, contact_number, status FROM hotels").fetchall()
        if hotels_df:
            import pandas as pd
            st.dataframe(pd.DataFrame([dict(r) for r in hotels_df]), use_container_width=True)

    st.divider()
    st.markdown("#### 🛏️ Rooms & Live Availability")
    st.caption("Check real-time availability across specific dates, or view all confirmed reservation dates.")

    # Date Range Selector for Live Availability Checking
    d_col1, d_col2 = st.columns(2)
    with d_col1:
        check_in = st.date_input("Check-in Date:", value=date.today() + timedelta(days=1))
    with d_col2:
        check_out = st.date_input("Check-out Date:", value=date.today() + timedelta(days=4))

    s_in = check_in.strftime("%Y-%m-%d")
    s_out = check_out.strftime("%Y-%m-%d")

    rooms_list = hotel_db.get_rooms_with_availability(s_in, s_out)
    if rooms_list:
        import pandas as pd
        st.dataframe(pd.DataFrame(rooms_list), use_container_width=True)

    # Detailed schedule of all reserved dates per room
    st.markdown("##### 📅 Confirmed Room Booking Schedule (All Dates)")
    schedule_rows = conn.execute("""
    SELECT r.room_number,
           h.name as hotel_name,
           r.room_type,
           b.booking_id,
           u.name as guest_name,
           b.check_in_date,
           b.check_out_date,
           b.booking_status
    FROM rooms r
    JOIN hotels h ON r.hotel_id = h.hotel_id
    JOIN bookings b ON r.room_id = b.room_id
    JOIN users u ON b.customer_id = u.user_id
    WHERE b.booking_status = 'CONFIRMED'
    ORDER BY r.hotel_id, r.room_number, b.check_in_date
    """).fetchall()
    if schedule_rows:
        import pandas as pd
        st.dataframe(pd.DataFrame([dict(sr) for sr in schedule_rows]), use_container_width=True)
    else:
        st.info("No active confirmed bookings on record.")
    conn.close()


with tab_policy:
    st.subheader("📜 Hotel Policy Documents & Vector Store Inspection")
    st.caption("ChromaDB vector store partitions hotel policy context for grounded RAG (Item 7).")

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    mumbai_pdf = os.path.join(data_dir, "Grand_Palace_Mumbai_Policy.pdf")
    delhi_pdf = os.path.join(data_dir, "Royal_Orchid_Delhi_Policy.pdf")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Mumbai Policy Document:**")
        if os.path.exists(mumbai_pdf):
            st.success(f"✓ Found: `{os.path.basename(mumbai_pdf)}` ({os.path.getsize(mumbai_pdf)} bytes)")
        else:
            st.warning("Not generated yet. Click 'Generate PDFs' in sidebar.")

    with c2:
        st.markdown("**Delhi Policy Document:**")
        if os.path.exists(delhi_pdf):
            st.success(f"✓ Found: `{os.path.basename(delhi_pdf)}` ({os.path.getsize(delhi_pdf)} bytes)")
        else:
            st.warning("Not generated yet. Click 'Generate PDFs' in sidebar.")

    st.markdown("#### 🔍 Test Policy Retrieval Directly")
    test_q = st.text_input("Test query on policy vector store:", value="What is the check-in and check-out time?")
    if st.button("Execute Similarity Search"):
        docs = rag_hotel_policy.retrieve_policy_context(test_q, hotel_id=st.session_state.selected_hotel_id, k=1)
        if docs:
            for d in docs:
                st.markdown(f"**Policy Section (from `{d.metadata.get('source')}`):**")
                st.info(d.page_content)
        else:
            st.warning("No matching vectors found. Ensure database and PDFs are indexed.")
