"""
Sonnet Extractor - Uses Claude Sonnet for entity extraction.

Good balance of quality and cost for extraction tasks.
~$3/1M input, $15/1M output

Created: 2026-02-06
"""

import os
import json
import requests
from typing import Optional, Dict, Any
from pathlib import Path

# Try to get API key from OpenClaw auth profiles
def get_anthropic_token() -> Optional[str]:
    """Get Anthropic API key from OpenClaw auth profiles or env."""
    # First try env var
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    
    # Try OpenClaw API key (OAuth tokens don't work for direct API)
    auth_path = Path("/root/.openclaw/agents/main/agent/auth-profiles.json")
    if auth_path.exists():
        try:
            with open(auth_path) as f:
                auth = json.load(f)
            # API key works for direct API calls
            api_key = auth.get('profiles', {}).get('anthropic:api-key', {})
            if api_key.get('key'):
                return api_key['key']
        except:
            pass
    
    return None


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"

EXTRACTION_PROMPT = """Extract entities and relationships from this text.

<text>
{text}
</text>

Return a JSON object with:
- people: list of person names mentioned
- projects: list of project/product names
- tools: list of tools, technologies, services
- decisions: list of decisions made (short phrases)
- facts: list of key facts stated

JSON only, no explanation:"""


class SonnetExtractor:
    """
    Entity extractor using Claude Sonnet.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or get_anthropic_token()
        if not self.api_key:
            print("Warning: No Anthropic API key found")
        
    async def extract(self, text: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Extract entities and facts from text."""
        
        if not self.api_key:
            return self._empty_result()
        
        prompt = EXTRACTION_PROMPT.format(text=text[:8000])  # Limit input
        
        try:
            response = requests.post(
                ANTHROPIC_URL,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL,
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Anthropic API error: {response.status_code} - {response.text[:200]}")
                return self._empty_result()
            
            data = response.json()
            content = data['content'][0]['text']
            
            # Parse JSON from response
            result = self._parse_json(content)
            result['_success'] = True
            return result
            
        except Exception as e:
            print(f"Extraction error: {e}")
            return self._empty_result()
    
    def _parse_json(self, content: str) -> Dict[str, Any]:
        """Extract JSON from response content."""
        import re
        
        # Look for ```json ... ``` block
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if match:
            content = match.group(1)
        
        # Try to parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON object
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
        
        return self._empty_result()
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty extraction result."""
        return {
            '_success': False,
            'people': [],
            'projects': [],
            'tools': [],
            'decisions': [],
            'facts': []
        }


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        extractor = SonnetExtractor()
        
        if not extractor.api_key:
            print("No API key available!")
            return
        
        text = """
        The user and I worked on the Unified Memory Architecture today.
        We decided to use SQLite for the entity graph and keep LanceDB for vectors.
        Key insight: combining graphs + vectors beats either alone.
        Tools used: Python, SQLite, Claude for testing.
        """
        
        print("Testing Sonnet extraction...")
        print(f"Using token: {extractor.api_key[:20]}...")
        result = await extractor.extract(text)
        
        print(f"\nSuccess: {result.get('_success')}")
        print(f"People: {result.get('people', [])}")
        print(f"Projects: {result.get('projects', [])}")
        print(f"Tools: {result.get('tools', [])}")
        print(f"Decisions: {result.get('decisions', [])}")
        print(f"Facts: {result.get('facts', [])}")
    
    asyncio.run(test())
