import logging
import sys
import os
from pythonjsonlogger import jsonlogger

def setup_logging():
    """
    Configures centralized JSON logging for ECS/CloudWatch.
    Optimizes verbosity for LangChain, Boto3, and LangGraph components.
    """
    # 1. Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 2. Prevent duplicate logs by removing existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 3. Create StreamHandler for stdout (Required for AWS ECS)
    log_handler = logging.StreamHandler(sys.stdout)
    
    # 4. Define JSON Format
    # CloudWatch Insights performs best when specific fields are extracted
    formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%SZ'
    )
    log_handler.setFormatter(formatter)
    root_logger.addHandler(log_handler)

    # 5. Library-Specific Verbosity Management
    # High verbosity (INFO) for application logic and orchestration
    logging.getLogger("langchain").setLevel(logging.INFO)
    logging.getLogger("langgraph").setLevel(logging.INFO)
    
    # Noise reduction (WARNING) for infrastructure and transport layers
    # Boto3/Botocore can be extremely chatty with API calls to AWS
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    
    # LangSmith (langsmith-sdk) configuration
    # Set to WARNING to avoid logging every trace upload event
    logging.getLogger("langsmith").setLevel(logging.WARNING)

    root_logger.info("Logging infrastructure initialized successfully.")