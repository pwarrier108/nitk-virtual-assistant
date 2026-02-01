# Standard library imports
import logging
from typing import Optional

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

# Request/Response models
class QueryRequest(BaseModel):
    question: str
    format: Optional[str] = "web"  # "web" or "voice"

class QueryResponse(BaseModel):
    response: str
    emotion: str = "neutral"
    cache_safe: bool = True  # NEW: Indicates if response is from cache-safe content
    metadata: dict = {}

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    message: Optional[str] = None

# Create router
router = APIRouter()
logger = logging.getLogger('rag-service')

# Dependency to get RAG assistant instance
def get_assistant():
    from main import assistant
    if assistant is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return assistant

# Dependency to get config instance
def get_config():
    from main import config
    if config is None:
        raise HTTPException(status_code=503, detail="Configuration not loaded")
    return config

@router.get("/", response_model=dict)
async def root(config = Depends(get_config)):
    """Root endpoint for basic health check."""
    return {
        "message": f"{config.api_title} is running", 
        "status": "healthy",
        "version": config.api_version,
        "endpoints": ["/health", "/query", "/stats"],
        "supported_formats": ["web", "voice"],
        "features": [
            "emotion_detection", 
            "format_aware_responses", 
            "temporal_cache_control",
            "perplexity_integration"
        ]
    }

@router.get("/health", response_model=HealthResponse)
async def health_check(assistant = Depends(get_assistant), config = Depends(get_config)):
    """Detailed health check endpoint."""
    try:
        # Perform basic checks
        collection_count = assistant.collection.count() if hasattr(assistant, 'collection') else 0
        
        # Check service availability
        cache_enabled = assistant.is_cache_enabled()
        perplexity_available = (assistant.perplexity_client.is_available() 
                              if hasattr(assistant, 'perplexity_client') else False)
        
        return HealthResponse(
            status="healthy",
            service="rag-api",
            version=config.api_version,
            message=f"Service operational with {collection_count} documents, "
                   f"cache: {'enabled' if cache_enabled else 'disabled'}, "
                   f"temporal queries: {'enabled' if perplexity_available else 'disabled'}"
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        error_detail = f"Service unhealthy: {str(e)}" if config.detailed_error_responses else "Service unhealthy"
        raise HTTPException(
            status_code=503, 
            detail=error_detail
        )

@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest, assistant = Depends(get_assistant), config = Depends(get_config)):
    """Process a query through the RAG system with emotion detection and cache control."""
    
    # Validate input
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    if len(request.question.strip()) > config.max_query_length:
        raise HTTPException(
            status_code=400, 
            detail=f"Question too long (max {config.max_query_length} characters)"
        )
    
    # Validate format parameter
    if request.format not in ["web", "voice"]:
        raise HTTPException(
            status_code=400,
            detail="Format must be 'web' or 'voice'"
        )
    
    try:
        # Determine if this is a temporal query for logging
        is_temporal = False
        if hasattr(assistant, 'temporal_detector') and config.perplexity_enabled:
            is_temporal = assistant.temporal_detector.needs_current_info(request.question)
        
        # Console logging for format and query type tracking
        query_type = "TEMPORAL" if is_temporal else "RAG"
        print(f"Query - Type: {query_type} | Format: {request.format.upper()} | Question: {request.question[:100]}{'...' if len(request.question) > 100 else ''}")
        
        logger.info(f"Processing {request.format} query ({'temporal' if is_temporal else 'static'}): {request.question[:100]}...")
        
        # Collect the complete response from the generator
        response_text = ""
        chunk_count = 0
        
        # Process query and collect all chunks
        for chunk in assistant.query(
            question=request.question,
            response_format=request.format
        ):
            response_text += chunk
            chunk_count += 1
        
        # Get detected emotion from assistant (set during streaming)
        detected_emotion = assistant.get_last_detected_emotion()
        
        # Get cache safety from assistant's last query
        cache_safe = True  # Default for static content
        if hasattr(assistant, '_current_query_data') and assistant._current_query_data:
            cache_safe = assistant._current_query_data.get("cache_safe", True)
        elif is_temporal:
            cache_safe = False  # Temporal queries are never cache-safe
        
        # Clean response text by removing emotion tag if it somehow got through
        import re
        cleaned_response = re.sub(r'EMOTION:\s*[a-zA-Z]+\s*$', '', response_text.strip()).strip()
        
        # Console logging for response summary
        cache_status = "CACHED" if cache_safe else "FRESH"
        print(f"Response - Type: {query_type} | Format: {request.format.upper()} | Length: {len(cleaned_response)} chars | Emotion: {detected_emotion} | Cache: {cache_status} | Chunks: {chunk_count}")
        
        logger.info(f"Query processed successfully - {chunk_count} chunks, {len(cleaned_response)} chars, format: {request.format}, emotion: {detected_emotion}, cache_safe: {cache_safe}")
        
        return QueryResponse(
            response=cleaned_response,
            emotion=detected_emotion,
            cache_safe=cache_safe,  # NEW: Critical for client cache control
            metadata={
                "question": request.question,
                "format": request.format,
                "response_length": len(cleaned_response),
                "chunk_count": chunk_count,
                "service_version": config.api_version,
                "emotion_detected": detected_emotion,
                "cache_safe": cache_safe,
                "query_type": query_type.lower(),
                "temporal_detected": is_temporal,
                "features_used": [
                    "emotion_detection", 
                    "format_aware_response",
                    "temporal_cache_control"
                ]
            }
        )
        
    except Exception as e:
        # Console logging for errors
        print(f"Error - Format: {request.format.upper()} | Error: {str(e)}")
        logger.error(f"Error processing query '{request.question[:50]}...' (format: {request.format}): {str(e)}", exc_info=True)
        error_detail = f"Query processing failed: {str(e)}" if config.detailed_error_responses else "Query processing failed"
        raise HTTPException(
            status_code=500, 
            detail=error_detail
        )

@router.get("/stats")
async def get_stats(assistant = Depends(get_assistant), config = Depends(get_config)):
    """Get service statistics including cache information."""
    try:
        stats = {
            "service": "rag-api",
            "version": config.api_version,
            "status": "operational",
            "features": {
                "emotion_detection": True,
                "format_aware_responses": True,
                "temporal_detection": config.perplexity_enabled,
                "perplexity_integration": config.perplexity_enabled,
                "cache_control": assistant.is_cache_enabled(),
                "supported_query_types": ["static_rag", "temporal_perplexity"]
            },
            "configuration": {
                "max_query_length": config.max_query_length,
                "request_timeout": config.request_timeout,
                "default_results": config.DEFAULT_RESULTS,
                "collection_name": config.COLLECTION_NAME,
                "supported_formats": ["web", "voice"],
                "supported_emotions": [
                    "happy", "excited", "thinking", "confused", 
                    "greeting", "goodbye", "neutral", "sad", "surprised"
                ],
                "cache_enabled": assistant.is_cache_enabled(),
                "perplexity_enabled": config.perplexity_enabled
            }
        }
        
        # Add collection stats if available
        if hasattr(assistant, 'collection'):
            try:
                collection_count = assistant.collection.count()
                stats["document_count"] = collection_count
            except:
                stats["document_count"] = "unavailable"
        
        # Add cache stats if available
        if assistant.is_cache_enabled():
            try:
                cache_stats = assistant.get_cache_stats()
                stats["cache_stats"] = cache_stats
            except:
                stats["cache_stats"] = "unavailable"
        else:
            stats["cache_stats"] = {"enabled": False}
        
        # Add Perplexity availability
        if hasattr(assistant, 'perplexity_client'):
            try:
                perplexity_available = assistant.perplexity_client.is_available()
                stats["perplexity_status"] = {
                    "available": perplexity_available,
                    "enabled": config.perplexity_enabled
                }
            except:
                stats["perplexity_status"] = {"available": False, "enabled": config.perplexity_enabled}
        
        # Add temporal detection keywords for debugging
        if hasattr(assistant, 'temporal_detector'):
            stats["temporal_detection"] = {
                "enabled": config.perplexity_enabled,
                "temporal_keywords": config.temporal_keywords[:5],  # Sample
                "status_keywords": config.status_keywords[:3],     # Sample
                "current_year_range": f"{config.current_year_range} years"
            }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        error_detail = f"Failed to retrieve stats: {str(e)}" if config.detailed_error_responses else "Failed to retrieve stats"
        raise HTTPException(status_code=500, detail=error_detail)

@router.get("/cache/stats")
async def get_cache_stats(assistant = Depends(get_assistant)):
    """Get detailed cache statistics (if caching is enabled)."""
    if not assistant.is_cache_enabled():
        raise HTTPException(status_code=404, detail="Caching not enabled")
    
    try:
        cache_stats = assistant.get_cache_stats()
        return {
            "cache_enabled": True,
            "stats": cache_stats,
            "cache_types": ["llm_responses", "translations", "audio"],
            "cache_policies": {
                "llm_responses": "7 days TTL, format-aware keys",
                "temporal_queries": "never cached",
                "static_queries": "cached with emotion parsing"
            }
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")

@router.post("/cache/clear")
async def clear_cache(assistant = Depends(get_assistant)):
    """Clear all caches (admin endpoint)."""
    if not assistant.is_cache_enabled():
        raise HTTPException(status_code=404, detail="Caching not enabled")
    
    try:
        if hasattr(assistant.cache_manager, 'clear_all_caches'):
            cleared_count = assistant.cache_manager.clear_all_caches()
            logger.info(f"Manual cache clear: {cleared_count} entries removed")
            return {
                "status": "success",
                "message": f"Cleared {cleared_count} cache entries",
                "timestamp": assistant.cache_manager._get_current_timestamp()
            }
        else:
            return {
                "status": "error", 
                "message": "Cache clear not implemented"
            }
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
