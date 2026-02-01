#!/usr/bin/env python3
# encoding: utf-8
# Utility functions for robot assistant

def get_language_code(language_name: str) -> str:
    """Get language code for translation services"""
    from config import LANGUAGE_CODES
    return LANGUAGE_CODES.get(language_name, "en")

def get_startup_greeting():
    """Get the startup greeting from config"""
    from config import STARTUP_GREETING
    return STARTUP_GREETING