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


class TestPlayerDisconnection(unittest.TestCase):
    """Testes para desconexão de jogadores durante a partida."""

    def test_two_players_disconnect_during_voting_ends_game(self):
        """
        Com 2 jogadores, se um sair durante a votação, o outro termina de votar
        e o jogo encerra com ranking final (não inicia próxima rodada).
        """
        cb1 = MagicMock()
        cb2 = MagicMock()

        room = Room("Sala2P", "P1", ["Nome", "Fruta"], 3)
        room.add_player("P1", cb1)
        room.add_player("P2", cb2)
        room.start_game("P1")

        # Fase de preenchimento
        room.submit_answers("P1", {"Nome": "Amora", "Fruta": "Abacate"})
        room.submit_answers("P2", {"Nome": "Abelha", "Fruta": "Abacaxi"})
        self.assertEqual(room.state, "VOTING")

        # P2 desconecta durante a votação
        room.remove_player("P2")

        # P2 deve estar em disconnected_players
        self.assertIn("P2", room.disconnected_players)
        # Flag deve estar ativa (restou 1 jogador < MIN_PLAYERS)
        self.assertTrue(room.force_game_over_after_round)
        # Estado ainda deve ser VOTING (esperando P1 votar)
        self.assertEqual(room.state, "VOTING")

        # P1 vota normalmente (inclusive nas palavras de P2)
        room.submit_votes("P1", {
            "Nome": {"P2": True},
            "Fruta": {"P2": True}
        })

        # Votação deve ter encerrado e estado agora é ROUND_END
        self.assertEqual(room.state, "ROUND_END")

        # Pontos de ambos devem ter sido computados
        self.assertIn("P1", room.accumulated_scores)
        self.assertIn("P2", room.accumulated_scores)

        # Simular a transição (normalmente feita pelo timer de 5s)
        room.start_next_round_or_finish()

        # Jogo deve ter encerrado (não iniciou rodada 2)
        self.assertEqual(room.state, "GAME_OVER")
        self.assertEqual(room.current_round, 1)  # Parou na rodada 1

        # on_game_over deve ter sido chamado (no cb1, que ainda está conectado)
        cb1.on_game_over.assert_called()

        room.cleanup()

    def test_three_players_disconnect_during_voting_continues(self):
        """
        Com 3 jogadores, se um sair durante a votação, os outros 2 terminam
        de votar e o jogo continua normalmente na próxima rodada.
        """
        cb1 = MagicMock()
        cb2 = MagicMock()
        cb3 = MagicMock()

        room = Room("Sala3P", "P1", ["Nome"], 3)
        room.add_player("P1", cb1)
        room.add_player("P2", cb2)
        room.add_player("P3", cb3)
        room.start_game("P1")

        # Fase de preenchimento — todos respondem
        room.submit_answers("P1", {"Nome": "Amora"})
        room.submit_answers("P2", {"Nome": "Abelha"})
        room.submit_answers("P3", {"Nome": "Arara"})
        self.assertEqual(room.state, "VOTING")

        # P3 desconecta durante a votação
        room.remove_player("P3")

        # Ainda restam 2 jogadores (>= MIN_PLAYERS), jogo continua
        self.assertFalse(room.force_game_over_after_round)
        self.assertIn("P3", room.disconnected_players)
        self.assertEqual(room.state, "VOTING")

        # P1 e P2 votam normalmente (votam nas palavras de P3 também)
        room.submit_votes("P1", {"Nome": {"P2": True, "P3": True}})
        # Ainda não terminou (falta P2 votar)
        self.assertEqual(room.state, "VOTING")

        room.submit_votes("P2", {"Nome": {"P1": True, "P3": True}})
        # Agora todos os conectados votaram → encerra votação
        self.assertEqual(room.state, "ROUND_END")

        # Pontos de P3 devem ter sido computados
        self.assertIn("P3", room.accumulated_scores)

        # Transição para próxima rodada
        room.start_next_round_or_finish()

        # Jogo deve continuar (não encerrou)
        self.assertEqual(room.state, "FILLING")
        self.assertEqual(room.current_round, 2)

        # disconnected_players deve ter sido limpo para a nova rodada
        self.assertEqual(len(room.disconnected_players), 0)

        # P3 não está mais nos players ativos
        self.assertNotIn("P3", room.players)

        room.cleanup()

    def test_three_players_disconnect_during_filling_unblocks(self):
        """
        Com 3 jogadores, se um sair durante a fase de preenchimento,
        a fase deve avançar quando os outros 2 submeterem.
        """
        cb1 = MagicMock()
        cb2 = MagicMock()
        cb3 = MagicMock()

        room = Room("SalaFill", "P1", ["Nome", "Fruta"], 2)
        room.add_player("P1", cb1)
        room.add_player("P2", cb2)
        room.add_player("P3", cb3)
        room.start_game("P1")
        self.assertEqual(room.state, "FILLING")

        # P1 envia respostas
        room.submit_answers("P1", {"Nome": "Amora", "Fruta": "Abacate"})
        self.assertEqual(room.state, "FILLING")

        # P3 desconecta antes de enviar respostas
        room.remove_player("P3")
        # Ainda FILLING porque P2 não enviou
        self.assertEqual(room.state, "FILLING")

        # P2 envia respostas → agora todos os conectados enviaram
        room.submit_answers("P2", {"Nome": "Abelha", "Fruta": "Abacaxi"})
        # Deve avançar para VOTING
        self.assertEqual(room.state, "VOTING")

        # As respostas de P3 devem ter sido preenchidas com vazio
        self.assertIn("P3", room.current_answers)
        self.assertEqual(room.current_answers["P3"]["Nome"], "")
        self.assertEqual(room.current_answers["P3"]["Fruta"], "")

        room.cleanup()

    def test_two_players_disconnect_during_filling_still_plays(self):
        """
        Com 2 jogadores, se um sair durante o preenchimento, o restante
        termina preenchendo, vota, e o jogo encerra após a votação.
        """
        cb1 = MagicMock()
        cb2 = MagicMock()

        room = Room("SalaFill2", "P1", ["Nome"], 3)
        room.add_player("P1", cb1)
        room.add_player("P2", cb2)
        room.start_game("P1")

        # P2 desconecta durante o preenchimento
        room.remove_player("P2")
        self.assertTrue(room.force_game_over_after_round)
        self.assertEqual(room.state, "FILLING")

        # P1 envia respostas → todos os conectados enviaram
        room.submit_answers("P1", {"Nome": "Amora"})
        self.assertEqual(room.state, "VOTING")

        # P1 vota nas palavras de P2 (que são vazias)
        room.submit_votes("P1", {"Nome": {"P2": True}})
        self.assertEqual(room.state, "ROUND_END")

        # Transição → deve encerrar o jogo
        room.start_next_round_or_finish()
        self.assertEqual(room.state, "GAME_OVER")

        room.cleanup()


if __name__ == "__main__":
    unittest.main()
