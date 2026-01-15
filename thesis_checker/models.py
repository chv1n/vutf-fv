from dataclasses import dataclass
from typing import Tuple, Optional

@dataclass
class Issue:
    page: int
    code: str
    message: str
    severity: str = "error"
    bbox: Optional[Tuple[float, float, float, float]] = None