import os
import asyncio
import json
from pathlib import Path
from app.worker import celery_app

LOCAL_UPLOAD_DIR = os.getenv("LOCAL_UPLOAD_DIR", "/app/uploads")


@celery_app.task(bind=True, max_retries=3, name="process_document")
def process_document(self, document_id: str):
    asyncio.run(_process(self, document_id))


async def _process(task, document_id: str):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from app.models import Document, Chunk, DocumentStatus
    from app.services.ai import embed_batch, extract_document, summarize_document

    engine = create_async_engine(os.getenv("DATABASE_URL"))
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        doc = await db.get(Document, document_id)
        if not doc:
            return
        doc.status = DocumentStatus.processing
        await db.commit()
        try:
            import fitz
            file_path = Path(LOCAL_UPLOAD_DIR) / doc.s3_key
            pdf = fitz.open(str(file_path))
            doc.page_count = len(pdf)
            full_text = ""
            chunks_data = []
            idx = 0
            for pn in range(len(pdf)):
                text = pdf[pn].get_text().strip()
                if not text:
                    continue
                full_text = full_text + "\n" + text
                words = text.split()
                s = 0
                while s < len(words):
                    ct = " ".join(words[s:s + 512])
                    chunks_data.append({
                        "content": ct,
                        "page_num": pn,
                        "chunk_index": idx,
                        "token_count": len(words[s:s + 512])
                    })
                    idx += 1
                    s += 462
            pdf.close()
            print("[worker] chunks extracted: " + str(len(chunks_data)))
            all_emb = []
            for i in range(0, len(chunks_data), 20):
                batch = await embed_batch([c["content"] for c in chunks_data[i:i + 20]])
                all_emb.extend(batch)
                print("[worker] Embedded " + str(min(i + 20, len(chunks_data))) + "/" + str(len(chunks_data)))
            old = await db.execute(select(Chunk).where(Chunk.document_id == doc.id))
            for c in old.scalars().all():
                await db.delete(c)
            for i, cd in enumerate(chunks_data):
                db.add(Chunk(
                    document_id=doc.id,
                    workspace_id=doc.workspace_id,
                    content=cd["content"],
                    page_num=cd["page_num"],
                    chunk_index=cd["chunk_index"],
                    token_count=cd["token_count"],
                    embedding=all_emb[i]
                ))
            await db.flush()
            print("[worker] Running AI extraction...")
            doc.extracted_data = json.dumps(await extract_document(full_text))
            print("[worker] Generating summary...")
            doc.summary = await summarize_document(full_text)
            doc.status = DocumentStatus.processed
            await db.commit()
            print("[worker] Document " + document_id + " fully processed with AI")
        except Exception as e:
            doc.status = DocumentStatus.failed
            doc.error_message = str(e)
            await db.commit()
            print("[worker] FAILED: " + str(e))
            raise task.retry(exc=e, countdown=30)