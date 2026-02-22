#!/usr/bin/env python3
"""
Fireworks.ai Client - Kimi K2.5 for cheap sub-agent inference

Usage:
    from fireworks_client import FireworksClient
    
    client = FireworksClient()
    response = client.chat("What is 2+2?")
    print(response)
    
    # Or with full messages
    response = client.chat_messages([
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello!"}
    ])
"""

import os
import json
import requests
from typing import List, Dict, Optional
from pathlib import Path

# Load API key from .env
def load_api_key() -> str:
    env_path = Path("/workspace/clawd/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("FIREWORKS_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("FIREWORKS_API_KEY", "")


class FireworksClient:
    """Client for Fireworks.ai API - optimized for Kimi K2.5"""
    
    BASE_URL = "https://api.fireworks.ai/inference/v1"
    
    # Available models
    MODELS = {
        "kimi-k2.5": "accounts/fireworks/models/kimi-k2p5",
        "kimi-k2-thinking": "accounts/fireworks/models/kimi-k2-thinking",
        "kimi-k2-instruct": "accounts/fireworks/models/kimi-k2-instruct-0905",
    }
    
    def __init__(self, api_key: Optional[str] = None, model: str = "kimi-k2.5", extract_code: bool = True):
        self.api_key = api_key or load_api_key()
        if not self.api_key:
            raise ValueError("No Fireworks API key found. Set FIREWORKS_API_KEY or pass api_key.")
        
        self.model = self.MODELS.get(model, model)
        self.extract_code = extract_code  # Auto-extract code blocks from thinking models
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Track usage
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0
    
    def _extract_code_blocks(self, content: str) -> str:
        """Extract code blocks from thinking model output."""
        import re
        # Find all code blocks
        code_blocks = re.findall(r'```(?:\w*)\n?(.*?)```', content, re.DOTALL)
        if code_blocks:
            # Return the last (usually most complete) code block
            return code_blocks[-1].strip()
        return content  # Return original if no code blocks
    
    def chat(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        extract_code: Optional[bool] = None,
    ) -> str:
        """Simple chat completion - returns just the response text.
        
        Args:
            extract_code: If True, extract code blocks from response. 
                          Defaults to self.extract_code setting.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        result = self.chat_messages(messages, max_tokens, temperature)
        content = result.get("content", "")
        
        # Extract code if enabled and this looks like a code request
        should_extract = extract_code if extract_code is not None else self.extract_code
        if should_extract and '```' in content:
            return self._extract_code_blocks(content)
        return content
    
    def chat_messages(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> Dict:
        """Full chat completion with messages array."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        response = requests.post(
            f"{self.BASE_URL}/chat/completions",
            headers=self.headers,
            json=payload,
            timeout=120
        )
        
        if response.status_code != 200:
            return {
                "error": True,
                "status_code": response.status_code,
                "message": response.text
            }
        
        data = response.json()
        
        # Track usage
        usage = data.get("usage", {})
        self.total_input_tokens += usage.get("prompt_tokens", 0)
        self.total_output_tokens += usage.get("completion_tokens", 0)
        self.total_requests += 1
        
        # Extract response
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        return {
            "content": content,
            "usage": usage,
            "model": self.model,
            "finish_reason": data.get("choices", [{}])[0].get("finish_reason"),
        }
    
    def get_usage_stats(self) -> Dict:
        """Get accumulated usage statistics."""
        # Pricing: $0.10/1M input, $0.30/1M output
        input_cost = (self.total_input_tokens / 1_000_000) * 0.10
        output_cost = (self.total_output_tokens / 1_000_000) * 0.30
        
        return {
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": round(input_cost + output_cost, 6),
        }
    
    def list_models(self) -> List[str]:
        """List available models."""
        response = requests.get(
            f"{self.BASE_URL}/models",
            headers=self.headers,
            timeout=30
        )
        if response.status_code == 200:
            return [m["id"] for m in response.json().get("data", [])]
        return []


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python fireworks_client.py 'Your prompt here'")
        print("       python fireworks_client.py --models  # List available models")
        sys.exit(1)
    
    client = FireworksClient()
    
    if sys.argv[1] == "--models":
        print("Available Kimi models:")
        for name, model_id in client.MODELS.items():
            print(f"  {name}: {model_id}")
    else:
        prompt = " ".join(sys.argv[1:])
        print(f"Prompt: {prompt}\n")
        response = client.chat(prompt)
        print(f"Response: {response}\n")
        print(f"Usage: {client.get_usage_stats()}")
