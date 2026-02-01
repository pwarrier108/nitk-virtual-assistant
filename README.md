# NITK Virtual Assistant

An AI-powered virtual assistant system for NITK (National Institute of Technology Karnataka) featuring multi-modal interaction through web UI, voice interface, and robotic embodiment.

## Overview

The NITK Virtual Assistant is a comprehensive Retrieval-Augmented Generation (RAG) system that combines:
- **Vector search** over NITK knowledge base
- **AI-powered response generation** with OpenAI GPT
- **Multi-language support** (English, Hindi, Kannada, Tamil, Telugu, Malayalam)
- **Voice interaction** with Text-to-Speech
- **Physical robot interface** (TonyPi robot with emotion expressions)
- **Web-based UI** for easy access

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Sources                              │
│  (Instagram, LinkedIn, NITK Website, Events, Faculty DB)     │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              Data Pipeline (6 Steps)                         │
│  Standardize → Chunk → Load → Validate → Query → Export     │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│            ChromaDB Vector Database                          │
│     (Embeddings with HNSW for fast similarity search)       │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│           RAG Service (FastAPI)                              │
│  • Vector Search  • Entity Extraction                        │
│  • Relevance Scoring  • Temporal Detection                   │
│  • Response Caching  • Emotion Detection                     │
└─────────┬────────────────┬──────────────┬───────────────────┘
          │                │              │
          ▼                ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌──────────────┐
│   Web UI    │  │   Robot     │  │  API Clients │
│ (Streamlit) │  │  (TonyPi)   │  │   (Custom)   │
└─────────────┘  └─────────────┘  └──────────────┘
```

## Project Structure

```
nitkmodular/
├── datapipeline/          # Data ingestion and processing (6-step pipeline)
├── rag-service/           # Core RAG API service (FastAPI)
├── web-ui/                # Web interface (Streamlit)
├── robot/                 # Robot controller and voice assistant
├── config/                # Entity data (persons, orgs, locations, events)
├── audio/                 # Audio assets and TTS module
├── outputs/               # Vector DB and processed data
├── cache/                 # Response and translation cache
├── logs/                  # Application logs
├── results/               # Query results and analytics
├── tests/                 # Test scripts
├── .env.example           # Environment variables template
└── requirements.txt       # Python dependencies
```

## Features

### Core Capabilities
- **Retrieval-Augmented Generation (RAG):** Combines vector search with AI generation for accurate, context-aware responses
- **Entity Recognition:** Identifies and matches persons, organizations, locations, and events
- **Temporal Awareness:** Detects time-sensitive queries and routes to Perplexity for current information
- **Smart Caching:** Caches static responses, avoids caching temporal queries
- **Multi-format Responses:** Adapts response length and style for web vs. voice interfaces

### Multi-Modal Interaction
- **Web Interface:** Full-featured UI with translation, audio playback, and cache management
- **Voice Interface:** Speech recognition and synthesis for natural conversation
- **Robot Interface:** Physical TonyPi robot with emotion expressions and gestures

### Advanced Features
- **Multi-language Translation:** Real-time translation to 6 Indian languages
- **Emotion Detection:** Content-based emotion detection from responses
- **Context-Aware Follow-ups:** Maintains conversation context
- **Relevance Scoring:** Boosts results based on entity matching and metadata
- **Semantic Chunking:** Intelligent text segmentation for optimal embeddings

## Quick Start

### Prerequisites

- Python 3.10+
- Git
- 8GB+ RAM (for embedding models)
- OpenAI API key
- (Optional) Perplexity API key for temporal queries
- (Optional) Google Cloud credentials for advanced TTS

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd nitkmodular
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements-14-07-2025.txt
   ```

4. **Download spaCy model**
   ```bash
   python -m spacy download en_core_web_sm
   ```

5. **Configure environment**
   ```bash
   # Copy the example file
   cp .env.example .env

   # Edit .env and add your API keys
   # Required: OPENAI_API_KEY
   # Optional: PERPLEXITY_API_KEY
   ```

6. **Set up the vector database**

   If you have existing data:
   ```bash
   cd datapipeline
   python "Step 1. Create Standard JSON from Instagram.py"
   python "Step 2. Chunk into JSONL.py"
   python "Step 3. Chroma Loader.py"
   ```

   Or use the pre-built database in `outputs/chroma_db/` (if provided)

### Running the Services

#### Option 1: RAG Service + Web UI (Recommended for testing)

```bash
# Terminal 1: Start RAG service
cd rag-service
python main.py

# Terminal 2: Start Web UI
cd web-ui
streamlit run main.py
```

Then open your browser to `http://localhost:8501`

#### Option 2: RAG Service + Robot (for physical robot)

```bash
# Terminal 1: Start RAG service
cd rag-service
python main.py

# Terminal 2: Start robot (on TonyPi hardware)
cd robot
python main.py
```

#### Option 3: Standalone API Service

```bash
cd rag-service
python main.py
```

API will be available at `http://localhost:8000`

## Usage

### Web UI

1. Enter your question in natural language
2. Select language for response (optional translation)
3. Click "Submit" or press Enter
4. View text response and play audio if needed

### API Endpoint

```bash
# Query endpoint
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Who is the director of NITK?", "response_format": "web"}'

# Health check
curl http://localhost:8000/health
```

### Robot Interface

1. Say the wake word ("Hello HiWonder" or configured phrase)
2. Wait for acknowledgment
3. Ask your question
4. Robot responds with speech and gestures

## Data Pipeline

The system includes a 6-step data pipeline for processing information:

1. **Standardization:** Convert from various sources (Instagram, LinkedIn, Web) to standard JSON
2. **Chunking:** Split content into semantic chunks with overlap
3. **Loading:** Generate embeddings and load into ChromaDB
4. **Validation:** Verify records and test queries
5. **Querying:** Search with entity extraction and relevance scoring
6. **Export:** Export results to CSV for analysis

See [datapipeline/README.md](datapipeline/README.md) for details.

## Configuration

### Key Configuration Files

- `.env` - Environment variables (API keys, service settings)
- `rag-service/core/config.py` - RAG service configuration
- `config/*.json` - Entity databases (persons, organizations, locations, events)

### Environment Variables

See [.env.example](.env.example) for all available configuration options.

### Important Settings

```python
# RAG Service
RAG_SERVICE_HOST=0.0.0.0      # Allow network access
RAG_SERVICE_PORT=8000

# AI Models
OPENAI_MODEL=gpt-4o-mini      # Or gpt-4o for better quality
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Cache
CACHE_MAX_AGE_DAYS=7
CACHE_MAX_SIZE_GB=1
```

## API Documentation

### Endpoints

#### `POST /query`
Query the RAG system

**Request:**
```json
{
  "question": "What is NITK?",
  "response_format": "web"  // "web" or "voice"
}
```

**Response:**
```json
{
  "response": "NITK (National Institute of Technology Karnataka)...",
  "emotion": "neutral",
  "source": "rag",
  "cached": false
}
```

#### `GET /health`
Health check endpoint

#### `GET /stats`
Service statistics

See [rag-service/README.md](rag-service/README.md) for complete API documentation.

## Development

### Project Components

- **[datapipeline/](datapipeline/)** - Data processing pipeline
- **[rag-service/](rag-service/)** - FastAPI service
- **[web-ui/](web-ui/)** - Streamlit web interface
- **[robot/](robot/)** - Robot controller

Each component has its own README with detailed documentation.

### Adding New Data Sources

1. Create standardization script in `datapipeline/`
2. Output to standard JSON format:
   ```json
   {
     "source_id": "unique-id",
     "created_date": "YYYY-MM-DD",
     "author_name": "Author",
     "platform": "source",
     "content": {
       "text": "content",
       "entities": {}
     }
   }
   ```
3. Run chunking and loading pipeline

### Testing

```bash
# Web UI test
cd tests
python web_ui_test.py

# RAG service test
python rag_stt_test.py

# Robot test (requires hardware)
python robot_test.py
```

## Troubleshooting

### Common Issues

1. **RAG Service not accessible**
   - Check if service is running on port 8000
   - Verify firewall settings
   - Check `.env` for correct `RAG_SERVICE_HOST` and `RAG_SERVICE_PORT`

2. **OpenAI API errors**
   - Verify `OPENAI_API_KEY` in `.env`
   - Check API quota and billing

3. **ChromaDB errors**
   - Ensure `outputs/chroma_db/` exists and has data
   - Re-run data pipeline if needed

4. **spaCy model not found**
   - Run: `python -m spacy download en_core_web_sm`

5. **Translation errors**
   - Check internet connection (uses Google Translate)
   - Verify translation provider in config

6. **Robot not responding**
   - Check hardware connections (TonyPi)
   - Verify audio device path in config
   - Test wake word sensitivity setting

### Logs

Check logs in the `logs/` directory:
- `rag_service_*.log` - RAG service logs
- `web_ui.log` - Web UI logs
- Robot logs output to console

## Performance

### Optimization Tips

1. **Use appropriate models:**
   - Development: `gpt-4o-mini` (faster, cheaper)
   - Production: `gpt-4o` (better quality)

2. **Enable caching:**
   - Caching reduces API calls by ~60% for common queries
   - Configure `CACHE_MAX_AGE_DAYS` based on data update frequency

3. **Tune ChromaDB:**
   - Adjust HNSW parameters in `config.py` for speed vs. accuracy tradeoff
   - Current settings optimized for 10K+ documents

4. **Batch processing:**
   - Process multiple queries in parallel when possible
   - Use async API calls in custom clients

## Security

### Best Practices

1. **Never commit secrets:**
   - Use `.env` file (in `.gitignore`)
   - Use environment variables in production
   - Rotate API keys regularly

2. **Restrict CORS in production:**
   - Change `CORS_ALLOW_ORIGINS=*` to specific domains
   - Set `CORS_ALLOW_CREDENTIALS=false` if not needed

3. **Disable debug mode:**
   - Set `DEBUG=False` in production
   - Use `detailed_error_responses: false` in config

4. **Secure the API:**
   - Add authentication for production deployment
   - Use HTTPS for external access
   - Rate limit API requests

## License

[Add your license here]

## Contributors

See [credits for development.txt](credits for development.txt)

## Support

For issues, questions, or contributions:
1. Check existing documentation
2. Review logs for error messages
3. Create an issue with detailed description

## Roadmap

See TODO comments in code for planned improvements:
- [ ] Add authentication to RAG service
- [ ] Implement real-time data updates
- [ ] Add support for more languages
- [ ] Improve emotion detection accuracy
- [ ] Add admin dashboard
- [ ] Implement query analytics
- [ ] Add A/B testing for response quality

---

**Built with ❤️ for NITK Community**
