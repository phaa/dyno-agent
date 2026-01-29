#!/usr/bin/env python3
"""
Golden Set Evaluation Runner for Dyno-Agent

Executes the real agent against golden sets and validates:
- Decision cases: tools_used, allocation_valid, reason_contains
- QA cases: expected_contains, must_not_contain
"""

import sys
import asyncio
import logging

from .golden_set_runner import GoldenSetRunner

# Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Main Entry Point
async def main():
    """Main entry point."""
    runner = GoldenSetRunner()
    
    try:
        passed, failed, results = await runner.run_all()
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Total:  {passed + failed}")
        
        if failed == 0:
            logger.info("\n✓ All tests passed!")
            return 0
        else:
            logger.error(f"\n✗ {failed} test(s) failed")
            return 1
    
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
