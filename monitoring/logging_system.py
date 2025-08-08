#!/usr/bin/env python3
"""
Enhanced logging system for DPerformance Agent
Provides structured logging with multiple output formats and severity levels
"""

import logging
import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum
import threading
from logging.handlers import RotatingFileHandler

class LogLevel(Enum):
    """Enhanced log levels with custom categories"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    SUCCESS = "SUCCESS"
    PERFORMANCE = "PERFORMANCE"
    BUSINESS = "BUSINESS"

class StructuredLogger:
    """Enhanced logger with structured output and multiple handlers"""
    
    def __init__(self, name: str, log_dir: str = "logs"):
        self.name = name
        self.log_dir = log_dir
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Setup handlers
        self._setup_console_handler()
        self._setup_file_handler()
        self._setup_json_handler()
        self._setup_error_handler()
        
        # Thread-local context
        self._context = threading.local()
    
    def _setup_console_handler(self):
        """Setup colorized console handler"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Colorized formatter
        class ColoredFormatter(logging.Formatter):
            COLORS = {
                'DEBUG': '\033[36m',      # Cyan
                'INFO': '\033[37m',       # White
                'WARNING': '\033[33m',    # Yellow
                'ERROR': '\033[31m',      # Red
                'CRITICAL': '\033[35m',   # Magenta
                'SUCCESS': '\033[32m',    # Green
                'PERFORMANCE': '\033[34m', # Blue
                'BUSINESS': '\033[35m',   # Magenta
                'ENDC': '\033[0m'         # End color
            }
            
            def format(self, record):
                log_color = self.COLORS.get(record.levelname, '')
                record.levelname = f"{log_color}{record.levelname}{self.COLORS['ENDC']}"
                return super().format(record)
        
        formatter = ColoredFormatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def _setup_file_handler(self):
        """Setup rotating file handler for general logs"""
        file_path = os.path.join(self.log_dir, f"{self.name}.log")
        file_handler = RotatingFileHandler(
            file_path, maxBytes=10*1024*1024, backupCount=5  # 10MB files, 5 backups
        )
        file_handler.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
    
    def _setup_json_handler(self):
        """Setup JSON structured log handler"""
        json_path = os.path.join(self.log_dir, f"{self.name}_structured.jsonl")
        json_handler = RotatingFileHandler(
            json_path, maxBytes=10*1024*1024, backupCount=5
        )
        json_handler.setLevel(logging.DEBUG)
        
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                    'logger': record.name,
                    'level': record.levelname,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno,
                    'thread_id': record.thread,
                    'process_id': record.process
                }
                
                # Add extra context if available
                if hasattr(record, 'extra_data'):
                    log_entry.update(record.extra_data)
                
                return json.dumps(log_entry)
        
        json_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(json_handler)
    
    def _setup_error_handler(self):
        """Setup dedicated error log handler"""
        error_path = os.path.join(self.log_dir, f"{self.name}_errors.log")
        error_handler = RotatingFileHandler(
            error_path, maxBytes=5*1024*1024, backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s\n'
            'Exception: %(exc_info)s\n' + '-'*80
        )
        error_handler.setFormatter(formatter)
        self.logger.addHandler(error_handler)
    
    def set_context(self, **context):
        """Set thread-local context for logging"""
        if not hasattr(self._context, 'data'):
            self._context.data = {}
        self._context.data.update(context)
    
    def clear_context(self):
        """Clear thread-local context"""
        if hasattr(self._context, 'data'):
            self._context.data.clear()
    
    def _get_context(self):
        """Get current thread-local context"""
        if hasattr(self._context, 'data'):
            return self._context.data.copy()
        return {}
    
    def _log(self, level: str, message: str, extra_data: Dict[str, Any] = None):
        """Internal logging method with context"""
        # Merge context with extra data
        context = self._get_context()
        if extra_data:
            context.update(extra_data)
        
        # Create log record with extra data
        extra = {'extra_data': context} if context else {}
        
        # Map custom levels to standard levels
        log_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.log(log_level, message, extra=extra)
    
    def debug(self, message: str, **extra):
        """Debug level logging"""
        self._log('DEBUG', message, extra)
    
    def info(self, message: str, **extra):
        """Info level logging"""
        self._log('INFO', message, extra)
    
    def warning(self, message: str, **extra):
        """Warning level logging"""
        self._log('WARNING', message, extra)
    
    def error(self, message: str, **extra):
        """Error level logging"""
        self._log('ERROR', message, extra)
    
    def critical(self, message: str, **extra):
        """Critical level logging"""
        self._log('CRITICAL', message, extra)
    
    def success(self, message: str, **extra):
        """Success level logging (custom)"""
        self._log('INFO', f"✅ SUCCESS: {message}", extra)
    
    def performance(self, message: str, duration: float = None, **extra):
        """Performance level logging (custom)"""
        if duration is not None:
            extra['duration'] = duration
            message = f"⏱️  PERFORMANCE: {message} (duration: {duration:.3f}s)"
        else:
            message = f"⏱️  PERFORMANCE: {message}"
        self._log('INFO', message, extra)
    
    def business(self, message: str, **extra):
        """Business logic level logging (custom)"""
        self._log('INFO', f"💼 BUSINESS: {message}", extra)

# Logger factory
_loggers = {}
_lock = threading.Lock()

def get_logger(name: str) -> StructuredLogger:
    """Get or create logger instance"""
    with _lock:
        if name not in _loggers:
            _loggers[name] = StructuredLogger(name)
        return _loggers[name]

# Convenience loggers for main components
def get_main_logger() -> StructuredLogger:
    """Get main application logger"""
    return get_logger("main")

def get_image_logger() -> StructuredLogger:
    """Get image agent logger"""
    return get_logger("image_agent")

def get_vehicle_logger() -> StructuredLogger:
    """Get vehicle application logger"""
    return get_logger("vehicle_agent")

def get_bigcommerce_logger() -> StructuredLogger:
    """Get BigCommerce agent logger"""
    return get_logger("bigcommerce_agent")

def get_ui_logger() -> StructuredLogger:
    """Get UI logger"""
    return get_logger("ui")

class LogContext:
    """Context manager for setting logging context"""
    
    def __init__(self, logger: StructuredLogger, **context):
        self.logger = logger
        self.context = context
        self.previous_context = None
    
    def __enter__(self):
        self.previous_context = self.logger._get_context()
        self.logger.set_context(**self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.clear_context()
        if self.previous_context:
            self.logger.set_context(**self.previous_context)

def log_operation(logger_name: str, operation: str):
    """Decorator for logging operation start/end"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            
            with LogContext(logger, operation=operation, function=func.__name__):
                logger.info(f"Starting {operation}")
                start_time = datetime.now()
                
                try:
                    result = func(*args, **kwargs)
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.success(f"Completed {operation}", duration=duration)
                    return result
                except Exception as e:
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.error(f"Failed {operation}: {e}", 
                               duration=duration, error_type=type(e).__name__)
                    raise
        
        return wrapper
    return decorator