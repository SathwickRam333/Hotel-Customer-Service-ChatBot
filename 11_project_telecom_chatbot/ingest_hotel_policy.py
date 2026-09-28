"""
ingest_hotel_policy.py
CLI script to index all hotel policy PDFs into ChromaDB:
- data/Grand_Palace_Mumbai_Policy.pdf (hotel_id: 1)
- data/Royal_Orchid_Delhi_Policy.pdf  (hotel_id: 2)
"""
import os
from rag_hotel_policy import ingest_hotel_pdf
from generate_hotel_pdfs import main as generate_pdfs

def main():
    print("=== Ingesting Hotel Policy PDFs into ChromaDB ===")
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    mumbai_pdf = os.path.join(data_dir, "Grand_Palace_Mumbai_Policy.pdf")
    delhi_pdf = os.path.join(data_dir, "Royal_Orchid_Delhi_Policy.pdf")

    # Generate if not exists
    if not os.path.exists(mumbai_pdf) or not os.path.exists(delhi_pdf):
        print("PDFs not found. Generating now...")
        generate_pdfs()

    print("1. Ingesting Mumbai Grand Palace Hotel Policy...")
    c1 = ingest_hotel_pdf(mumbai_pdf, hotel_id=1, hotel_name="Grand Palace Hotel Mumbai")
    print(f"   -> Stored {c1} chunks.")

    print("2. Ingesting Delhi Royal Orchid Residency Policy...")
    c2 = ingest_hotel_pdf(delhi_pdf, hotel_id=2, hotel_name="Royal Orchid Residency Delhi")
    print(f"   -> Stored {c2} chunks.")

    print("=== Policy Ingestion Complete ===")

if __name__ == "__main__":
    main()
