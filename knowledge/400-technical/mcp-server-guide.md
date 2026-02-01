# MCP Server Development Guide

Source: https://github.com/anthropics/skills/tree/main/skills/mcp-builder

## Overview

Create MCP (Model Context Protocol) servers that enable LLMs to interact with external services.

## Key Principles

### Tool Design
- Balance comprehensive API coverage with workflow tools
- Clear, descriptive names with consistent prefixes (e.g., `github_create_issue`)
- Concise tool descriptions
- Actionable error messages

### Recommended Stack
- **Language**: TypeScript (best SDK support)
- **Transport**: Streamable HTTP for remote, stdio for local

### Implementation Phases

1. **Research & Planning**
   - Study MCP specification
   - Understand target API
   - Plan tool selection

2. **Implementation**
   - Set up project structure
   - Create shared utilities (auth, error handling, pagination)
   - Implement tools with proper schemas

3. **Testing & Refinement**
   - Test each tool
   - Validate error handling
   - Document usage

## Resources
- MCP Spec: https://modelcontextprotocol.io/specification/draft.md
- TypeScript SDK: https://github.com/modelcontextprotocol/typescript-sdk
- Python SDK: https://github.com/modelcontextprotocol/python-sdk
