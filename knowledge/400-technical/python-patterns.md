# Python Patterns

## Rich TUI
```python
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn

console = Console()

with Live(panel, refresh_per_second=4) as live:
    live.update(new_panel)
```

## Non-blocking Keyboard Input
```python
import sys
import select
import termios
import tty

def get_key_nonblocking():
    if select.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.read(1).lower()
    return None

# Setup
old_settings = termios.tcgetattr(sys.stdin)
tty.setcbreak(sys.stdin.fileno())

# Cleanup
termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
```

## LanceDB Vector Search
```python
import lancedb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
db = lancedb.connect("/path/to/db")

# Index
embedding = model.encode(text).tolist()
table.add([{"text": text, "vector": embedding}])

# Search
query_vec = model.encode(query).tolist()
results = table.search(query_vec).limit(5).to_pandas()
```
