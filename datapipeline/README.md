# Data Pipeline - NITK Virtual Assistant

A 6-step sequential data processing pipeline for ingesting, chunking, and loading data into the ChromaDB vector database.

## Overview

The data pipeline transforms raw data from multiple sources (Instagram, LinkedIn, Website) into semantically chunked documents with embeddings stored in ChromaDB for efficient RAG retrieval.

## Pipeline Architecture

```
┌─────────────────┐
│  Raw Data       │  Instagram posts, LinkedIn content, Website articles
│  (Multiple      │
│   Formats)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  STEP 1:        │  Standardize to common JSON format
│  Standardize    │  • Extract metadata
│                 │  • Normalize fields
│                 │  • Entity extraction
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  STEP 2:        │  Semantic chunking with overlap
│  Chunk          │  • Sentence boundary detection
│                 │  • Clause splitting for long sentences
│                 │  • Metadata preservation
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  STEP 3:        │  Generate embeddings and load
│  Load to DB     │  • Sentence Transformers embedding
│                 │  • ChromaDB HNSW indexing
│                 │  • Metadata storage
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  STEP 4:        │  Quality assurance
│  Validate       │  • Record count verification
│                 │  • Test queries
│                 │  • Embedding visualization
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  STEP 5:        │  Production querying
│  Query          │  • Entity-first search
│                 │  • Semantic search fallback
│                 │  • Relevance scoring
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  STEP 6:        │  Analytics and reporting
│  Export         │  • CSV export
│                 │  • Query results
│                 │  • Performance metrics
└─────────────────┘
```

## Step-by-Step Guide

### STEP 1: Standardization

Convert data from different sources into a common JSON format.

**Files:**
- `Step 1. Create Standard JSON from Instagram.py`
- `Step 1. Create Standard JSON from LinkedIn.py`
- `Step 1. Create Standard JSON from Web.py`

**Standard JSON Format:**
```json
{
  "source_id": "unique-identifier",
  "created_date": "YYYY-MM-DD",
  "author_name": "Author Name",
  "platform": "instagram|linkedin|website",
  "content": {
    "text": "Main content text",
    "entities": {
      "persons": ["Dr. John Doe"],
      "organizations": ["NITK"],
      "locations": ["Surathkal"]
    }
  },
  "hashtags": ["#NITK", "#Engineering"],
  "mentions": ["@user"],
  "source_url": "https://..."
}
```

**Usage:**
```bash
python "Step 1. Create Standard JSON from Instagram.py"
# Output: outputs/instagram/processed_instagram.json

python "Step 1. Create Standard JSON from LinkedIn.py"
# Output: outputs/linkedin/processed_linkedin.json

python "Step 1. Create Standard JSON from Web.py"
# Output: outputs/website/processed_website.json
```

**Configuration:**
Edit the `INPUT_DIR` and `OUTPUT_DIR` in each script.

---

### STEP 2: Chunking

Split standardized JSON into semantically meaningful chunks with metadata.

**File:** `Step 2. Chunk into JSONL.py`

**Features:**
- **Semantic Chunking:** Uses spaCy for sentence detection
- **Target Size:** 512 characters (configurable)
- **Overlap:** 100 characters between chunks
- **Smart Splitting:** Respects sentence boundaries and clauses
- **Metadata Preservation:** Each chunk carries source metadata

**Configuration:**
```python
class Config:
    INPUT_DIR = Path("outputs/instagram")
    OUTPUT_DIR = Path("outputs/instagram/output-chunks")
    CHUNK_TARGET_SIZE = 512
    CHUNK_OVERLAP = 100
    MIN_SENTENCES_PER_CHUNK = 2
```

**Usage:**
```bash
python "Step 2. Chunk into JSONL.py"
```

**Output Format (JSONL):**
```jsonl
{"text": "Chunk content...", "metadata": {"source_id": "...", "created_date": "...", "author": "...", "platform": "...", "chunk_position": 1}}
{"text": "Another chunk...", "metadata": {...}}
```

**TODO:**
- Add cross-platform path support (use forward slashes)
- Add file size validation before processing
- Extract clause splitting to separate testable method
- Add progress estimation for large files

---

### STEP 3: ChromaDB Loading

Generate embeddings and load chunks into ChromaDB vector database.

**File:** `Step 3. Chroma Loader.py`

**Features:**
- **Embedding Model:** `all-MiniLM-L6-v2` (384-dimensional)
- **Vector Index:** HNSW for fast approximate nearest neighbor search
- **Batch Processing:** Efficient bulk loading
- **Metadata Indexing:** Searchable by source, author, date, platform

**HNSW Configuration:**
```python
hnsw_config = {
    "ef_construction": 450,  # Build quality (higher = better, slower)
    "ef_search": 100,        # Search quality
    "M": 64,                 # Connectivity (higher = more memory, faster search)
    "num_threads": 1         # CPU threads
}
```

**Usage:**
```bash
python "Step 3. Chroma Loader.py"
```

**Output:** ChromaDB database in `outputs/chroma_db/`

**TODO:**
- Add duplicate detection before loading
- Implement incremental updates (add new data without full reload)
- Add embedding validation (detect degenerate embeddings)
- Add rollback capability for failed loads

---

### STEP 4: Validation

Quality assurance and testing of the loaded database.

**Files:**
- `Step 4a. Chroma Record Check.py` - Verify record count and metadata
- `Step 4b. Chroma Test Query.py` - Run test queries
- `Step 4c. Visualize Embeddings.py` - Visualize embedding space (t-SNE/UMAP)

**Step 4a: Record Check**
```bash
python "Step 4a. Chroma Record Check.py"
```
Outputs:
- Total record count
- Records by platform
- Records by author
- Date range coverage

**Step 4b: Test Queries**
```bash
python "Step 4b. Chroma Test Query.py"
```
Tests:
- Sample queries for each entity type (person, org, location, event)
- Relevance score distribution
- Response time measurements

**Step 4c: Embedding Visualization**
```bash
python "Step 4c. Visualize Embeddings.py"
```
Generates:
- 2D/3D plots of embedding space
- Cluster visualization by platform/author
- Outlier detection

**TODO:**
- Add automated quality metrics (recall@k, precision@k)
- Add semantic coherence tests
- Create regression test suite

---

### STEP 5: Query System

Production-ready query system with entity extraction and relevance scoring.

**File:** `Step 5. Query Chroma.py` (619 lines)

**Query Flow:**
```
Query → Preprocessing → Entity Detection → Search Strategy Selection
                                                      ↓
                                          ┌───────────┴───────────┐
                                          ▼                       ▼
                                   Entity-First Search    Semantic Search
                                          │                       │
                                          └───────────┬───────────┘
                                                      ▼
                                              Relevance Scoring
                                                      ▼
                                              Reranking & Filtering
                                                      ▼
                                              Top-k Results
```

**Entity-First Search:**
- Detects persons, organizations, locations, events in query
- Filters database by entity metadata first
- Then applies vector similarity
- Boosts results containing matched entities

**Semantic Search:**
- Fallback when no entities detected
- Pure vector similarity with cosine distance
- Uses query expansion techniques

**Relevance Scoring:**
```python
final_score = (
    vector_similarity * 0.5 +
    entity_match_score * 0.3 +
    metadata_boost * 0.2
)
```

**Usage:**
```python
from query import query_chroma

results = query_chroma(
    query="Who is the director of NITK?",
    top_k=5,
    entity_boost=True
)
```

**TODO:**
- Add query expansion using synonyms
- Implement query caching
- Add semantic deduplication of results
- Add explainability (why this result was returned)

---

### STEP 6: Export & Analytics

Export query results and generate analytics.

**File:** `Step 6. Export CSV.py`

**Features:**
- Export to CSV for external analysis
- Aggregate statistics by platform, author, date
- Query performance metrics
- Entity co-occurrence analysis

**Usage:**
```bash
python "Step 6. Export CSV.py"
```

**Output Files:**
- `results/query_results.csv` - Individual query results
- `results/analytics.csv` - Aggregate statistics
- `results/performance.csv` - Query timing metrics

**TODO:**
- Add JSON export option
- Add interactive dashboards (Plotly/Streamlit)
- Add automated report generation

---

## Supporting Files

### `query.py`
Main query engine used by RAG service. Contains:
- `VectorSearchService` - Embedding and search
- `ScoringService` - Relevance scoring
- `EntityExtractor` - Entity recognition
- `TemporalDetector` - Time-based query detection

### `where-filtering.py` / `where_filtering.ipynb`
Advanced ChromaDB filtering examples:
- Metadata filtering
- Date range queries
- Multi-condition filtering
- Performance comparisons

### `requirements.txt`
Pipeline-specific dependencies (if different from main requirements)

---

## Configuration

### Chunking Parameters

**Chunk Size:** 512 characters
- Too small: Loss of context, many chunks
- Too large: Irrelevant content in chunks, poor retrieval
- Sweet spot: 400-600 characters

**Overlap:** 100 characters
- Prevents information loss at chunk boundaries
- Helps with queries that span chunk boundaries
- Trade-off: More chunks, more storage

**Min Sentences:** 2
- Ensures chunks have complete thoughts
- Prevents single-word or fragment chunks

### Embedding Model

**Current:** `all-MiniLM-L6-v2`
- Dimensions: 384
- Speed: Fast
- Quality: Good for general text
- Size: ~90MB

**Alternatives:**
- `all-mpnet-base-v2` - Higher quality, slower (768 dims)
- `multi-qa-MiniLM-L6-cos-v1` - Optimized for Q&A
- `paraphrase-multilingual-MiniLM-L12-v2` - Multi-language support

### ChromaDB HNSW

**ef_construction: 450**
- Higher = better index quality, slower build
- Range: 100-500
- Use 450+ for production databases

**ef_search: 100**
- Higher = better search accuracy, slower queries
- Range: 50-200
- Use 100+ for high-quality results

**M: 64**
- Higher = more memory, faster search
- Range: 16-128
- Use 64 for balanced performance

---

## Data Sources

### Instagram
- Official NITK Instagram account posts
- Event announcements
- Photo descriptions
- Hashtags and mentions

### LinkedIn
- NITK official page updates
- Faculty posts
- Achievement announcements
- Alumni updates

### Website
- nitk.ac.in content
- Department pages
- Faculty profiles
- Event calendars

---

## Troubleshooting

### Common Issues

**1. Out of Memory during chunking**
- Reduce batch size in processing
- Process files one at a time
- Increase system swap space

**2. spaCy model not found**
```bash
python -m spacy download en_core_web_sm
```

**3. ChromaDB collection already exists**
- Delete existing collection or use different name
- Use `get_or_create_collection()` instead

**4. Encoding errors**
- Ensure UTF-8 encoding in all files
- Use `encoding='utf-8'` in file operations

**5. Slow embedding generation**
- Use CPU with `device='cpu'` (default)
- Or GPU with `device='cuda'` if available
- Batch process instead of one-by-one

### Performance Tips

**Chunking:**
- Disable debug logging for large files
- Use SSD for input/output directories
- Process in parallel for multiple sources

**Loading:**
- Batch embeddings (32-64 chunks at a time)
- Use persistent client instead of ephemeral
- Pre-allocate ChromaDB storage

**Querying:**
- Cache frequent queries
- Use entity-first search when possible
- Tune HNSW parameters for speed vs. accuracy

---

## Best Practices

### Data Quality

1. **Validate input data:**
   - Check for empty fields
   - Verify date formats
   - Normalize text encoding

2. **Entity extraction:**
   - Use consistent entity formats
   - Validate against known entities
   - Handle abbreviations and aliases

3. **Metadata consistency:**
   - Use standard platforms names
   - Normalize author names
   - Consistent date formats (YYYY-MM-DD)

### Pipeline Execution

1. **Version control:**
   - Tag data pipeline runs
   - Keep source data in separate repo (large files)
   - Version ChromaDB snapshots

2. **Incremental updates:**
   - Add new data without full reload
   - Track processed source IDs
   - Implement change detection

3. **Testing:**
   - Test with small dataset first
   - Validate output at each step
   - Run QA queries before production

---

## TODO: Future Improvements

### High Priority
- [ ] Add cross-platform path handling (Windows/Linux compatibility)
- [ ] Implement incremental data updates
- [ ] Add data validation at each pipeline step
- [ ] Create automated regression tests

### Medium Priority
- [ ] Add support for PDF document ingestion
- [ ] Implement multi-language text processing
- [ ] Add deduplication logic
- [ ] Create pipeline orchestration (Airflow/Prefect)

### Low Priority
- [ ] Add real-time data ingestion (webhooks)
- [ ] Implement A/B testing for chunking strategies
- [ ] Add embedding model comparison tools
- [ ] Create interactive data exploration UI

---

## Performance Benchmarks

*Measured on: [Add your system specs]*

| Step | Input Size | Processing Time | Output Size |
|------|-----------|----------------|-------------|
| Step 1: Instagram | 500 posts | ~2 min | 2.5 MB JSON |
| Step 2: Chunking | 2.5 MB JSON | ~5 min | 8 MB JSONL (1200 chunks) |
| Step 3: Loading | 1200 chunks | ~3 min | 150 MB ChromaDB |
| Step 4: Validation | 1200 records | ~30 sec | - |
| Step 5: Query | - | ~200ms/query | - |

---

**Next Steps:** Once data is loaded, proceed to [rag-service/](../rag-service/README.md) to start the RAG API service.
