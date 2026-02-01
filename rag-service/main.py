# Standard library imports
import logging
import os
import socket
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

# Third-party imports
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment from parent directory
load_dotenv(Path(__file__).parent.parent / '.env')

# Local application imports
from api.routes import router
from core.cache import CacheManager
from core.config import Config
from core.entities import EntityExtractor, NameMatcher
from core.rag import RAGAssistant

warnings.filterwarnings("ignore", message=".*torch.classes.*")
os.environ["ANONYMIZED_TELEMETRY"] = "False" # Disable ChromaDB telemetry

# Global variables
assistant: RAGAssistant = None
logger: logging.Logger = None
config: Config = None

def get_local_ip() -> str:
    """Get the local IP address of the machine."""
    try:
        # Connect to a remote address to determine local IP
        # This doesn't actually send data, just determines routing
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        return local_ip
    except Exception:
        # Fallback to hostname resolution
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return local_ip
        except Exception:
            return "127.0.0.1"

def get_all_network_interfaces() -> list:
    """Get all available network interfaces and their IPs."""
    interfaces = []
    try:
        hostname = socket.gethostname()
        # Get all IP addresses associated with the hostname
        addr_info = socket.getaddrinfo(hostname, None)
        ips = set()
        for info in addr_info:
            ip = info[4][0]
            if not ip.startswith('127.') and ':' not in ip:  # Skip localhost and IPv6
                ips.add(ip)
        
        # Add the primary interface
        primary_ip = get_local_ip()
        ips.add(primary_ip)
        
        return sorted(list(ips))
    except Exception:
        return [get_local_ip()]

def setup_logger(config: Config) -> logging.Logger:
    """Setup logging for the service."""
    logging.getLogger().setLevel(logging.DEBUG if config.debug else logging.INFO)
    logger = logging.getLogger('rag-service')
    
    if logger.handlers:
        logger.handlers.clear()
        
    logger.setLevel(logging.DEBUG if config.debug else logging.INFO)
    
    # Ensure all required directories exist (same as RAGAssistant.setup_dirs())
    dirs = [
        config.chroma_path,
        config.log_path,
        config.results_path,
        config.cache_dir,
        config.cache_dir / "llm"
    ]
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # File handler
    log_file = config.log_path / f"rag_service_{config.log_file}"
    file_handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler for debug mode
    if config.debug:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger

def initialize_rag_assistant(config: Config) -> tuple[RAGAssistant, logging.Logger]:
    """Initialize RAG assistant and supporting services."""
    logger = setup_logger(config)
    logger.info("Initializing RAG service components")
    
    try:
        # Initialize supporting services
        cache_manager = CacheManager(config, logger)
        name_matcher = NameMatcher(config)
        entity_extractor = EntityExtractor(config)
        
        # Initialize RAG assistant (translation/TTS now handled by clients)
        assistant = RAGAssistant(
            config=config,
            logger=logger,
            name_matcher=name_matcher,
            entity_extractor=entity_extractor,
            cache_manager=cache_manager
        )
        
        logger.info("RAG service initialization completed successfully")
        return assistant, logger
        
    except Exception as e:
        logger.error(f"Failed to initialize RAG service: {str(e)}", exc_info=True)
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global assistant, logger, config
    
    # Startup
    try:
        config = Config()
        assistant, logger = initialize_rag_assistant(config)
        logger.info("RAG service started successfully")
        yield
    except Exception as e:
        print(f"Failed to start RAG service: {str(e)}")
        raise
    finally:
        # Shutdown
        if logger:
            logger.info("RAG service shutting down")

def create_app(config: Config) -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=config.api_title,
        description=config.api_description,
        version=config.api_version,
        lifespan=lifespan
    )

    # Add CORS middleware for local network access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_allow_origins,
        allow_credentials=config.cors_allow_credentials,
        allow_methods=config.cors_allow_methods,
        allow_headers=config.cors_allow_headers,
    )

    # Include routes
    app.include_router(router)
    
    return app

def print_network_info(host: str, port: int):
    """Print network information for easy client setup."""
    print("\n" + "="*60)
    print("🚀 RAG Service Network Information")
    print("="*60)
    
    if host == "0.0.0.0":
        # Get actual IP addresses
        primary_ip = get_local_ip()
        all_ips = get_all_network_interfaces()
        
        print(f"📡 Service is accessible on ALL network interfaces:")
        print(f"   Primary IP: http://{primary_ip}:{port}")
        
        if len(all_ips) > 1:
            print(f"   Alternative IPs:")
            for ip in all_ips:
                if ip != primary_ip:
                    print(f"     - http://{ip}:{port}")
        
        print(f"\n🤖 For robot client configuration:")
        print(f"   RAG_SERVICE_HOST={primary_ip}")
        print(f"   RAG_SERVICE_PORT={port}")
        print(f"   Full URL: http://{primary_ip}:{port}")
        
        print(f"\n🌐 API Endpoints:")
        print(f"   Health Check: http://{primary_ip}:{port}/health")
        print(f"   Query: http://{primary_ip}:{port}/query")
        print(f"   Stats: http://{primary_ip}:{port}/stats")
        
    else:
        print(f"📡 Service URL: http://{host}:{port}")
    
    print("="*60 + "\n")

# Create FastAPI app with config
config = Config()
app = create_app(config)

if __name__ == "__main__":
    import uvicorn
    
    # Print network information before starting
    print_network_info(config.server_host, config.server_port)
    
    # Show actual IP instead of 0.0.0.0 for clarity
    display_host = get_local_ip() if config.server_host == "0.0.0.0" else config.server_host
    
    print(f"Starting RAG service...")
    print(f"Primary IP: {display_host}")
    print(f"Port: {config.server_port}")
    print(f"Debug: {config.debug}")
    print(f"Service will be accessible at: http://{display_host}:{config.server_port}")
    
    uvicorn.run(
        "main:app",
        host=config.server_host,
        port=config.server_port,
        reload=config.server_reload,
        log_level=config.server_log_level
    )