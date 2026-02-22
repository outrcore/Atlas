"""
Cheap Extractor - Uses Fireworks Kimi for entity extraction.

~100x cheaper than Claude for extraction tasks.
$0.10/1M input, $0.30/1M output vs Claude's $15/$75

Created: 2026-02-06
"""

import os
import json
import requests
from typing import Optional, Dict, Any

# Fireworks API config
FIREWORKS_API_KEY = os.environ.get("FIREWORKS_API_KEY", "YOUR_FIREWORKS_API_KEY")
FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
MODEL = "accounts/fireworks/models/minimax-m2-5"

EXTRACTION_PROMPT = """Extract entities from this text as JSON only:

{text}

Return JSON with: people, projects, tools, decisions, facts

JSON:"""


class CheapExtractor:
    """
    Entity extractor using Fireworks Kimi (cheap).
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or FIREWORKS_API_KEY
        
    async def extract(self, text: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Extract entities and facts from text."""
        
        prompt = EXTRACTION_PROMPT.format(text=text[:4000])  # Limit input size
        
        try:
            response = requests.post(
                FIREWORKS_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.1
                },
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Fireworks API error: {response.status_code} - {response.text}")
                return self._empty_result()
            
            data = response.json()
            content = data['choices'][0]['message']['content']
            
            # Parse JSON from response
            result = self._parse_json(content)
            result['_success'] = True
            return result
            
        except Exception as e:
            print(f"Extraction error: {e}")
            return self._empty_result()
    
    def _parse_json(self, content: str) -> Dict[str, Any]:
        """Extract JSON from response content."""
        # Try to find JSON block
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
            'key_entities': {'people': [], 'projects': [], 'tools': [], 'concepts': []},
            'facts': [],
            'decisions': [],
            'action_items': []
        }


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        extractor = CheapExtractor()
        
        text = """
        Matt and I worked on the Unified Memory Architecture today.
        We decided to use SQLite for the entity graph and keep LanceDB for vectors.
        Key insight: combining graphs + vectors beats either alone.
        Tools used: Python, SQLite, Claude for testing.
        """
        
        print("Testing Kimi extraction...")
        result = await extractor.extract(text)
        
        print(f"Success: {result.get('_success')}")
        print(f"Entities: {json.dumps(result.get('key_entities', {}), indent=2)}")
        print(f"Facts: {result.get('facts', [])}")
        print(f"Decisions: {result.get('decisions', [])}")
    
    asyncio.run(test())
