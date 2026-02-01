import streamlit as st
import logging
import requests
from pathlib import Path
from config import WebUIConfig

logger = logging.getLogger('ui')
def setup_logger():
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler('../logs/ui.log')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
setup_logger()

def create_ui(assistant, config: WebUIConfig) -> None:  
    logger.debug("Initializing Streamlit UI")
    
    st.set_page_config(
        page_title=config.page_title,
        page_icon=config.page_icon,
        layout=config.page_layout, 
        initial_sidebar_state=config.sidebar_state
    )

    _apply_css_styles(config)
    _init_session_state(config)
    
    st.title(config.page_title)
    st.markdown(
        f"<p style='font-size: 1.2em; font-weight: 600;'>"
        f"{config.welcome_message}"
        f"</p>",
        unsafe_allow_html=True
    )

    chat_container = st.container(height=config.chat_container_height, border=config.chat_container_border)
    input_container = st.container()
    translation_container = st.container()

    _handle_chat_display(chat_container)
    _handle_user_input(assistant, chat_container, input_container, config)
    _handle_translation_section(assistant, translation_container, config)

def _apply_css_styles(config: WebUIConfig):
    st.markdown(f"""
        <style>
        .main > div {{ padding: 0.5em 0; }}
        .translate-section {{ margin-top: 1em; padding: 0.5em 0; }}
        .stSelectbox {{ background-color: #f8f9fa; }}
        div[data-testid="stButton"] button {{
            background-color: {config.primary_button_color};
            color: white !important;
            padding: 0.5em 1em;
            transition: all 0.3s ease;
        }}
        div[data-testid="stButton"] button:hover {{
            background-color: {config.primary_button_hover_color};
            color: white !important;
        }}
        div[data-testid="stButton"] button:disabled {{
            background-color: {config.primary_button_color};
            opacity: {config.primary_button_opacity};
            color: white !important;
        }}
        .translated-text {{
            background-color: white;
            padding: 1em;
            border-radius: 0.5em;
            border: 1px solid #eee;
            line-height: 1.6;
            margin: 0.5em 0;
        }}
        .stMarkdown {{ margin-bottom: 0.5em; }}
        </style>
    """, unsafe_allow_html=True)

def _init_session_state(config: WebUIConfig):
    for var, default in config.session_vars.items():
        if var not in st.session_state:
            st.session_state[var] = default

def _handle_chat_display(chat_container):
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

def _handle_user_input(assistant, chat_container, input_container, config: WebUIConfig):
    with input_container:
        if prompt := st.chat_input(config.chat_input_placeholder):
            if not st.session_state.processing:
                _process_user_input(assistant, chat_container, prompt, config)

def _process_user_input(assistant, chat_container, prompt, config: WebUIConfig):
    st.session_state.current_audio = None
    st.session_state.generating_audio = False
    
    st.session_state.processing = True
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with chat_container:
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            # Use existing RAG client query method
            for chunk in assistant.query(prompt, "web"):
                full_response += chunk
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
            
            # MINIMAL APPROACH: Extract cache_safe from the rag_client's last API response
            response_cache_safe = getattr(assistant.rag_client, 'last_response_cache_safe', True)
    
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    st.session_state.last_response = full_response
    st.session_state.last_response_cache_safe = response_cache_safe  # Store for translation/TTS
    
    # Console logging for cache behavior
    cache_status = "cache-safe" if response_cache_safe else "temporal"
    target_lang = st.session_state.selected_language or st.session_state.language_selector
    print(f"UI - Processing response: {cache_status} | Translation: {target_lang}")
    
    # Translate response immediately with cache control
    try:
        translated = assistant.translation_service.translate(full_response, target_lang, cache_safe=response_cache_safe)
        st.session_state.translated_text = translated
    except Exception as e:
        st.error(f"Translation error: {str(e)}")
        st.session_state.translated_text = ""
    
    st.session_state.processing = False

def _handle_translation_section(assistant, translation_container, config: WebUIConfig):
    with translation_container:
        st.markdown('<div class="translate-section">', unsafe_allow_html=True)
        st.markdown(
            f"<p style='font-size: 1.2em; font-weight: 600; margin: 0.5em 0;'>{config.translate_section_title}</p>",
            unsafe_allow_html=True
        )
        
        col1, col2, col3 = st.columns([1.5, 1, 1.5])
        
        with col1:
            _handle_language_selector(assistant, config)

        _handle_audio_controls(col2, col3, assistant, config)
        _display_translated_text()
        
        st.markdown('</div>', unsafe_allow_html=True)

def _handle_language_selector(assistant, config: WebUIConfig):
    def on_language_change():
        st.session_state.selected_language = st.session_state.language_selector
        if st.session_state.last_response:
            try:
                # Use cache_safe flag from last response
                cache_safe = getattr(st.session_state, 'last_response_cache_safe', True)
                translated = assistant.translation_service.translate(
                    st.session_state.last_response,
                    st.session_state.language_selector,
                    cache_safe=cache_safe
                )
                st.session_state.translated_text = translated
                # Reset audio when language changes
                st.session_state.current_audio = None
                st.session_state.generating_audio = False
            except Exception as e:
                st.error(f"Translation error: {str(e)}")
                st.session_state.translated_text = ""
    
    st.selectbox(
        "Translate to:",
        config.supported_languages,
        key="language_selector",
        on_change=on_language_change,
        label_visibility="collapsed"
    )

def _handle_audio_controls(col2, col3, assistant, config: WebUIConfig):
    with col2:
        if st.session_state.generating_audio:
            st.button(config.generating_button_text, use_container_width=True, disabled=True, key="generating_button")
        else:
            if st.button(config.play_audio_button_text, use_container_width=True, key="play_button"):
                if st.session_state.translated_text:
                    _generate_audio(assistant, config)
    
    with col3:
        if isinstance(st.session_state.current_audio, Path):
            st.audio(str(st.session_state.current_audio))

def _generate_audio(assistant, config: WebUIConfig):
    """Generate audio using TTS service with cache control"""
    st.session_state.generating_audio = True
    
    try:
        with st.spinner("Generating audio..."):
            target_lang = st.session_state.selected_language or st.session_state.language_selector
            # Use cache_safe flag from last response
            cache_safe = getattr(st.session_state, 'last_response_cache_safe', True)
            # TTS service handles all caching internally with cache control
            audio_file = assistant.tts_service.synthesize(st.session_state.translated_text, target_lang, cache_safe=cache_safe)[0]
            
            if audio_file and audio_file.exists():
                st.session_state.current_audio = audio_file
            else:
                st.error("Audio generation failed")
                
    except Exception as e:
        st.error(f"Audio generation error: {str(e)}")
        logger.error(f"Audio generation failed: {str(e)}")
        
    finally:
        st.session_state.generating_audio = False
        st.rerun()

def _display_translated_text():
    """Display translated text"""
    if st.session_state.translated_text:
        st.markdown('<div class="translated-text">', unsafe_allow_html=True)
        st.markdown(st.session_state.translated_text)
        st.markdown('</div>', unsafe_allow_html=True)