from .config import ENABLE_STREAM_WRITER
from langgraph.config import get_stream_writer as get_writer

class StreamWriter:
    def __init__(self, enabled: bool):
        self._enabled = enabled
        
    def __call__(self, message: str):
        if self._enabled:
            writer = get_writer()
            writer(message)

def get_stream_writer():
    """Wrapper to get the stream writer from langgraph config."""
    writer = StreamWriter(enabled=ENABLE_STREAM_WRITER)
    return writer