# RAG Service - NITK Virtual Assistant

FastAPI-based REST API service for Retrieval-Augmented Generation (RAG) with entity extraction, temporal detection, and intelligent caching.

## Overview

The RAG Service is the core backend that powers the NITK Virtual Assistant. It combines vector search over a ChromaDB knowledge base with OpenAI's GPT models to provide accurate, context-aware responses about NITK.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │   Routes   │  │   Health   │  │   Stats    │           │
│  │  /query    │  │  /health   │  │  /stats    │           │
│  └──────┬─────┘  └────────────┘  └────────────┘           │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────────────────────────────────┐          │
│  │           RAGAssistant (Orchestrator)        │          │
│  └───┬──────────────────────────────────────┬───┘          │
│      │                                      │               │
│      ▼                                      ▼               │
│  ┌──────────────────┐            ┌──────────────────┐     │
│  │ Temporal         │            │  Cache-Safe      │     │
│  │ Query Path       │            │  Query Path      │     │
│  │                  │            │                  │     │
│  │ ┌──────────────┐ │            │ ┌──────────────┐ │     │
│  │ │ Perplexity   │ │            │ │ Cache Check  │ │     │
│  │ │ Client       │ │            │ └──────┬───────┘ │     │
│  │ └──────────────┘ │            │        │         │     │
│  │        ↓         │            │        ▼         │     │
│  │ [No Cache]       │            │ ┌──────────────┐ │     │
│  └────────┬─────────┘            │ │Vector Search │ │     │
│           │                      │ └──────┬───────┘ │     │
│           │                      │        ▼         │     │
│           │                      │ ┌──────────────┐ │     │
│           │                      │ │ Relevance    │ │     │
│           │                      │ │ Scoring      │ │     │
│           │                      │ └──────┬───────┘ │     │
│           │                      │        ▼         │     │
│           │                      │ ┌──────────────┐ │     │
│           │                      │ │ LLM Response │ │     │
│           │                      │ └──────┬───────┘ │     │
│           │                      │        ▼         │     │
│           │                      │ ┌──────────────┐ │     │
│           │                      │ │Cache Response│ │     │
│           │                      │ └──────────────┘ │     │
│           │                      └──────────────────┘     │
│           ▼                                               │
│  ┌──────────────────────────────────────────────┐        │
│  │        Unified Emotion Detection              │        │
│  │       (Content-based, Post-response)          │        │
│  └──────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. RAGAssistant (`core/rag.py`)
Main orchestrator that coordinates all services.

**Responsibilities:**
- Query routing (temporal vs. cache-safe)
- Cache management
- Response streaming
- Emotion detection

**Key Methods:**
```python
def query(question: str, response_format: str = "web") -> Generator[str, None, None]
def get_last_detected_emotion() -> str
def get_cache_stats() -> dict
```

### 2. Vector Search Service (`core/vector_search_service.py`)
Handles embedding generation and similarity search.

**Features:**
- Text preprocessing and normalization
- Sentence Transformer embeddings
- Entity-first search (filters by metadata first)
- Semantic search fallback

**Search Strategies:**
```python
# Entity-First Search (when person/org detected)
results = entity_first_search(collection, query, entity)

# Semantic Search (general queries)
results = semantic_search(collection, query)
```

### 3. Scoring Service (`core/scoring_service.py`)
Re-ranks search results based on multiple factors.

**Scoring Formula:**
```python
final_score = (
    vector_similarity * 0.5 +      # Semantic match
    entity_boost * 0.3 +            # Entity match bonus
    metadata_boost * 0.2            # Recency, author match
)
```

**Boost Factors:**
- Person match: +15%
- Organization match: +12%
- Event match: +10%
- Location match: +8%
- Recency: up to +5%

### 4. Entity Extractor (`core/entities.py`)
Identifies and matches entities in queries.

**Supported Entities:**
- **Persons:** Faculty, staff, notable alumni
- **Organizations:** Departments, clubs, committees
- **Locations:** Buildings, landmarks, cities
- **Events:** Conferences, fests, ceremonies

**Features:**
- spaCy NER for entity detection
- Fuzzy name matching (handles typos, abbreviations)
- Title normalization (Dr., Prof., etc.)

### 5. Temporal Detector (`core/temporal_detector.py`)
Identifies queries requiring current information.

**Temporal Keywords:**
- Time: "today", "now", "current", "latest"
- Events: "upcoming", "next", "recent"
- Status: "currently", "at present"

**Routing:**
- Temporal queries → Perplexity API (real-time)
- Static queries → RAG pipeline (cached)

### 6. Perplexity Client (`core/perplexity_client.py`)
Integrates Perplexity AI for temporal queries.

**Features:**
- Streaming responses
- Citation removal
- Format-aware prompts (web vs. voice)
- Timeout handling

### 7. Cache Manager (`core/cache.py`)
Manages response caching with TTL and size limits.

**Cache Strategy:**
```
Cache-Safe Queries:
✓ "Who is the director?"
✓ "What is NITK?"
✓ "Tell me about CSE department"

Temporal Queries (No Cache):
✗ "What events are happening today?"
✗ "Current weather in Surathkal"
✗ "Latest NITK news"
```

**Configuration:**
- Max age: 7 days
- Max size: 1 GB
- Cleanup: Every 24 hours

### 8. Query Formatter (`core/query_formatting.py`)
Formats responses for different interfaces.

**Format Types:**
- **Web:** Detailed, structured (150-300 words)
- **Voice:** Concise, conversational (50-80 words)

### 9. Text Processor (`core/text_processing.py`)
Text preprocessing and normalization utilities.

**Operations:**
- Lowercasing, whitespace normalization
- Stop word removal
- Punctuation handling
- Query expansion

## API Endpoints

### `POST /query`

Query the RAG system.

**Request:**
```json
{
  "question": "Who is the director of NITK?",
  "response_format": "web"
}
```

**Parameters:**
- `question` (required): User's question (max 1000 chars)
- `response_format` (optional): "web" or "voice" (default: "web")

**Response:**
```json
{
  "response": "The current Director of NITK is Prof. ...",
  "emotion": "neutral",
  "source": "rag",
  "cached": false,
  "timestamp": "2025-01-31T10:30:00"
}
```

**Response Fields:**
- `response`: The answer text
- `emotion`: Detected emotion (happy, sad, neutral, excited, etc.)
- `source`: "rag" or "perplexity"
- `cached`: Whether response came from cache
- `timestamp`: Query timestamp

**Streaming:**
The endpoint supports Server-Sent Events (SSE) for streaming responses:
```python
import requests

response = requests.post(
    "http://localhost:8000/query",
    json={"question": "Tell me about NITK", "response_format": "web"},
    stream=True
)

for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
    print(chunk, end='', flush=True)
```

---

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "NITK RAG Service",
  "version": "1.0.0",
  "features": [
    "emotion_detection",
    "caching",
    "temporal_queries",
    "multi_format"
  ],
  "database": {
    "status": "connected",
    "collection": "nitk_knowledgebase",
    "documents": 1234
  }
}
```

---

### `GET /stats`

Service statistics.

**Response:**
```json
{
  "queries_total": 5678,
  "cache_hits": 3421,
  "cache_misses": 2257,
  "cache_hit_rate": 0.602,
  "avg_response_time_ms": 234,
  "temporal_queries": 456,
  "uptime_seconds": 86400
}
```

---

## Configuration

### Config File: `core/config.py`

**Key Settings:**
```python
@dataclass
class Config:
    # Debug and logging
    debug: bool = True
    log_level: str = "INFO"

    # Database
    chroma_path: Path = Path("../outputs/chroma_db")
    COLLECTION_NAME: str = "nitk_knowledgebase"

    # AI Models
    embedding_model: str = 'all-MiniLM-L6-v2'
    openai_model: str = "gpt-4o-mini"
    temperature: float = 0.4

    # Search parameters
    DEFAULT_RESULTS: int = 5
    PERSON_BOOST: float = 0.15
    ORG_BOOST: float = 0.12

    # Cache
    cache_max_age_days: int = 7
    cache_max_size_gb: int = 1

    # Perplexity
    perplexity_enabled: bool = True
    perplexity_model: str = "sonar"

    # CORS
    cors_allow_origins: List[str] = ["*"]  # Restrict in production!
```

**Environment Variables:**
See [../.env.example](../.env.example) for all configuration options.

---

## Running the Service

### Development Mode

```bash
cd rag-service
python main.py
```

Service will start on `http://localhost:8000` with:
- Auto-reload enabled
- Debug logging
- CORS enabled for all origins

### Production Mode

1. **Update configuration:**
   ```bash
   # .env
   DEBUG=False
   LOG_LEVEL=INFO
   CORS_ALLOW_ORIGINS=https://your-domain.com
   ```

2. **Run with Gunicorn:**
   ```bash
   gunicorn main:app \
     --workers 4 \
     --worker-class uvicorn.workers.UvicornWorker \
     --bind 0.0.0.0:8000 \
     --log-level info
   ```

3. **Or use Docker:**
   ```dockerfile
   FROM python:3.10-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

### Network Access

To make the service accessible on local network:

```python
# main.py already configured for network access
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # Listen on all interfaces
        port=8000,
        reload=True
    )
```

The service will print network information on startup:
```
🚀 RAG Service Network Information
📡 Primary IP: http://192.168.1.100:8000
🤖 For robot client: RAG_SERVICE_HOST=192.168.1.100
```

---

## Usage Examples

### Python Client

```python
import requests

# Simple query
response = requests.post(
    "http://localhost:8000/query",
    json={
        "question": "Who is the director of NITK?",
        "response_format": "web"
    }
)
data = response.json()
print(data['response'])
print(f"Emotion: {data['emotion']}")
```

### cURL

```bash
# Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is NITK known for?", "response_format": "web"}'

# Health check
curl http://localhost:8000/health

# Stats
curl http://localhost:8000/stats
```

### JavaScript/TypeScript

```javascript
async function queryRAG(question, format = 'web') {
  const response = await fetch('http://localhost:8000/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, response_format: format })
  });
  return await response.json();
}

const result = await queryRAG("Tell me about CSE department");
console.log(result.response);
```

---

## System Prompts

### Web Format Prompt
```
RESPONSE FORMAT FOR WEB INTERFACE:
Provide structured, informative responses that are detailed but concise.

Structure: Use clear sections and bullet points for readability
Length: 2-4 paragraphs (150-300 words)
Detail: Include key facts, dates, names, and context
```

### Voice Format Prompt
```
RESPONSE FORMAT FOR VOICE INTERFACE:
Respond in a conversational, voice-friendly manner.

Length: 50-80 words max
Style: Simple sentences, natural for text-to-speech
Focus: Direct answer without long lists
```

---

## Error Handling

### Error Responses

```json
{
  "error": "Query too long",
  "details": "Maximum query length is 1000 characters",
  "status_code": 400
}
```

### Common Errors

| Error | Code | Cause | Solution |
|-------|------|-------|----------|
| Query too long | 400 | Query > 1000 chars | Shorten query |
| Invalid format | 400 | format not "web"/"voice" | Use valid format |
| Database error | 500 | ChromaDB connection | Check DB path |
| OpenAI API error | 500 | API key invalid | Check .env |
| Timeout | 504 | Query takes > 60s | Retry or check logs |

---

## Performance

### Optimization Tips

1. **Use appropriate models:**
   - Development: `gpt-4o-mini` (fast, cheap)
   - Production: `gpt-4o` (better quality)

2. **Enable caching:**
   - Reduces API calls by ~60%
   - Configure `cache_max_age_days` based on data update frequency

3. **Tune search parameters:**
   ```python
   # Faster, less accurate
   hnsw_config = {"ef_search": 50, "M": 32}

   # Slower, more accurate
   hnsw_config = {"ef_search": 200, "M": 128}
   ```

4. **Adjust result count:**
   ```python
   DEFAULT_RESULTS = 3  # Faster, less context
   DEFAULT_RESULTS = 10  # Slower, more context
   ```

### Performance Benchmarks

*Measured on: Intel i7, 16GB RAM, SSD*

| Operation | Avg Time | Notes |
|-----------|----------|-------|
| Embedding generation | 50ms | For query |
| Vector search | 20ms | 1000 documents |
| Entity extraction | 30ms | spaCy NER |
| LLM response (streaming) | 2-5s | OpenAI API |
| Cache hit | 5ms | Instant response |
| Total (cached) | ~10ms | |
| Total (uncached) | ~2.5s | |

---

## Troubleshooting

### Service won't start

**Check logs:**
```bash
tail -f ../logs/rag_service_*.log
```

**Common issues:**
1. ChromaDB path incorrect
2. OpenAI API key missing
3. Port 8000 already in use

### Slow responses

1. Check OpenAI API latency
2. Verify database size (optimize if > 100K docs)
3. Monitor system resources
4. Check network latency (for remote DB)

### Poor answer quality

1. Verify relevant data in database
2. Check entity extraction working
3. Adjust relevance scoring weights
4. Review system prompts
5. Try different OpenAI model

### Cache issues

```python
# Clear cache manually
from core.cache import CacheManager
cache = CacheManager(config, logger)
cache.clear_cache()
```

---

## Development

### Adding New Features

1. **New entity type:**
   - Add to `config/*.json`
   - Update `QueryIntent` enum
   - Add extraction logic in `entities.py`

2. **New search strategy:**
   - Implement in `vector_search_service.py`
   - Add scoring logic in `scoring_service.py`

3. **New endpoint:**
   - Add route in `api/routes.py`
   - Update OpenAPI docs
   - Add tests

### Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Load testing
locust -f tests/load/locustfile.py
```

---

## TODO: Future Improvements

### High Priority
- [ ] Add authentication/authorization (JWT tokens)
- [ ] Implement rate limiting per client
- [ ] Add request validation with Pydantic models
- [ ] Improve error messages (more specific error codes)
- [ ] Add query timeout handling

### Medium Priority
- [ ] Implement query expansion using synonyms
- [ ] Add A/B testing framework for prompt variations
- [ ] Create admin dashboard for monitoring
- [ ] Add support for conversation history (multi-turn)
- [ ] Implement semantic deduplication of search results

### Low Priority
- [ ] Add GraphQL API option
- [ ] Implement webhook notifications
- [ ] Add real-time database updates (watch for changes)
- [ ] Create plugin system for custom search strategies
- [ ] Add federated search across multiple databases

### Code Quality
- [ ] Add comprehensive unit tests (target 80% coverage)
- [ ] Improve type hints throughout codebase
- [ ] Extract magic numbers to constants
- [ ] Refactor emotion detection to config-driven approach
- [ ] Use template system (Jinja2) for system prompts

---

## API Documentation

Full OpenAPI documentation available at `http://localhost:8000/docs` when service is running.

---

**Next Steps:** Once the RAG service is running, you can connect clients like [web-ui](../web-ui/README.md) or [robot](../robot/README.md).
