import logging
import json
import sys
from app.config import settings

class JSONFormatter(logging.Formatter):
    """
    Formats log records as a JSON object.
    Matches requirement: One JSON line per request.
    """
    def format(self, record):
        # 1. Base log object with required fields
        log_obj = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # 2. Add extra fields if they exist (critical for request_id and analytics)
        # When we log later like logger.info("msg", extra={"request_id": "123"}),
        # this loop puts "request_id" directly into the JSON root.
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id
            
        # Handle 'extra' dict passed to logger
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in ["args", "asciitime", "created", "exc_info", "exc_text", 
                               "filename", "funcName", "levelname", "levelno", "lineno", 
                               "module", "msecs", "msg", "name", "pathname", "process", 
                               "processName", "relativeCreated", "stack_info", "thread", 
                               "threadName"]:
                    log_obj[key] = value

        return json.dumps(log_obj)

def setup_logging():
    """Applies the JSON formatter to the root logger."""
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)
    
    # Remove default handlers to avoid duplicate logs
    if root_logger.handlers:
        root_logger.handlers = []

    # Create console handler with our JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)
