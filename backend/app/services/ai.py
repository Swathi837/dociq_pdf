import os
import json
import asyncio
import re
from typing import Optional
from fastembed import TextEmbedding

_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        print("[ai] Loading embedding model...")
        _embedding_model = TextEmbedding("BAAI/bge-small-en-v1.5")
        print("[ai] Embedding model loaded")
    return _embedding_model


async def embed_text(text: str) -> list[float]:
    loop = asyncio.get_event_loop()
    def _embed():
        model = get_embedding_model()
        return list(model.embed([text]))[0].tolist()
    return await loop.run_in_executor(None, _embed)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    loop = asyncio.get_event_loop()
    def _embed():
        model = get_embedding_model()
        return [r.tolist() for r in model.embed(texts)]
    return await loop.run_in_executor(None, _embed)


async def extract_document(text: str) -> dict:
    """Extract key info using regex — no API needed."""
    loop = asyncio.get_event_loop()
    def _extract():
        # Extract dates
        date_patterns = re.findall(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b', text, re.IGNORECASE)

        # Extract amounts
        amount_patterns = re.findall(r'[$£€₹]\s*[\d,]+(?:\.\d{2})?|\b[\d,]+(?:\.\d{2})?\s*(?:USD|EUR|GBP|INR|dollars?|rupees?)\b', text, re.IGNORECASE)

        # Extract emails
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)

        # Detect document type
        text_lower = text.lower()
        if any(w in text_lower for w in ['agreement', 'contract', 'parties', 'whereas']):
            doc_type = 'contract'
        elif any(w in text_lower for w in ['invoice', 'bill', 'payment due', 'amount due']):
            doc_type = 'invoice'
        elif any(w in text_lower for w in ['policy', 'terms', 'conditions']):
            doc_type = 'policy'
        elif any(w in text_lower for w in ['report', 'analysis', 'summary']):
            doc_type = 'report'
        else:
            doc_type = 'other'

        # Extract first 5 sentences as key clauses
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 30]
        key_clauses = sentences[:5]

        return {
            "document_type": doc_type,
            "parties": list(set(emails)) if emails else [],
            "effective_date": date_patterns[0] if date_patterns else None,
            "expiry_date": date_patterns[-1] if len(date_patterns) > 1 else None,
            "key_dates": [{"label": "detected date", "date": d} for d in date_patterns[:5]],
            "amounts": [{"label": "detected amount", "amount": a} for a in amount_patterns[:5]],
            "payment_terms": None,
            "termination_clause": None,
            "jurisdiction": None,
            "key_clauses": key_clauses,
            "risks": [],
            "obligations": []
        }
    return await loop.run_in_executor(None, _extract)


async def summarize_document(text: str) -> str:
    """Generate summary from first and last paragraphs — no API needed."""
    loop = asyncio.get_event_loop()
    def _summarize():
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]
        if not paragraphs:
            paragraphs = [text[:500]]
        intro = paragraphs[0][:500] if paragraphs else ""
        middle = paragraphs[len(paragraphs)//2][:300] if len(paragraphs) > 2 else ""
        ending = paragraphs[-1][:300] if len(paragraphs) > 1 else ""
        summary = f"Document Overview:\n{intro}"
        if middle:
            summary += f"\n\nKey Content:\n{middle}"
        if ending:
            summary += f"\n\nConclusion:\n{ending}"
        return summary
    return await loop.run_in_executor(None, _summarize)


async def answer_question(
    question: str,
    context_chunks: list[dict],
    chat_history: Optional[list[dict]] = None
) -> str:
    """Answer using context chunks — keyword matching, no API needed."""
    loop = asyncio.get_event_loop()
    def _answer():
        question_words = set(question.lower().split())
        best_chunks = sorted(
            context_chunks,
            key=lambda c: sum(1 for w in question_words if w in c['content'].lower()),
            reverse=True
        )[:3]
        if not best_chunks:
            return "I couldn't find relevant information in this document."
        answer = f"Based on the document (Page {best_chunks[0]['page_num']+1}):\n\n"
        for chunk in best_chunks:
            answer += f"• {chunk['content'][:300]}...\n\n"
        return answer
    return await loop.run_in_executor(None, _answer)