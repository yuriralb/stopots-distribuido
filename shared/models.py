# shared/models.py

from dataclasses import dataclass
from typing import List, Dict, Tuple, Any

@dataclass
class RoomInfo:
    name: str
    host: str
    categories: List[str]
    num_rounds: int
    player_count: int
    status: str  # LOBBY, PLAYING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": str(self.name),
            "host": str(self.host),
            "categories": list(self.categories),
            "num_rounds": int(self.num_rounds),
            "player_count": int(self.player_count),
            "status": str(self.status)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoomInfo":
        return cls(
            name=data["name"],
            host=data["host"],
            categories=list(data["categories"]),
            num_rounds=data["num_rounds"],
            player_count=data["player_count"],
            status=data["status"]
        )

@dataclass
class RoundResult:
    player_scores: Dict[str, int]        # nickname -> pontuação na rodada
    accumulated_scores: Dict[str, int]  # nickname -> pontuação total
    ranking: List[Tuple[str, int]]      # lista de (nickname, pontuação total) em ordem decrescente
    round_number: int
    total_rounds: int
    letter: str
    # details: nickname -> categoria -> {"palavra": str, "pontuação": int, "válido?": bool, "único?": bool}
    details: Dict[str, Dict[str, Dict[str, Any]]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_scores": dict(self.player_scores),
            "accumulated_scores": dict(self.accumulated_scores),
            "ranking": [list(item) for item in self.ranking],
            "round_number": int(self.round_number),
            "total_rounds": int(self.total_rounds),
            "letter": str(self.letter),
            "details": {p: {c: dict(d) for c, d in cats.items()} for p, cats in self.details.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoundResult":
        ranking_list = [tuple(item) for item in data["ranking"]]
        return cls(
            player_scores=dict(data["player_scores"]),
            accumulated_scores=dict(data["accumulated_scores"]),
            ranking=ranking_list,
            round_number=data["round_number"],
            total_rounds=data["total_rounds"],
            letter=data["letter"],
            details=dict(data["details"])
        )
