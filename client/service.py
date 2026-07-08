# client/service.py

import rpyc
import threading
from typing import Dict, List, Any

class ClientState:
    def __init__(self):
        self.lock = threading.Lock()

        # Informações do Jogador e Sala
        self.nickname = ""
        self.room_name = ""
        self.players: List[str] = []
        self.categories: List[str] = []
        self.is_host = False

        # Estado do Jogo
        self.game_state = "LOBBY"  # LOBBY, FILLING, VOTING, ROUND_END, GAME_OVER
        self.current_letter = ""
        self.round_number = 0
        self.total_rounds = 0
        self.time_limit = 0
        self.vote_time_per_category = 15  # seconds per category during voting

        # Payloads de Dados
        self.all_answers: Dict[str, Dict[str, str]] = {}
        self.round_results: Dict[str, Any] = {}
        self.final_ranking: List[Any] = []
        self.cancelled_reason = ""

        # Eventos de Sincronização da Thread de UI
        self.game_started_event = threading.Event()
        self.round_started_event = threading.Event()
        self.stop_event = threading.Event()
        self.who_stopped = ""
        self.voting_started_event = threading.Event()
        self.results_received_event = threading.Event()
        self.game_over_event = threading.Event()
        self.cancelled_event = threading.Event()

    def reset_for_round(self):
        self.stop_event.clear()
        self.who_stopped = ""
        self.voting_started_event.clear()
        self.results_received_event.clear()
        self.all_answers.clear()
        self.round_results.clear()

    def reset_all(self):
        self.reset_for_round()
        self.game_started_event.clear()
        self.round_started_event.clear()
        self.game_over_event.clear()
        self.cancelled_event.clear()
        self.players.clear()
        self.categories.clear()
        self.is_host = False
        self.game_state = "LOBBY"


class ClientCallbackService(rpyc.Service):
    def __init__(self, state: ClientState):
        super().__init__()
        self.state = state

    def exposed_on_player_joined(self, nickname: str):
        with self.state.lock:
            if nickname not in self.state.players:
                self.state.players.append(nickname)
        # Avisa o console sem corromper a tela, se possível. (Será tratado na UI)

    def exposed_on_player_left(self, nickname: str):
        with self.state.lock:
            if nickname in self.state.players:
                self.state.players.remove(nickname)

    def exposed_on_game_started(self):
        with self.state.lock:
            self.state.game_state = "FILLING"
        self.state.game_started_event.set()

    def exposed_on_round_started(self, letter: str, round_num: int, total_rounds: int, time_limit: int):
        with self.state.lock:
            self.state.reset_for_round()
            self.state.game_state = "FILLING"
            self.state.current_letter = letter
            self.state.round_number = round_num
            self.state.total_rounds = total_rounds
            self.state.time_limit = time_limit
        self.state.round_started_event.set()

    def exposed_on_stop(self, who_stopped: str):
        with self.state.lock:
            self.state.who_stopped = who_stopped
        self.state.stop_event.set()

    def exposed_on_voting_started(self, all_answers: Dict[str, Dict[str, str]], time_limit: int):
        with self.state.lock:
            self.state.game_state = "VOTING"
            # Converte netrefs do RPyC em dicionários puros do Python
            self.state.all_answers = {p: dict(ans) for p, ans in all_answers.items()}
            self.state.time_limit = time_limit
            # Calcula tempo por categoria a partir do total
            num_cats = len(self.state.categories) if self.state.categories else 1
            self.state.vote_time_per_category = max(1, time_limit // num_cats)
        self.state.voting_started_event.set()

    def exposed_on_round_results(self, results: Dict[str, Any]):
        with self.state.lock:
            self.state.game_state = "ROUND_END"
            self.state.round_results = dict(results)
        self.state.results_received_event.set()

    def exposed_on_game_over(self, final_ranking: List[Any]):
        with self.state.lock:
            self.state.game_state = "GAME_OVER"
            self.state.final_ranking = list(final_ranking)
        self.state.game_over_event.set()
        # Desbloqueia qualquer wait em round_started, voting_started ou results_received
        self.state.round_started_event.set()
        self.state.voting_started_event.set()
        self.state.results_received_event.set()

    def exposed_on_game_cancelled(self, reason: str):
        with self.state.lock:
            self.state.game_state = "GAME_OVER"
            self.state.cancelled_reason = reason
        self.state.cancelled_event.set()
        # Desbloqueia qualquer wait em round_started, voting_started ou results_received
        self.state.round_started_event.set()
        self.state.voting_started_event.set()
        self.state.results_received_event.set()
