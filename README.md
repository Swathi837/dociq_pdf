# DocIQ PDF

DocIQ is a full-stack document intelligence platform for uploading PDFs, extracting text and key metadata, asking questions about documents, and creating deadline alerts.

## Features

- JWT authentication with user workspaces
- PDF upload and local file storage
- Background document processing with Celery and Redis
- Text extraction, chunking, local embeddings, and pgvector search
- Document summary, extracted fields, and Q&A
- Deadline alerts with manual creation and auto-detection
- Dashboard for document status, chunks, alerts, and failures
- Retry flow for failed document processing

## Tech Stack

- Frontend: React, Vite, Axios, React Router
- Backend: FastAPI, SQLAlchemy async, Alembic
- Database: PostgreSQL 16 with pgvector
- Jobs: Celery with Redis
- PDF processing: PyMuPDF
- Runtime: Docker Compose

## Project Structure

```text
backend/
  app/
    routers/      API routes
    services/     storage, email, AI helpers
    tasks/        Celery tasks
    main.py       FastAPI entrypoint
    worker.py     Celery app
  migrations/     Alembic migrations
frontend/
  src/
    api/          API client
    components/   shared layout
    pages/        app screens
docker-compose.yml
```

## Getting Started

Clone the repository:

```bash
git clone https://github.com/Swathi837/dociq_pdf.git
cd dociq_pdf
```

Create your local environment file:

```bash
cp .env.example .env
```

Start the app:

```bash
docker-compose up -d
```

Run migrations:

```bash
docker exec -it dociq_backend alembic upgrade head
```

Open the app:

```text
Frontend: http://localhost:5173
Backend docs: http://localhost:8000/docs
```

## Development Commands

```bash
docker-compose up -d
docker-compose logs -f backend celery_worker
docker-compose restart backend frontend celery_worker
docker exec -it dociq_backend alembic upgrade head
docker exec -it dociq_frontend sh -c "cd /app && npm install"
```

## Test Flow

1. Sign in or register.
2. Upload a small PDF.
3. Wait for the status to become `processed`.
4. Open the document detail page.
5. Review summary and extraction.
6. Ask a document question.
7. Create or auto-detect alerts.

## Notes

- Do not commit `.env`; it is ignored by Git.
- Uploaded PDFs are stored in `backend/uploads/` locally and are ignored by Git.
- The `chunks.embedding` vector dimension should stay at `384`.
- For fresh databases, make sure pgvector is enabled before using embeddings.
