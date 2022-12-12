from dataclasses import dataclass
from typing import List, NamedTuple, Optional


Name = NamedTuple("Name", [("forename", str), ("lastname", str)])

@dataclass
class Paper:
    authors: List[Name]
    year: int
    title: str
    doi: str
    url: Optional[str]

    def __str__(self) -> str:
        if len(self.authors) > 2:
            return f"{self.authors[0][1]} et al. {self.year}"
        elif len(self.authors) == 2:
            return f"{self.authors[0][1]} and {self.authors[1][1]} {self.year}"
        else:
            return f"{self.authors[0][1]} {self.year}"