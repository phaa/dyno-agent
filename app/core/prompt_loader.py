"""
Prompt loader utility for versioned LLM prompts.

Provides a centralized mechanism to load prompts from external files,
enabling versioning and management of LLM system prompts outside the codebase.

Usage:
    system_prompt = load_prompt("llm_node", "system", version="1.0.0")
    summary_prompt = load_prompt("summarization_node", "summary")  # defaults to 1.0.0
"""

import os
from pathlib import Path
from typing import Optional


def load_prompt(
    node_name: str,
    prompt_name: str,
    version: str = "1.0.0"
) -> str:
    """
    Load a versioned prompt from the prompts directory.
    
    Args:
        node_name: The node directory name (e.g., 'llm_node', 'summarization_node')
        prompt_name: The prompt file name without version or extension (e.g., 'system', 'summary')
        version: Semantic version string (default: '1.0.0')
        
    Returns:
        str: The prompt content as a string
        
    Raises:
        FileNotFoundError: If the prompt file does not exist
        
    Examples:
        system_prompt = load_prompt("llm_node", "system")
        summary_prompt = load_prompt("summarization_node", "summary", version="1.0.0")
    """
    prompt_dir = Path(__file__).parent.parent.parent / "prompts" / node_name
    prompt_file = prompt_dir / f"{prompt_name}_v{version}.txt"
    
    if not prompt_file.exists():
        raise FileNotFoundError(
            f"Prompt not found: {prompt_file}. "
            f"Expected format: prompts/{node_name}/{prompt_name}_v{version}.txt"
        )
    
    return prompt_file.read_text(encoding="utf-8")
