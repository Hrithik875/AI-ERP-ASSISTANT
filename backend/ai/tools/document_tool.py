"""
AI ERP Assistant — Document Tool
==================================
Handles document retrieval queries via the RAG pipeline.

Returns structured results including:
  - context text for LLM consumption
  - source citations (filename, page, score) for the API response
  - explicit fallback message when no relevant documents are found
"""

from typing import Any, Dict
from .base import BaseTool
import logging

logger = logging.getLogger("erp-assistant")

# Explicit fallback message returned when no uploaded document is relevant.
# This prevents the LLM from hallucinating an answer from weak context.
NO_MATCH_MESSAGE = (
    "I couldn't find anything in the uploaded documents relevant to that question. "
    "If you believe the answer should be in a document, please check that it has "
    "been uploaded and try rephrasing your query."
)


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
            result = rag.search_with_sources(query)

            if result["has_relevant_results"]:
                return {
                    "context": result["context"],
                    "sources": result["sources"],
                    "has_relevant_results": True,
                }
            else:
                logger.info(f"DocumentTool: no relevant results for query: '{query[:60]}'")
                return {
                    "message": NO_MATCH_MESSAGE,
                    "sources": [],
                    "has_relevant_results": False,
                }
        except Exception as e:
            logger.error(f"DocumentTool error: {e}")
            return {"error": f"Failed to retrieve documents: {e}"}
