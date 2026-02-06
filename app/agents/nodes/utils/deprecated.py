"""Deprecated utility functions."""

import logging
from agents.state import GraphState
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


# Deprecated
def db_disabled_node(state: GraphState) -> GraphState:
    """Handles the case where the database is empty or unreachable."""
    error_message = "Apparently our database is not configured. Aborting further operations"
    return {
        "messages": [AIMessage(content=error_message)],
    }
