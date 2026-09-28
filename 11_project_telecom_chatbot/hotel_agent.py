"""
hotel_agent.py
Robust Tool-Calling Agent Orchestrator for the Hotel Booking System.
Uses native LLM tool binding (`llm.bind_tools(ALL_TOOLS)`), supported natively
by Groq (`llama-3.3-70b-versatile`, `qwen/qwen3-32b`).
"""
import os
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from booking_tools import ALL_TOOLS
import hotel_db
from hotel_memory import memory_manager

TOOL_MAP = {t.name: t for t in ALL_TOOLS}

SYSTEM_PROMPT = """You are 'Arohak Concierge', an intelligent, reliable, and professional AI Hotel Booking Assistant.
You assist customers with finding hotel rooms, making reservations, managing cancellations, and answering questions about hotel policies.

CRITICAL RULES & OPERATING PROCEDURES:
1. NEVER INVENT OR HALLUCINATE AVAILABILITY OR ROOMS:
   - Always call `search_rooms` or `check_room_availability` with actual dates, city, and number of guests.
   - If the user says: "I need a room in Mumbai for 2 people from Sept 20 to Sept 23", extract the location ('Mumbai'), number of guests (2), check-in date, and check-out date (format as YYYY-MM-DD, e.g. 2026-09-20 to 2026-09-23), and invoke `search_rooms`.
   - If dates or guest counts are missing, politely ask for the missing information.
   - If no rooms or records match, tell the guest and say: "Please refer to our website for other information."

2. BOOKING ACTIONS:
   - When the user confirms booking a room, invoke `create_booking` using the customer's ID, hotel_id, room_id, and dates.
   - Clearly present the booking confirmation details (Booking ID, Hotel, Room, Dates, Total Amount, Status).

3. BOOKING MANAGEMENT & CANCELLATION:
   - For listing reservations, use `list_customer_bookings`.
   - For viewing details, use `get_booking_details`.
   - For cancellations, use `cancel_booking`. Explain whether the booking was directly cancelled (if > 24 hours prior to check-in) or submitted as a cancellation request (if <= 24 hours).
   - If a requested booking cannot be found, say: "Please refer to our website for other information."

4. HOTEL POLICIES & RAG (PDF GROUNDING):
   - For questions regarding check-in/out times, Wi-Fi passwords, cancellation rules, breakfast timings, parking, or amenities, invoke `get_hotel_policy_info`.
   - Pass the hotel_id if the user mentioned a specific hotel (1 for Mumbai Grand Palace, 2 for Delhi Royal Orchid).
   - If the requested information, policy, or amenity is NOT in the official PDF document or database, you MUST say: "I apologize, but that information is not available in our official documents or database. Please refer to our website for other information."
   - NEVER invent or assume policies, amenities, or rules not present in the documents.

5. HOTEL CONTACT & FRONT DESK:
   - If the user asks for the front desk number, contact phone, email, or address for any hotel, invoke `get_hotel_contact_info`.

6. GENERAL RULE FOR MISSING INFORMATION:
   - If ANY information, service, amenity, policy, or record is not in the PDF documents or database, ALWAYS tell the user to refer to our website for other info (e.g. "Please refer to our website for other information.").

7. LONG-TERM GUEST MEMORY & PERSONAL PREFERENCES:
   - The system maintains permanent memory of guest preferences across all chats.
   - When the user tells you personal preferences, favorites, or facts (e.g., "I prefer high floor rooms", "my preferred view is sea view", "my anniversary is Oct 12"):
     Call `remember_user_preference` to store it permanently, and acknowledge it warmly.
   - When the user asks about their remembered details in ANY chat (new or existing, e.g. "what is my preferred room type?"):
     Answer accurately based on the KNOWN GUEST PROFILE & STORED MEMORIES section below or call `get_user_memories`.
   - Never say you don't know if the fact is present in the KNOWN GUEST PROFILE & STORED MEMORIES section!

8. TONE:
   - Be hospitable, concise, clear, and professional.
"""


def parse_memory_declaration(text: str) -> Optional[Tuple[str, str]]:
    """Extracts explicit memory statements like 'my preferred room type is Deluxe'."""
    text_clean = text.strip()

    # Pattern: (remember that) my favorite <X> is <Y>
    m1 = re.search(r"(?:remember\s+(?:that\s+)?)?my\s+favou?rite\s+([\w\s]+?)\s+is\s+([^.,!?\n]+)", text_clean, re.IGNORECASE)
    if m1:
        key = f"favorite {m1.group(1).strip().lower()}"
        val = m1.group(2).strip()
        return (key, val)

    # Pattern: (remember that) my preferred <X> is <Y>
    m2 = re.search(r"(?:remember\s+(?:that\s+)?)?my\s+preferred\s+([\w\s]+?)\s+is\s+([^.,!?\n]+)", text_clean, re.IGNORECASE)
    if m2:
        key = f"preferred {m2.group(1).strip().lower()}"
        val = m2.group(2).strip()
        return (key, val)

    # Pattern: remember that my <X> is <Y>
    m3 = re.search(r"remember\s+(?:that\s+)?my\s+([\w\s]+?)\s+is\s+([^.,!?\n]+)", text_clean, re.IGNORECASE)
    if m3:
        key = m3.group(1).strip().lower()
        val = m3.group(2).strip()
        return (key, val)

    return None


def parse_memory_query(text: str) -> Optional[str]:
    """Detects questions asking for remembered personal facts (e.g., 'what is my preferred room type?')."""
    text_clean = text.strip()
    m_pref = re.search(r"(?:what(?:\s+is|'s)|do\s+you\s+know)\s+my\s+(?:preferred|favou?rite)\s+([\w\s]+?)(?:\?|$)", text_clean, re.IGNORECASE)
    if m_pref:
        return f"preferred {m_pref.group(1).strip().lower()}"
    m_gen = re.search(r"(?:what(?:\s+is|'s)|do\s+you\s+know)\s+my\s+([\w\s]+?)(?:\?|$)", text_clean, re.IGNORECASE)
    if m_gen and not any(w in m_gen.group(1).lower() for w in ["booking id", "current reservation", "active booking"]):
        return m_gen.group(1).strip().lower()
    return None


class HotelAgentRunner:
    """
    Executes multi-step tool-calling with persistent long-term memory and tool tracing.
    Gracefully handles missing GROQ_API_KEY by falling back to direct tool execution.
    """
    def __init__(self, customer_id: int = 3, model_name: Optional[str] = None):
        self.customer_id = customer_id
        openai_key = os.environ.get("OPENAI_API_KEY")
        groq_key = os.environ.get("GROQ_API_KEY")

        self.has_key = False
        self.llm = None
        self.llm_with_tools = None

        # 1. Priority: Direct OpenAI API if OPENAI_API_KEY is provided
        if openai_key and openai_key.strip() and not openai_key.startswith("your_"):
            try:
                from langchain_openai import ChatOpenAI
                o_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
                self.llm = ChatOpenAI(model=o_model, api_key=openai_key.strip(), temperature=0.1)
                self.llm_with_tools = self.llm.bind_tools(ALL_TOOLS)
                self.has_key = True
            except Exception:
                self.llm = None
                self.llm_with_tools = None

        # 2. Priority: Groq API (defaulting to openai/gpt-oss-120b)
        if self.llm_with_tools is None and groq_key and groq_key.strip() and not groq_key.startswith("your_"):
            if not model_name:
                model_name = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
            try:
                self.llm = ChatGroq(
                    model=model_name,
                    temperature=0.1,
                    max_retries=2,
                )
                self.llm_with_tools = self.llm.bind_tools(ALL_TOOLS)
                self.has_key = True
            except Exception:
                self.has_key = False

    def get_system_message(self) -> SystemMessage:
        """Dynamically injects active guest profile and persistent memories into the prompt via Mem0."""
        profile_str = memory_manager.get_guest_profile_prompt(self.customer_id)
        mode_label = memory_manager.get_mode_label()

        content = (
            SYSTEM_PROMPT +
            f"\n\nCURRENT ACTIVE CUSTOMER CONTEXT: Customer ID = {self.customer_id}." +
            f"\n\nKNOWN GUEST PROFILE & STORED MEMORIES (ENGINE: {mode_label}):\n{profile_str}\n"
        )
        return SystemMessage(content=content)

    def _fallback_invoke(self, user_input: str) -> Dict[str, Any]:
        """Direct tool execution fallback with full long-term memory support via Mem0."""
        inp = user_input.lower().strip()
        steps = []

        class StepToolCall:
            def __init__(self, name, args):
                self.tool = name
                self.tool_input = args

        # 1. Check if user is sharing a personal preference or fact (e.g. "I prefer high floor rooms")
        decl = parse_memory_declaration(user_input)
        if decl:
            k, v = decl
            memory_manager.save_preference(k, v, self.customer_id)
            msg = f"I've saved that to your guest profile! Your {k} is **{v}**. I will remember this even across new chats."
            steps.append((StepToolCall("remember_user_preference", {"key": k, "value": v, "customer_id": self.customer_id}), f"Saved {k}={v}"))
            return {"output": msg, "intermediate_steps": steps}

        # 2. Check if user is querying a remembered preference (e.g. "what is my preferred room type?")
        query_key = parse_memory_query(user_input)
        if query_key:
            all_mems = memory_manager.get_all_memories(self.customer_id)
            found_val = None
            matched_key = None
            clean_q = query_key.replace("preferred ", "").replace("favorite ", "").strip()
            for m in all_mems:
                mk, mv = m.get("key", ""), m.get("value", "")
                clean_m = mk.replace("preferred ", "").replace("favorite ", "").strip()
                if query_key in mk or mk in query_key or (clean_q and clean_q in clean_m) or (clean_m and clean_m in clean_q) or clean_q in mv.lower():
                    found_val = mv
                    matched_key = mk
                    break
            if found_val:
                steps.append((StepToolCall("get_user_memories", {"customer_id": self.customer_id}), str(all_mems)))
                return {
                    "output": f"Your {matched_key} is **{found_val}**! I remembered this from our previous conversation.",
                    "intermediate_steps": steps,
                }
            else:
                return {
                    "output": f"I don't have your {query_key} saved in your profile yet. You can let me know by saying 'My {query_key} is ...'!",
                    "intermediate_steps": [],
                }

        # 3. Check for general memory listing or clearing
        if any(w in inp for w in ["what do you remember about me", "my preferences", "show my memories", "my profile"]):
            profile_str = memory_manager.get_guest_profile_prompt(self.customer_id)
            return {"output": f"Here are the preferences and details I remember about you:\n{profile_str}", "intermediate_steps": []}

        if "clear my memory" in inp or "clear memories" in inp:
            memory_manager.clear_memories(self.customer_id)
            return {"output": "I have cleared all your stored personal preferences.", "intermediate_steps": []}

        if "my booking" in inp or "current reservation" in inp or "show" in inp and "booking" in inp:
            res = TOOL_MAP["list_customer_bookings"].invoke({"customer_id": self.customer_id})
            steps.append((StepToolCall("list_customer_bookings", {"customer_id": self.customer_id}), res))
            return {"output": res, "intermediate_steps": steps}

        elif "cancel" in inp:
            import re
            match = re.search(r"bk-\d+", inp)
            bk_id = match.group(0).upper() if match else "BK-1001"
            res = TOOL_MAP["cancel_booking"].invoke({"booking_id": bk_id, "customer_id": self.customer_id})
            steps.append((StepToolCall("cancel_booking", {"booking_id": bk_id, "customer_id": self.customer_id}), res))
            return {"output": res, "intermediate_steps": steps}

        elif any(k in inp for k in ["check in", "check-in", "check out", "check-out", "wifi", "wi-fi", "parking", "policy", "rule", "breakfast", "dining", "ev", "pet", "pool", "gym", "spa", "helicopter"]):
            hotel_id = 1 if "mumbai" in inp or "grand palace" in inp else (2 if "delhi" in inp or "orchid" in inp else 1)
            res = TOOL_MAP["get_hotel_policy_info"].invoke({"question": user_input, "hotel_id": hotel_id})
            steps.append((StepToolCall("get_hotel_policy_info", {"question": user_input, "hotel_id": hotel_id}), res))
            return {"output": res, "intermediate_steps": steps}

        elif any(k in inp for k in ["front desk", "reception", "phone", "number", "contact", "call", "helpdesk", "email", "address"]):
            hotel_name = None
            if "mumbai" in inp or "grand palace" in inp:
                hotel_name = "Grand Palace"
            elif "delhi" in inp or "orchid" in inp:
                hotel_name = "Royal Orchid"
            elif "bangalore" in inp or "bengaluru" in inp or "silicon" in inp:
                hotel_name = "Silicon Oasis"
            res = TOOL_MAP["get_hotel_contact_info"].invoke({"hotel_name_or_city": hotel_name})
            steps.append((StepToolCall("get_hotel_contact_info", {"hotel_name_or_city": hotel_name}), res))
            return {"output": res, "intermediate_steps": steps}

        elif any(k in inp for k in ["search", "room", "hotel", "availab", "vacan", "stay", "book", "accommodat"]):
            import re
            import datetime
            from dateutil import parser

            # City extraction
            city = None
            if "mumbai" in inp or "bombay" in inp or "grand palace" in inp:
                city = "Mumbai"
            elif "delhi" in inp or "orchid" in inp:
                city = "Delhi"
            elif "bangalore" in inp or "bengaluru" in inp or "garden" in inp:
                city = "Bangalore"

            # Date extraction
            d_in = None
            d_out = None
            try:
                # Check for date range with 'to', 'until', or '-'
                if re.search(r"\bto\b|\buntil\b", inp):
                    parts = re.split(r"\bto\b|\buntil\b", user_input, maxsplit=1)
                    parsed_in = parser.parse(parts[0], fuzzy=True)
                    parsed_out = parser.parse(parts[1], fuzzy=True)
                    d_in = parsed_in.strftime("%Y-%m-%d")
                    d_out = parsed_out.strftime("%Y-%m-%d")
                else:
                    parsed_in = parser.parse(user_input, fuzzy=True)
                    d_in = parsed_in.strftime("%Y-%m-%d")
                    d_out = (parsed_in + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            except Exception:
                today = datetime.date.today()
                d_in = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                d_out = (today + datetime.timedelta(days=3)).strftime("%Y-%m-%d")

            # Guests count extraction
            guests = 1
            guest_match = re.search(r"(\d+)\s*(?:guest|person|people|adult)", inp)
            if guest_match:
                guests = int(guest_match.group(1))

            args = {
                "city": city,
                "check_in_date": d_in,
                "check_out_date": d_out,
                "number_of_guests": guests,
            }
            res = TOOL_MAP["search_rooms"].invoke(args)
            steps.append((StepToolCall("search_rooms", args), res))
            return {"output": res, "intermediate_steps": steps}

        else:
            return {
                "output": "Welcome to Arohak Concierge! I can help you search rooms, make reservations, manage cancellations, and answer hotel policy questions.",
                "intermediate_steps": [],
            }

    def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        user_input = inputs.get("input", "")
        chat_history = inputs.get("chat_history", [])

        # Proactively detect and persist direct memory declarations
        decl = parse_memory_declaration(user_input)
        if decl:
            k, v = decl
            memory_manager.save_preference(k, v, self.customer_id)

        if not self.has_key or self.llm_with_tools is None:
            return self._fallback_invoke(user_input)

        # Dynamic system prompt containing updated persistent memories
        system_message = self.get_system_message()

        # Construct message list
        messages = [system_message]
        for msg in chat_history:
            if isinstance(msg, (HumanMessage, AIMessage, SystemMessage, ToolMessage)):
                messages.append(msg)
            elif isinstance(msg, dict):
                role = msg.get("role")
                content = msg.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))

        messages.append(HumanMessage(content=user_input))

        intermediate_steps = []
        max_iterations = 6
        final_text = ""

        class StepToolCall:
            def __init__(self, name, args):
                self.tool = name
                self.tool_input = args

        try:
            for _ in range(max_iterations):
                response: AIMessage = self.llm_with_tools.invoke(messages)
                messages.append(response)

                # Check if tools need to be executed
                if response.tool_calls:
                    for tool_call in response.tool_calls:
                        tool_name = tool_call.get("name")
                        tool_args = tool_call.get("args", {})
                        call_id = tool_call.get("id")

                        # Bind active customer_id if memory or booking tools require it
                        if tool_name in ("remember_user_preference", "get_user_memories", "list_customer_bookings"):
                            if "customer_id" not in tool_args or not tool_args.get("customer_id"):
                                tool_args["customer_id"] = self.customer_id

                        if tool_name in TOOL_MAP:
                            try:
                                tool_result = TOOL_MAP[tool_name].invoke(tool_args)
                            except Exception as e:
                                tool_result = f"Error executing {tool_name}: {str(e)}"
                        else:
                            tool_result = f"Tool '{tool_name}' not recognized."

                        intermediate_steps.append((StepToolCall(tool_name, tool_args), str(tool_result)))
                        messages.append(ToolMessage(
                            content=str(tool_result),
                            tool_call_id=call_id,
                            name=tool_name,
                        ))
                else:
                    # No more tools called, this is the final answer
                    final_text = response.content
                    break
        except Exception:
            return self._fallback_invoke(user_input)

        if not final_text and messages:
            final_text = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])

        if final_text:
            try:
                memory_manager.add_interaction(user_input, final_text, self.customer_id)
            except Exception:
                pass

        return {
            "output": final_text,
            "intermediate_steps": intermediate_steps,
        }


def build_hotel_agent(customer_id: int = 3, model_name: Optional[str] = None) -> HotelAgentRunner:
    return HotelAgentRunner(customer_id=customer_id, model_name=model_name)
