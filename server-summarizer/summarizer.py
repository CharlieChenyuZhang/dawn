import os
import logging
from typing import List, Dict, Any, Optional
import time
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SummarizerWorker:
    """Worker that summarizes text using OpenAI's GPT-4.5 Turbo model."""
    
    def __init__(self, agent_id: int, api_key: Optional[str] = None):
        """
        Initialize the summarizer worker.
        
        Args:
            agent_id: Unique identifier for this summarizer agent (1-3)
            api_key: OpenAI API key (if None, will try to get from environment)
        """
        self.agent_id = agent_id
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No OpenAI API key provided. Summarization will fail.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.processed_count = 0
        
        # Different focus areas based on agent_id
        self.focus_areas = {
            1: "new AI technologies and technical breakthroughs",
            2: "business applications and industry impact of AI",
            3: "ethical considerations, policy updates, and social implications of AI"
        }
    
    def chunk_text(self, text: str, max_chunk_size: int = 12000) -> List[str]:
        """
        Split text into manageable chunks for the LLM.
        
        Args:
            text: The article text to chunk
            max_chunk_size: Maximum size of each chunk
            
        Returns:
            List of text chunks
        """
        if len(text) <= max_chunk_size:
            return [text]
            
        # Split by paragraphs to avoid cutting sentences
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) + 2 <= max_chunk_size:
                if current_chunk:
                    current_chunk += '\n\n'
                current_chunk += paragraph
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = paragraph
                
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks
    
    def summarize_chunk(self, chunk: str, max_words: int = 100) -> str:
        """
        Summarize a single chunk of text using OpenAI API.
        
        Args:
            chunk: Text chunk to summarize
            max_words: Target maximum word count for summary
            
        Returns:
            Summarized text
        """
        if not self.api_key:
            raise ValueError("OpenAI API key is required for summarization")
        
        focus = self.focus_areas.get(self.agent_id, "the most important information")
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Using GPT-4o (latest available) as a proxy for 4.5
                messages=[
                    {"role": "system", "content": f"You are a highly efficient AI summarizer that focuses on {focus}. Extract only the most important information and provide a concise summary."},
                    {"role": "user", "content": f"Summarize the following text in approximately {max_words} words, focusing on {focus}. Format your response as bullet points:\n\n{chunk}"}
                ],
                temperature=0.2,
                max_tokens=400,
                top_p=0.95
            )
            
            summary = response.choices[0].message.content
            self.processed_count += 1
            return summary
            
        except Exception as e:
            logger.error(f"Error with OpenAI API: {str(e)}")
            raise
    
    def process_article(self, article_text: str, article_metadata: Dict[str, Any], max_words: int = 100) -> Dict[str, Any]:
        """
        Process a full article by chunking and summarizing.
        
        Args:
            article_text: The full article text
            article_metadata: Dictionary with metadata like title, source, URL
            max_words: Target maximum word count for summary
            
        Returns:
            Dictionary with original metadata and added summary
        """
        logger.info(f"Summarizer Agent {self.agent_id} processing article: {article_metadata.get('title', 'Untitled')}")
        
        chunks = self.chunk_text(article_text)
        logger.info(f"Split article into {len(chunks)} chunks")
        
        summaries = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")
            summary = self.summarize_chunk(chunk, max_words // len(chunks))
            summaries.append(summary)
            
            # Add a small delay to avoid rate limiting
            if i < len(chunks) - 1:
                time.sleep(0.5)
        
        # Combine chunk summaries if needed
        if len(summaries) > 1:
            combined_summary = self.combine_summaries(summaries, article_metadata, max_words)
        else:
            combined_summary = summaries[0]
        
        result = article_metadata.copy()
        result["summary"] = combined_summary
        result["agent_id"] = self.agent_id
        result["focus_area"] = self.focus_areas[self.agent_id]
        
        return result
    
    def combine_summaries(self, summaries: List[str], metadata: Dict[str, Any], max_words: int = 100) -> str:
        """
        Combine multiple chunk summaries into one coherent summary.
        
        Args:
            summaries: List of chunk summaries
            metadata: Article metadata
            max_words: Target maximum word count for final summary
            
        Returns:
            Combined summary
        """
        combined_text = "\n\n".join(summaries)
        
        # If combined text is small enough, return as is
        word_count = len(combined_text.split())
        if word_count <= max_words:
            return combined_text
        
        # If too large, perform a meta-summarization
        focus = self.focus_areas[self.agent_id]
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": f"You are a highly efficient AI summarizer that focuses on {focus}."},
                    {"role": "user", "content": f"This is a collection of summaries from different parts of the article: \"{metadata.get('title', 'Untitled')}\". Create a unified, coherent summary focusing on {focus} in approximately {max_words} words. Format your response as bullet points:\n\n{combined_text}"}
                ],
                temperature=0.2,
                max_tokens=300,
                top_p=0.95
            )
            
            final_summary = response.choices[0].message.content
            return final_summary
            
        except Exception as e:
            logger.error(f"Error with OpenAI API during meta-summarization: {str(e)}")
            return combined_text