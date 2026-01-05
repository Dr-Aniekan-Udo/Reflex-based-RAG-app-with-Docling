"""
Agent tools for document search and retrieval.
"""
from typing import Annotated
from langchain_core.tools import tool

def create_search_tool(vectorstore):
    """
    Create a search tool that has access to the vector store.
    Args:
        vectorstore: The Chroma vector store containing documents

    Returns:
        A tool function that can search the documents
    """

    @tool
    def search_documents(query: Annotated[str, "The search query or question about the documents"]) -> str:
        """
        Search the uploaded documents for relevant information.
        Use this tool when you need to find specific information from the uploaded documents.
        """
        try:
            # Perform similarity search
            results = vectorstore.similarity_search(query, k=8)

            if not results:
                return "No relevant information found in the documents for this query."

            # Format the results
            context_parts = []
            for i, doc in enumerate(results, 1):
                # 1. Get Source Name
                source = doc.metadata.get('filename', doc.metadata.get('source', 'Unknown source'))
                
                # 2. Get Page Number (The feature we added!)
                page = doc.metadata.get('page', 'Unknown Page')
                
                content = doc.page_content.strip()

                context_parts.append(
                    f"[Source {i}: {source} (Page {page})]\n"
                    f"Content: {content}\n"
                )

            return "\n---\n".join(context_parts)

        except Exception as e:
            return f"Error searching documents: {str(e)}"

    return search_documents
