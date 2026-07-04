# test_game.py

import unittest
from unittest.mock import MagicMock
import time
import threading

import server.game_engine as engine
from server.room import Room
from server.room_manager import RoomManager
from shared.constants import POINTS_UNIQUE, POINTS_REPEATED, POINTS_INVALID

class TestGameEngine(unittest.TestCase):
    def test_normalize_word(self):
        self.assertEqual(engine.normalize_word("  Banana  "), "banana")
        self.assertEqual(engine.normalize_word("Água"), "agua")
        self.assertEqual(engine.normalize_word("Cachorro-Quente"), "cachorro-quente")
        self.assertEqual(engine.normalize_word(""), "")

    def test_is_word_valid(self):
        self.assertTrue(engine.is_word_valid("Abelha", "A"))
        self.assertTrue(engine.is_word_valid("águia", "A"))
        self.assertTrue(engine.is_word_valid("bola", "b"))
        self.assertFalse(engine.is_word_valid("Bola", "C"))
        self.assertFalse(engine.is_word_valid("", "A"))

    def test_tally_votes(self):
        players = ["P1", "P2", "P3"]
        categories = ["Nome", "Fruta"]
        
        # P1's word "Amora" is voted:
        # P2: True (valid), P3: False (invalid) -> Tie (1-1) -> Approved (True)
        # P2's word "Abacaxi" is voted:
        # P1: False (invalid), P3: False (invalid) -> Rejected (0-2) -> Rejected (False)
        votes = {
            "P1": {
                "Nome": {"P2": False, "P3": True},
                "Fruta": {"P2": False, "P3": True}
            },
            "P2": {
                "Nome": {"P1": True, "P3": True},
                "Fruta": {"P1": True, "P3": True}
            },
            "P3": {
                "Nome": {"P1": False, "P2": False},
                "Fruta": {"P1": True, "P2": False}
            }
        }
        
        answers = {
            "P1": {"Nome": "Amora", "Fruta": "Amora"},
            "P2": {"Nome": "Abacaxi", "Fruta": "Abacaxi"},
            "P3": {"Nome": "Abelha", "Fruta": "Abelha"}
        }
        
        approvals = engine.tally_votes(players, categories, votes, answers)
        
        # P1's "Amora" has 1 invalid (P3) and 1 valid (P2) -> tie -> valid
        self.assertTrue(approvals["P1"]["Nome"])
        
        # P2's "Abacaxi" has 2 invalid (P1, P3) -> rejected
        self.assertFalse(approvals["P2"]["Nome"])

    def test_calculate_scores(self):
        players = ["P1", "P2", "P3"]
        categories = ["Nome", "Fruta"]
        letter = "A"
        
        answers = {
            "P1": {"Nome": "Amora", "Fruta": "Abacate"},
            "P2": {"Nome": "Amora", "Fruta": "Abacaxi"},
            "P3": {"Nome": "Abelha", "Fruta": "Abacaxi"}
        }
        
        approvals = {
            "P1": {"Nome": True, "Fruta": True},
            "P2": {"Nome": True, "Fruta": True},
            "P3": {"Nome": True, "Fruta": True}
        }
        
        scores, details = engine.calculate_scores(players, categories, letter, answers, approvals)
        
        # Nome:
        # P1: Amora (repeated with P2) -> 5 pts
        # P2: Amora (repeated with P1) -> 5 pts
        # P3: Abelha (unique) -> 10 pts
        # Fruta:
        # P1: Abacate (unique) -> 10 pts
        # P2: Abacaxi (repeated with P3) -> 5 pts
        # P3: Abacaxi (repeated with P2) -> 5 pts
        
        self.assertEqual(scores["P1"], 15)
        self.assertEqual(scores["P2"], 10)
        self.assertEqual(scores["P3"], 15)
        
        self.assertTrue(details["P3"]["Nome"]["unique"])
        self.assertFalse(details["P2"]["Nome"]["unique"])


class TestRoomLifecycle(unittest.TestCase):
    def test_room_lobby_and_transitions(self):
        cb1 = MagicMock()
        cb2 = MagicMock()
        
        room = Room("SalaTeste", "P1", ["Nome", "Fruta"], 2)
        
        # Add players
        self.assertTrue(room.add_player("P1", cb1))
        self.assertTrue(room.add_player("P2", cb2))
        
        # Rejects duplicate name
        self.assertFalse(room.add_player("P1", cb1))
        
        # Start game
        self.assertTrue(room.start_game("P1"))
        self.assertEqual(room.state, "FILLING")
        self.assertIsNotNone(room.letter)
        
        # Submit answers
        ans_p1 = {"Nome": "Amora", "Fruta": "Abacate"}
        ans_p2 = {"Nome": "Abelha", "Fruta": "Abacaxi"}
        
        room.submit_answers("P1", ans_p1)
        # Should not end filling yet
        self.assertEqual(room.state, "FILLING")
        
        # Request STOP for P1 (should fail as P2 hasn't filled but wait, the plan is:
        # "O cliente pode acionar o STOP a qualquer momento, desde que todas as categorias estejam preenchidas [localmente]"
        # P1 has filled all categories, so P1 can request STOP:
        self.assertTrue(room.request_stop("P1", ans_p1))
        # Grace timer starts, state is still FILLING
        self.assertEqual(room.state, "FILLING")
        
        # Submit P2 answers to complete the phase
        room.submit_answers("P2", ans_p2)
        
        # Now filling phase should end and voting starts
        # (It can happen immediately if all players submitted, which we just did)
        self.assertEqual(room.state, "VOTING")
        
        # Tidy up timers
        room.cleanup()


if __name__ == "__main__":
    unittest.main()
