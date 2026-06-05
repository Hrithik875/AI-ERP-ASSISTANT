"""
AI ERP Assistant — Document Tool
==================================
Handles document retrieval queries via existing RAG pipeline.
"""

from typing import Any, Dict
from .base import BaseTool
import logging

logger = logging.getLogger("erp-assistant")

class DocumentTool(BaseTool):
    name = "DocumentTool"
    description = "Searches for uploaded documents and policies using RAG."
    
    parameters = {
        "query": "The search query to find documents",
    }

    def execute(self, params: Dict[str, Any]) -> Any:
        query = params.get("query")
        if not query:
            return {"error": "Missing 'query' parameter"}
            
        try:
            from ai.rag_pipeline import get_rag
            rag = get_rag()
            context = rag.get_context(query)
            if context:
                return {"results": context}
            else:
                return {"message": "No relevant documents found."}
        except Exception as e:
            logger.error(f"DocumentTool error: {e}")
            return {"error": f"Failed to retrieve documents: {e}"}
