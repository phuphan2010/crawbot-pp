from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class Post:
    post_id: str
    author: str
    date: str
    text: str
    image_urls: List[str]
    video_urls: List[str]
    post_url: str
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_row(self) -> list:
        return [
            self.scraped_at,
            self.author,
            self.date,
            self.text,
            " | ".join(self.image_urls),
            " | ".join(self.video_urls),
            self.post_url,
        ]
