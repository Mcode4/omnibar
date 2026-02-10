from dataclasses import dataclass
from typing import Optional

@dataclass
class CommandResult:
    success: bool
    message: str
    data: Optional[dict] = None