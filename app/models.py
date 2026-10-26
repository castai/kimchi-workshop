"""Task model and validation rules."""
from dataclasses import dataclass, asdict


@dataclass
class Task:
    id: int
    title: str
    priority: int = 1
    status: str = "open"
    created_at: str = ""
    completed_at: str = ""
    updated_at: str = ""

    def to_dict(self):
        return asdict(self)


def validate_priority(priority):
    """Priority is an integer 1-5. Raises ValueError otherwise."""
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError("priority must be an integer")
    if not 1 <= priority <= 5:
        raise ValueError("priority must be between 1 and 5")
    return priority
