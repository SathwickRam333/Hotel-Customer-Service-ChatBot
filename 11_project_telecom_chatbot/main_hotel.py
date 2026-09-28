"""
main_hotel.py
CLI entry point for AROHAK Hotel AI Concierge (Items 6 & 7).
Usage: uv run python main_hotel.py
"""
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from hotel_agent import build_hotel_agent

load_dotenv()


def main():
    print("===============================================================")
    print("   AROHAK Hotel AI Concierge (CLI Interface)                  ")
    print("===============================================================")
    print("Type your question or booking request below.")
    print("Commands: 'quit', 'exit', or 'seed' to reset sample database.\n")

    customer_id = 3  # Rahul Sharma
    print(f"Active Simulated User: Rahul Sharma (Customer ID: {customer_id})\n")

    agent_executor = build_hotel_agent(customer_id=customer_id)
    chat_history = []

    while True:
        try:
            user_input = input("Guest: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("Thank you for using Arohak Concierge. Goodbye!")
                break
            if user_input.lower() == "seed":
                import seed_hotel
                seed_hotel.seed()
                print("Database re-seeded.\n")
                continue

            print("\nConcierge: ", end="", flush=True)
            res = agent_executor.invoke({"input": user_input, "chat_history": chat_history})
            print(res.get("output", ""))
            print("\n" + "-" * 60 + "\n")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Goodbye!")
            break
        except Exception as e:
            print(f"\n[Error]: {e}\n")


if __name__ == "__main__":
    main()
