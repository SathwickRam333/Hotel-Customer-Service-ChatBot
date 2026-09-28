"""
hotel_memory.py
Unified Memory Management for AROHAK Hotel Concierge with Mem0 support.
Supports:
1. Mem0 Cloud API (when MEM0_API_KEY is configured in .env)
2. Local Persistent Storage (SQLite hotel_booking.db) for 100% offline reliability.
"""
import os
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import hotel_db

load_dotenv()
logger = logging.getLogger(__name__)


class HotelMemoryManager:
    """
    Manages long-term guest memories and preferences across sessions.
    Automatically switches between Mem0 Cloud Platform and Local Persistent SQLite.
    """
    def __init__(self):
        self.api_key = os.environ.get("MEM0_API_KEY")
        self.client = None
        self.mode = "local"
        self._init_backend()

    def _init_backend(self):
        # Attempt Mem0 Cloud if an API key is provided and not a placeholder
        if self.api_key and self.api_key.strip() and not self.api_key.startswith("your_"):
            try:
                from mem0 import MemoryClient
                self.client = MemoryClient(api_key=self.api_key.strip())
                self.mode = "cloud"
                logger.info("HotelMemoryManager initialized with Mem0 Cloud API.")
                return
            except Exception as e:
                logger.warning(f"Could not connect to Mem0 Cloud API ({e}). Falling back to local store.")

        # Default: Local SQLite Memory Store
        self.mode = "local"
        hotel_db.init_db()
        logger.info("HotelMemoryManager initialized with Local SQLite persistent storage.")

    def get_mode_label(self) -> str:
        """Returns human-readable label for UI indicators."""
        if self.mode == "cloud":
            return "Mem0 Cloud API (Cloud)"
        return "Mem0 Local Engine (Local SQLite)"

    def add_interaction(self, user_text: str, assistant_text: Optional[str] = None, customer_id: int = 3) -> bool:
        """
        Stores memory or extracts guest facts from conversation.
        """
        if self.mode == "cloud" and self.client:
            try:
                user_id = f"guest_{customer_id}"
                messages = [{"role": "user", "content": user_text}]
                if assistant_text:
                    messages.append({"role": "assistant", "content": assistant_text})
                self.client.add(messages, user_id=user_id)
                return True
            except Exception as e:
                logger.warning(f"Mem0 Cloud add failed: {e}. Saving to local store.")

        # Local storage fallback / default
        hotel_db.save_user_memory(customer_id, "preference", user_text)
        return True

    def save_preference(self, key: str, value: str, customer_id: int = 3) -> bool:
        """
        Explicitly saves a key-value preference (e.g. room preference = high floor).
        """
        # Save to local SQLite first (ensuring immediate offline availability)
        hotel_db.save_user_memory(customer_id, key, value)

        if self.mode == "cloud" and self.client:
            try:
                user_id = f"guest_{customer_id}"
                self.client.add([{"role": "user", "content": f"My {key} is {value}"}], user_id=user_id)
            except Exception as e:
                logger.warning(f"Mem0 Cloud sync failed: {e}")

        return True

    def get_all_memories(self, customer_id: int = 3) -> List[Dict[str, str]]:
        """
        Returns all stored memories for a customer as list of dicts: [{'key': ..., 'value': ...}].
        """
        results = []

        if self.mode == "cloud" and self.client:
            try:
                user_id = f"guest_{customer_id}"
                cloud_mems = self.client.get_all(user_id=user_id)
                if cloud_mems:
                    for item in cloud_mems:
                        text = item.get("memory") if isinstance(item, dict) else getattr(item, "memory", str(item))
                        results.append({"key": "fact", "value": text})
                    return results
            except Exception as e:
                logger.warning(f"Mem0 Cloud get_all failed: {e}. Reading local store.")

        # Read from local SQLite
        local_mems = hotel_db.get_user_memories(customer_id)
        for k, v in local_mems.items():
            results.append({"key": k, "value": v})
        return results

    def get_guest_profile_prompt(self, customer_id: int = 3) -> str:
        """
        Formats remembered preferences as a concise prompt snippet for injection into the system prompt.
        """
        memories = self.get_all_memories(customer_id)
        if not memories:
            return "(No guest preferences recorded yet)"

        lines = []
        for m in memories:
            k = m.get("key", "").title()
            v = m.get("value", "")
            if k == "Fact":
                lines.append(f"- {v}")
            else:
                lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    def clear_memories(self, customer_id: int = 3) -> bool:
        """
        Wipes stored memories for a customer.
        """
        hotel_db.clear_user_memories(customer_id)

        if self.mode == "cloud" and self.client:
            try:
                user_id = f"guest_{customer_id}"
                # Delete user memories from cloud
                self.client.delete_all(user_id=user_id)
            except Exception as e:
                logger.warning(f"Mem0 Cloud delete failed: {e}")

        return True


# Global singleton instance
memory_manager = HotelMemoryManager()
