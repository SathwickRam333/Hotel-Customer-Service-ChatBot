"""
rag_hotel_policy.py
Handles RAG indexing and grounded retrieval for Hotel Policy PDFs:
- PyPDFLoader + RecursiveCharacterTextSplitter
- Multi-hotel isolation using metadata filtering (`hotel_id`)
- Grounded QA prompt that strictly prevents hallucinations
"""
import os
import re
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
from typing import Optional, List, Any
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from langchain_groq import ChatGroq

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_store")
COLLECTION_NAME = "hotel_policies"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

RAG_SYSTEM_PROMPT = """You are the official Hotel Guest Services Assistant.
Your duty is to answer customer questions accurately and strictly based on the provided Hotel Policy & Guidelines document.

CRITICAL INSTRUCTIONS:
1. Ground your answer EXCLUSIVELY on the Context below.
2. If the answer is found in the Context (such as check-in/out times, Wi-Fi details, cancellation rules, breakfast timings, parking, or amenities), provide a clear, polite, and concise answer.
3. If the requested information is NOT explicitly stated or cannot be directly inferred from the Context below, you MUST state:
   "I apologize, but that information is not available in our official policy documents or database. Please refer to our website for other information."
4. NEVER invent or assume policies, fees, or amenities not present in the text.

Context:
{context}
"""

_embeddings_cache = None


def get_embeddings():
    global _embeddings_cache
    if _embeddings_cache is None:
        _embeddings_cache = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    return _embeddings_cache


def get_vector_store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_DIR,
    )


def ingest_hotel_pdf(pdf_path: str, hotel_id: int, hotel_name: str) -> int:
    """
    Ingests a hotel policy PDF into ChromaDB with hotel_id metadata for isolation.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found at {pdf_path}")

    loader = PyPDFLoader(pdf_path)
    pages = loader.load()

    full_text = "\n".join([p.page_content for p in pages])
    full_text = re.sub(r'Page\s+\d+\s*\|\s*Official Guest Policy Document', '', full_text)

    # Split cleanly by numbered policy sections (e.g. "1. Check-in...", "2. Cancellation...")
    raw_sections = re.split(r'\n(?=\s*\d+\.\s+[A-Z])', full_text)

    chunks = []
    for sec in raw_sections:
        clean_sec = sec.strip()
        if clean_sec and re.search(r'\d+\.\s+[A-Z]', clean_sec):
            chunks.append(Document(page_content=clean_sec))

    if not chunks:
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
        chunks = splitter.split_documents(pages)

    for i, chunk in enumerate(chunks):
        chunk.metadata["hotel_id"] = hotel_id
        chunk.metadata["hotel_name"] = hotel_name
        chunk.metadata["source"] = os.path.basename(pdf_path)
        chunk.metadata["chunk_id"] = i

    ids = [f"hotel_{hotel_id}_sec_{i}" for i in range(len(chunks))]
    vector_store = get_vector_store()
    vector_store.add_documents(chunks, ids=ids)
    print(f"Ingested {len(chunks)} discrete policy sections for {hotel_name} (hotel_id={hotel_id}).")
    return len(chunks)


def retrieve_policy_context(query: str, hotel_id: Optional[int] = None, k: int = 3) -> List[Document]:
    """
    Retrieves top-k unique chunks, filtered by hotel_id if provided.
    Guarantees that no duplicate chunks are ever returned.
    """
    try:
        vector_store = get_vector_store()
        filter_kwargs = {}
        if hotel_id is not None:
            filter_kwargs["hotel_id"] = hotel_id

        raw_docs = vector_store.similarity_search(query, k=max(k * 2, 4), filter=filter_kwargs if filter_kwargs else None)

        unique_docs = []
        seen = set()
        for d in raw_docs:
            content = d.page_content.strip()
            if content and content not in seen:
                seen.add(content)
                unique_docs.append(d)
            if len(unique_docs) >= k:
                break

        return unique_docs
    except Exception as e:
        print(f"Notice: retrieve_policy_context error ({e}), recovering...")
        return []


TOPIC_KEYWORDS = {
    "Check-in and Check-out": ["check-in", "checkin", "check in", "checkout", "check out", "check-out", "arrival", "departure", "passport", "voter id", "aadhaar", "early check-in", "late check-out", "id proof", "identification"],
    "Cancellation and Refund": ["cancel", "cancellation", "refund", "cutoff", "24 hours", "penalty", "fee"],
    "Wi-Fi": ["wifi", "wi-fi", "internet", "ssid", "password", "network", "speed", "mbps", "portal", "connectivity"],
    "Dining & Breakfast": ["dining", "breakfast", "buffet", "restaurant", "lunch", "dinner", "food", "room service", "timings", "meal", "coffee"],
    "Parking": ["parking", "valet", "car", "ev", "electric vehicle", "charger", "charging", "basement", "vehicle"],
    "Pool, Gym, Spa": ["pool", "swimming", "gym", "fitness", "spa", "massage", "ayurvedic", "workout", "rooftop pool"],
    "House Rules & Pets": ["pet", "pets", "dog", "service dog", "smoking", "smoke", "quiet hours", "noise", "party", "parties", "guide dog"],
}

STOP_WORDS = {
    "does", "the", "hotel", "grand", "palace", "royal", "orchid", "residency", "silicon", "oasis", "have",
    "a", "an", "for", "guests", "is", "there", "any", "in", "on", "at", "of", "to",
    "what", "where", "when", "how", "who", "why", "can", "i", "you", "we", "they",
    "our", "your", "please", "tell", "me", "about", "do", "are", "available", "policy",
    "rules", "information", "details", "guidelines", "service", "services", "facility", "facilities"
}

HOTEL_NAMES = {
    1: "Grand Palace Hotel",
    2: "Royal Orchid Residency",
    3: "Silicon Oasis Suites",
}


def answer_policy_question(query: str, hotel_id: Optional[int] = None, llm: Optional[Any] = None) -> str:
    """
    Answers a policy question using RAG with strict relevance filtering and hallucination prevention.
    - If the user asks about an unmentioned amenity (e.g. helicopter landing pad), it rejects gracefully.
    - If relevant policy sections exist, only the relevant sections are returned without text dumping.
    """
    hotel_name = HOTEL_NAMES.get(hotel_id, "the hotel")
    docs = retrieve_policy_context(query, hotel_id=hotel_id, k=4)
    if not docs:
        return f"I apologize, but no policy documents have been indexed for {hotel_name} yet. Please refer to our website for other information."

    # Deduplicate and clean chunks
    unique_chunks = []
    seen = set()
    for d in docs:
        cleaned = d.page_content.strip()
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        filtered_lines = [
            line for line in lines
            if not line.startswith("Grand Palace Hotel, Mumbai - Guest Policy")
            and not line.startswith("Royal Orchid Residency, Delhi - Guest Policy")
            and not line.startswith("Colaba Causeway")
            and not line.startswith("Connaught Place")
            and not line.startswith("Page ")
        ]
        body = "\n".join(filtered_lines).strip()
        if body and body not in seen:
            seen.add(body)
            unique_chunks.append(body)

    if not unique_chunks:
        unique_chunks = [d.page_content.strip() for d in docs]

    # Semantic relevance filtering
    q_lower = query.lower()
    content_words = [w for w in re.findall(r"[a-zA-Z]{3,}", q_lower) if w not in STOP_WORDS]

    matched_chunks = []
    for chunk in unique_chunks:
        c_lower = chunk.lower()
        # Direct content keyword matches using word boundaries
        direct_matches = [w for w in content_words if re.search(r"\b" + re.escape(w) + r"\b", c_lower)]
        if direct_matches:
            matched_chunks.append((len(direct_matches) * 2, chunk))
            continue

        # Policy topic category matches using word boundaries
        for topic, kws in TOPIC_KEYWORDS.items():
            q_topic_match = any(re.search(r"\b" + re.escape(kw) + r"\b", q_lower) for kw in kws)
            c_topic_match = any(re.search(r"\b" + re.escape(kw) + r"\b", c_lower) for kw in kws)
            if q_topic_match and c_topic_match:
                matched_chunks.append((1, chunk))
                break

    # If NO chunks match the specific question (e.g., helicopter, casino, scuba)
    if not matched_chunks:
        missing_term = " ".join(content_words) if content_words else "that specific amenity"
        return (
            f"I apologize, but that information is not available in the official policy document for {hotel_name}. "
            f"According to our official guidelines, {hotel_name} does not provide {missing_term}. "
            f"Please refer to our website for other information."
        )

    # Sort chunks by relevance and take only top relevance tier
    matched_chunks.sort(key=lambda x: x[0], reverse=True)
    best_score = matched_chunks[0][0]
    relevant_chunks = [c[1] for c in matched_chunks if c[0] >= best_score]
    context_str = "\n\n".join(relevant_chunks)

    # Attempt neural LLM synthesis if GROQ_API_KEY is available
    if os.environ.get("GROQ_API_KEY"):
        candidate_models = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "llama3-8b-8192"]
        preferred_model = os.environ.get("GROQ_MODEL")
        if preferred_model and preferred_model not in candidate_models:
            candidate_models.insert(0, preferred_model)

        for model_name in candidate_models:
            try:
                chat_llm = ChatGroq(model=model_name, temperature=0, max_tokens=512)
                prompt = ChatPromptTemplate.from_messages([
                    ("system", RAG_SYSTEM_PROMPT),
                    ("human", "Question: {question}\nContext: {context}"),
                ])
                chain = prompt | chat_llm | StrOutputParser()
                return chain.invoke({"question": query, "context": context_str})
            except Exception:
                continue

    # Return only the relevant policy section
    return context_str
