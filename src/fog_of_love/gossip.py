"""The public gossip board: the world posts sightings, never judgments."""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class Post:
    day: int
    text: str
    about: list[str]


class GossipBoard:
    def __init__(self) -> None:
        self.posts: list[Post] = []

    def post(self, day: int, text: str, about: list[str]) -> Post:
        p = Post(day, text, list(about))
        self.posts.append(p)
        return p

    def recent(self, day: int, window: int = 3) -> list[Post]:
        return [p for p in self.posts if day - p.day < window]

    def render(self, day: int, window: int = 3) -> str:
        posts = self.recent(day, window)
        if not posts:
            return "Gossip board (last 3 days): nothing posted."
        return "Gossip board (last 3 days): " + " ".join(f"[day {p.day}] {p.text}" for p in posts)
