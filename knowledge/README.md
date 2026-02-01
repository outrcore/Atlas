# Knowledge Library

Dewey Decimal-inspired organization for ATLAS's knowledge base.

## Structure

- **000-reference/** — Quick facts, specs, configs, cheat sheets
- **100-projects/** — Coding projects, repos, documentation
- **200-trading/** — Markets, strategies, trading notes
- **300-personal/** — Matt's preferences, health, goals
- **400-technical/** — Code patterns, learnings, tech docs
- **500-atlas/** — My identity, capabilities, lessons learned

## Usage

Files in this library get indexed into the vector database (LanceDB).
Query with semantic search to find relevant information.

## Indexing

Run `python /workspace/clawd/scripts/index_knowledge.py` to rebuild the index.
