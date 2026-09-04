from dataclasses import dataclass
from pathlib import Path


@dataclass
class QueryContext:
    data_dir: Path
