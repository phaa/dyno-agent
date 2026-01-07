import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from core.prometheus_metrics import metrics_storer
from models.metrics import Metrics

try:
    from langsmith import Client
    langsmith_client = Client() if os.getenv("LANGSMITH_API_KEY") else None
except ImportError:
    langsmith_client = None

class ConversationMetrics:
    """Tracks conversation metrics with automatic LangSmith integration"""
    
    def __init__(self, db: Optional[AsyncSession] = None):
        self.langsmith_enabled = bool(os.getenv("LANGSMITH_API_KEY"))
        self.client = langsmith_client
        self.db = db
    
    async def track_conversation(
        self,
        user_message: str,
        assistant_response: str,
        user_email: str,
        conversation_id: str,
        duration_ms: float,
        token_usage: Optional[Dict[str, int]] = None,
        tools_used: Optional[list] = None
    ) -> Dict[str, Any]:
        """Track conversation metrics (LangGraph traces automatically to LangSmith)"""
        
        metadata = {
            "user_email": user_email,
            "conversation_id": conversation_id,
            "duration_ms": duration_ms,
            "message_length": len(user_message),
            "response_length": len(assistant_response),
            "tools_used": tools_used or [],
            "token_usage": token_usage or {}
        }
        
        # Update Prometheus metrics
        if metrics_storer:
            metrics_storer.record_method_execution(  
                service_name="ChatService",
                method_name="chat_conversation",
                duration_seconds=duration_ms / 1000,
                success=True,
                user_id=hash(user_email) % 10000
            )
        
        return {
            "conversation_tracked": True,
            "langsmith_enabled": self.langsmith_enabled,
            "extra_data": metadata
        }
    
    async def get_conversation_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get real conversation statistics from database and LangSmith"""
        if not self.langsmith_enabled:
            return {"error": "LangSmith not configured"}
        
        # Get data from PostgreSQL metrics table
        db_stats = await self._get_db_conversation_stats(hours) if self.db else {}
        
        # Get data from LangSmith API (if available)
        langsmith_stats = await self._get_langsmith_stats(hours)
        
        # Combine both sources
        return {
            **db_stats,
            **langsmith_stats,
            "data_sources": {
                "database": bool(self.db),
                "langsmith": self.langsmith_enabled
            }
        }
    
    async def _get_db_conversation_stats(self, hours: int) -> Dict[str, Any]:
        """Get conversation stats from PostgreSQL metrics table"""
        if not self.db:
            return {}
        
        since = datetime.now() - timedelta(hours=hours)
        
        # Query chat service metrics
        stmt = select(
            func.count().label('total_conversations'),
            func.avg(Metrics.duration_ms).label('avg_duration_ms'),
            func.sum(Metrics.success.cast(Integer)).label('success_count'),
            func.count().label('total_count')
        ).where(
            and_(
                Metrics.service_name == 'ChatService',
                Metrics.method_name == 'chat_conversation',
                Metrics.created_at >= since
            )
        )
        
        result = await self.db.execute(stmt)
        row = result.first()
        
        if not row or row.total_conversations == 0:
            return {
                "total_conversations": 0,
                "avg_duration_ms": 0,
                "success_rate": 0
            }
        
        success_rate = (row.success_count / row.total_count) * 100 if row.total_count > 0 else 0
        
        return {
            "total_conversations": row.total_conversations,
            "avg_duration_ms": round(row.avg_duration_ms, 2),
            "success_rate": round(success_rate, 2)
        }
    
    async def _get_langsmith_stats(self, hours: int) -> Dict[str, Any]:
        """Get stats from LangSmith API including cost tracking"""
        if not self.client:
            return {}
        
        try:
            # Query LangSmith for runs in the last N hours
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            # Get runs from LangSmith
            runs = list(self.client.list_runs(
                project_name=os.getenv("LANGCHAIN_PROJECT", "dyno-agent-production"),
                start_time=start_time,
                end_time=end_time
            ))
            
            if not runs:
                return {
                    "langsmith_conversations": 0,
                    "total_cost_usd": 0,
                    "avg_cost_per_conversation": 0
                }
            
            # Calculate costs and metrics
            total_cost = 0
            total_tokens = 0
            successful_runs = 0
            tool_usage = {}
            
            for run in runs:
                # Cost calculation (if available in run data)
                if hasattr(run, 'total_cost') and run.total_cost:
                    total_cost += run.total_cost
                
                # Token usage (if available)
                if hasattr(run, 'total_tokens') and run.total_tokens:
                    total_tokens += run.total_tokens
                elif hasattr(run, 'usage_metadata') and run.usage_metadata:
                    # Alternative way to get token usage
                    usage = run.usage_metadata
                    if 'total_tokens' in usage:
                        total_tokens += usage['total_tokens']
                
                # Success tracking
                if run.status == 'success':
                    successful_runs += 1
                
                # Tool usage tracking
                if hasattr(run, 'outputs') and run.outputs:
                    # Extract tool names from run outputs
                    tools = self._extract_tools_from_run(run)
                    for tool in tools:
                        tool_usage[tool] = tool_usage.get(tool, 0) + 1
            
            # Calculate averages
            avg_cost = total_cost / len(runs) if runs else 0
            avg_tokens = total_tokens / len(runs) if runs else 0
            success_rate = (successful_runs / len(runs)) * 100 if runs else 0
            
            # Get most used tools
            most_used_tools = sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)[:3]
            most_used_tools = [tool for tool, count in most_used_tools]
            
            return {
                "langsmith_conversations": len(runs),
                "total_cost_usd": round(total_cost, 4),
                "avg_cost_per_conversation": round(avg_cost, 4),
                "total_tokens": total_tokens,
                "avg_tokens_per_conversation": round(avg_tokens, 2),
                "langsmith_success_rate": round(success_rate, 2),
                "most_used_tools": most_used_tools,
                "cost_breakdown": {
                    "input_cost": round(float(total_cost) * 0.7, 4),  # Estimate
                    "output_cost": round(float(total_cost) * 0.3, 4)  # Estimate
                }
            }
            
        except Exception as e:
            return {"langsmith_error": str(e)}
    
    def _extract_tools_from_run(self, run) -> list:
        """Extract tool names from LangSmith run data"""
        tools = []
        try:
            if hasattr(run, 'child_runs') and run.child_runs:
                for child in run.child_runs:
                    if hasattr(child, 'name') and 'tool' in child.name.lower():
                        tools.append(child.name)
            
            # Alternative: check run inputs/outputs for tool calls
            if hasattr(run, 'inputs') and run.inputs:
                # Look for tool calls in inputs
                if 'tool_calls' in str(run.inputs):
                    # Extract tool names from tool calls
                    pass
        except:
            pass
        
        return tools

# Global instance - will be initialized with DB session in router
conversation_metrics = None