#!/bin/bash
# Run golden set evaluation

set -e

cd "$(dirname "$0")/.."

if [ ! -f "eval/run_agent_golden.py" ]; then
    echo "❌ eval/run_agent_golden.py not found"
    exit 1
fi

if [ ! -f "app/golden_sets/agent_decisions_v1.0.0.json" ]; then
    echo "❌ Golden set file not found: app/golden_sets/agent_decisions_v1.0.0.json"
    exit 1
fi

if [ ! -f "app/golden_sets/agent_qa_v1.0.0.json" ]; then
    echo "❌ Golden set file not found: app/golden_sets/agent_qa_v1.0.0.json"
    exit 1
fi

echo "🚀 Running Golden Set Evaluation..."
python eval/run_agent_golden.py
exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "✅ All golden sets passed!"
else
    echo ""
    echo "❌ Some golden sets failed"
fi

exit $exit_code
