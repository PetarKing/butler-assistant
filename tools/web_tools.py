import requests
import bs4
import re
import openai
from langchain_community.tools import DuckDuckGoSearchResults
from config.settings import CHEAP_MODEL

ddg = DuckDuckGoSearchResults()

def web_search(query: str) -> str:
    """
    Perform a web search using DuckDuckGo.
    
    Args:
        query: The search query string
        
    Returns:
        Search results truncated to 1500 characters, or error message
    """
    try:
        result = ddg.run(query)[:1500]
        return result
    except Exception as e:
        return f"[search-error] {e}"

_safe = re.compile(r"^[0-9+\-*/(). ]+$")

def calculator(expression: str) -> str:
    """
    Safely evaluate a basic arithmetic expression.
    
    Args:
        expression: Mathematical expression using only numbers and basic operators
        
    Returns:
        Result of the calculation or error message
    """
    if not _safe.match(expression):
        return "Only numbers and + - * / ( ) allowed."
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"[calc‑error] {e}"

def fetch_page(url: str) -> str:
    """
    Download and summarize a web page's content.
    
    Fetches the HTML content, strips scripts/styles, and uses AI to generate
    a summary along with a content snippet for further processing.
    
    Args:
        url: HTTP/HTTPS URL to fetch
        
    Returns:
        Formatted string containing page title, URL, AI summary, and content snippet
    """
    url = url.strip()
    print(f"[🌐 fetch] {url}")
    
    if not url.startswith(("http://", "https://")):
        return "fetch_page only supports http/https URLs."
    
    try:
        resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        resp.raise_for_status()
        
        soup = bs4.BeautifulSoup(resp.text, "html.parser")
        
        # Remove script, style, and noscript tags
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
            
        text = " ".join(soup.stripped_strings)
        if not text:
            return "[fetch_page] no readable text."

        # Generate summary using AI
        chunk = text[:4000]
        title = soup.title.string.strip() if soup.title and soup.title.string else "(no title)"
        
        summary_resp = openai.chat.completions.create(
            model=CHEAP_MODEL,
            messages=[
                {"role": "system", "content": "Summarise the page in a few bullet points, factual, no opinion."},
                {"role": "user", "content": f"TITLE: {title}\n\nCONTENT:\n{chunk}"}
            ],
            max_tokens=500,
            temperature=0.2,
        )
        summary = summary_resp.choices[0].message.content.strip()

        # Return structured response
        snippet = text[:2000]
        return (
            f"PAGE_TITLE: {title}\n"
            f"URL: {url}\n\n"
            f"SUMMARY:\n{summary}\n\n"
            f"CONTENT_SNIPPET:\n{snippet}"
        )
    except Exception as e:
        return f"[fetch_page-error] {e}"
