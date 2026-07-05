# server/room.py

import threading
import rpyc
from typing import Dict, List, Set, Any, Optional
from shared.constants import (
    FILL_TIME_PER_CATEGORY, VOTE_TIME_PER_CATEGORY,
    MIN_PLAYERS, GRACE_PERIOD
)
from shared.models import RoomInfo, RoundResult
import server.game_engine as engine

class Room:
    def __init__(self, name: str, host: str, categories: List[str], num_rounds: int):
        self.name = str(name)
        self.host = str(host)
        self.categories = [str(c) for c in categories]
        self.num_rounds = int(num_rounds)
        self.current_round = 0
        
        # lock for thread-safe state modifications
        self.lock = threading.Lock()
        
        # players: nickname -> RPyC connection root (callback receiver)
        self.players: Dict[str, Any] = {}
        
        self.state = "LOBBY"  # LOBBY, FILLING, VOTING, ROUND_END, GAME_OVER
        self.used_letters: Set[str] = set()
        self.accumulated_scores: Dict[str, int] = {}
        
        # Round-specific states
        self.letter = ""
        self.current_answers: Dict[str, Dict[str, str]] = {}  # nickname -> category -> word
        self.current_votes: Dict[str, Dict[str, Dict[str, bool]]] = {}  # nickname -> category -> player -> valid
        
        # Timers
        self.filling_timer: Optional[threading.Timer] = None
        self.grace_timer: Optional[threading.Timer] = None
        self.voting_timer: Optional[threading.Timer] = None
        self.results_timer: Optional[threading.Timer] = None

    def get_info(self) -> RoomInfo:
        with self.lock:
            return RoomInfo(
                name=self.name,
                host=self.host,
                categories=self.categories,
                num_rounds=self.num_rounds,
                player_count=len(self.players),
                status=self.state
            )

    def add_player(self, nickname: str, callback: Any) -> bool:
        with self.lock:
            if self.state != "LOBBY":
                return False
            if nickname in self.players:
                return False
            
            self.players[nickname] = callback
            self.accumulated_scores[nickname] = 0
            
            # If host left earlier and list was empty, re-assign host
            if not self.host or self.host not in self.players:
                self.host = nickname
                
        # Notify after releasing lock to avoid deadlocks
        self.notify_all("on_player_joined", nickname)
        return True

    def remove_player(self, nickname: str):
        game_cancelled = False
        host_left_lobby = False
        empty_room = False
        check_filling = False
        check_voting = False
        should_notify_left = False

        with self.lock:
            if nickname not in self.players:
                return
            
            is_host = (self.host == nickname)
            was_lobby = (self.state == "LOBBY")
            
            del self.players[nickname]
            # Keep the accumulated score for history, but player is no longer active
            
            if not self.players:
                empty_room = True
            elif is_host and was_lobby:
                # Host saiu do lobby — fechar a sala para todos
                host_left_lobby = True
            else:
                should_notify_left = True
                # Reassign host if the host disconnected during game
                if is_host:
                    self.host = list(self.players.keys())[0]
            
            # Check player count if game is active
            if self.state != "LOBBY" and not empty_room and not host_left_lobby:
                if len(self.players) < MIN_PLAYERS:
                    game_cancelled = True
                else:
                    # If game is running, check if this disconnection unblocks the current phase
                    if self.state == "FILLING":
                        check_filling = True
                    elif self.state == "VOTING":
                        check_voting = True
                        
        if empty_room:
            self.cleanup()
            return
        
        if host_left_lobby:
            self.cancel_game("O host encerrou a sala.")
            return
        
        # Notify after releasing lock to avoid deadlock
        if should_notify_left:
            self.notify_all("on_player_left", nickname)
            
        if game_cancelled:
            self.cancel_game("Jogadores insuficientes para continuar a partida.")
            return

        if check_filling:
            self._check_and_end_filling_if_complete()
            
        if check_voting:
            self._check_and_end_voting_if_complete()

    def start_game(self, nickname: str) -> bool:
        with self.lock:
            if nickname != self.host:
                return False
            if len(self.players) < MIN_PLAYERS:
                return False
            if self.state != "LOBBY":
                return False
            
            self.state = "PLAYING"
            self.current_round = 1
            
        self.notify_all("on_game_started")
        self.start_round()
        return True

    def start_round(self):
        with self.lock:
            self.state = "FILLING"
            self.letter = engine.draw_letter(self.used_letters)
            self.current_answers = {}
            self.current_votes = {}
            
            time_limit = FILL_TIME_PER_CATEGORY * len(self.categories)
            
            # Start global filling timer
            self._cancel_timer("filling")
            self._cancel_timer("grace")
            self.filling_timer = threading.Timer(time_limit, self._on_filling_timeout)
            self.filling_timer.daemon = True
            self.filling_timer.start()
            
        self.notify_all(
            "on_round_started",
            self.letter,
            self.current_round,
            self.num_rounds,
            time_limit
        )

    def submit_answers(self, nickname: str, answers: Dict[str, str]):
        with self.lock:
            if self.state != "FILLING":
                return
            
            # Validate categories
            sanitized = {}
            for cat in self.categories:
                sanitized[cat] = str(answers.get(cat, "")).strip()
            
            self.current_answers[nickname] = sanitized
            
        self._check_and_end_filling_if_complete()

    def request_stop(self, nickname: str, answers: Dict[str, str]) -> bool:
        with self.lock:
            if self.state != "FILLING":
                return False
            
            # Validate and save answers first
            sanitized = {}
            for cat in self.categories:
                sanitized[cat] = str(answers.get(cat, "")).strip()
            self.current_answers[nickname] = sanitized
            
            # Ensure the requesting player filled all categories
            has_all_filled = len(sanitized) == len(self.categories) and all(v != "" for v in sanitized.values())
            
            if not has_all_filled:
                return False
            
            # Cancel general filling timer, start grace timer (5s) for remaining submissions
            self._cancel_timer("filling")
            self._cancel_timer("grace")
            self.grace_timer = threading.Timer(GRACE_PERIOD, self._on_grace_timeout)
            self.grace_timer.daemon = True
            self.grace_timer.start()
            
        self.notify_all("on_stop", nickname)
        return True

    def submit_votes(self, nickname: str, votes: Dict[str, Dict[str, bool]]):
        with self.lock:
            if self.state != "VOTING":
                return
            
            # Format: votes = { category: { player: is_valid } }
            # Validate input structure
            sanitized_votes = {}
            for cat in self.categories:
                sanitized_votes[cat] = {}
                cat_votes = votes.get(cat, {})
                for p in self.players:
                    if p != nickname:
                        sanitized_votes[cat][p] = bool(cat_votes.get(p, True))
            
            self.current_votes[nickname] = sanitized_votes
            
        self._check_and_end_voting_if_complete()

    def _check_and_end_filling_if_complete(self):
        end_phase = False
        with self.lock:
            if self.state == "FILLING":
                # Check if all active players have submitted
                # (A submission counts if its key exists in current_answers)
                all_submitted = all(p in self.current_answers for p in self.players)
                if all_submitted:
                    end_phase = True
                    
        if end_phase:
            self.end_filling_phase()

    def _on_filling_timeout(self):
        # Called when the global filling timer expires
        self.end_filling_phase()

    def _on_grace_timeout(self):
        # Called when the STOP grace timer (5s) expires
        self.end_filling_phase()

    def end_filling_phase(self):
        with self.lock:
            if self.state != "FILLING":
                return
            
            self._cancel_timer("filling")
            self._cancel_timer("grace")
            
            self.state = "VOTING"
            
            # Fill missing answers with empty strings for players who didn't submit
            for p in self.players:
                if p not in self.current_answers:
                    self.current_answers[p] = {cat: "" for cat in self.categories}
            
            time_limit = VOTE_TIME_PER_CATEGORY * len(self.categories)
            
            self._cancel_timer("voting")
            self.voting_timer = threading.Timer(time_limit, self._on_voting_timeout)
            self.voting_timer.daemon = True
            self.voting_timer.start()
            
            # Deep copy answers dictionary to avoid threading netref issues
            answers_payload = {p: dict(ans) for p, ans in self.current_answers.items()}
            
        self.notify_all("on_voting_started", answers_payload, time_limit)

    def _check_and_end_voting_if_complete(self):
        end_phase = False
        with self.lock:
            if self.state == "VOTING":
                all_voted = all(p in self.current_votes for p in self.players)
                if all_voted:
                    end_phase = True
                    
        if end_phase:
            self.end_voting_phase()

    def _on_voting_timeout(self):
        self.end_voting_phase()

    def end_voting_phase(self):
        with self.lock:
            if self.state != "VOTING":
                return
            
            self._cancel_timer("voting")
            self.state = "ROUND_END"
            
            players_list = list(self.players.keys())
            
            # Fill missing votes with True (valid)
            for p in players_list:
                if p not in self.current_votes:
                    self.current_votes[p] = {
                        cat: {other: True for other in players_list if other != p}
                        for cat in self.categories
                    }
            
            # Tally votes & calculate scores
            approvals = engine.tally_votes(
                players_list,
                self.categories,
                self.current_votes,
                self.current_answers
            )
            
            round_scores, details = engine.calculate_scores(
                players_list,
                self.categories,
                self.letter,
                self.current_answers,
                approvals
            )
            
            # Update cumulative scores
            for p, score in round_scores.items():
                self.accumulated_scores[p] = self.accumulated_scores.get(p, 0) + score
                
            # Build ranking
            sorted_ranking = sorted(
                self.accumulated_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            # Create serialized RoundResult
            result = RoundResult(
                player_scores=round_scores,
                accumulated_scores=dict(self.accumulated_scores),
                ranking=sorted_ranking,
                round_number=self.current_round,
                total_rounds=self.num_rounds,
                letter=self.letter,
                details=details
            )
            
            result_payload = result.to_dict()
            
            # Set up timer to transition to the next round (or finish) after 5s
            self._cancel_timer("results")
            self.results_timer = threading.Timer(5, self.start_next_round_or_finish)
            self.results_timer.daemon = True
            self.results_timer.start()
            
        self.notify_all("on_round_results", result_payload)

    def start_next_round_or_finish(self):
        should_start_round = False
        should_end_game = False
        final_ranking = []

        with self.lock:
            if self.state != "ROUND_END":
                return
            
            self._cancel_timer("results")
            
            if self.current_round < self.num_rounds:
                self.current_round += 1
                should_start_round = True
            else:
                self.state = "GAME_OVER"
                should_end_game = True
                final_ranking = sorted(
                    self.accumulated_scores.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                
        if should_start_round:
            self.start_round()
        elif should_end_game:
            self.notify_all("on_game_over", final_ranking)
            self.cleanup()

    def cancel_game(self, reason: str):
        with self.lock:
            self.cleanup()
            self.state = "GAME_OVER"
        self.notify_all("on_game_cancelled", reason)

    def notify_all(self, event_name: str, *args):
        # Thread-safe copy of callbacks
        with self.lock:
            active_players = list(self.players.items())
            
        for nickname, callback in active_players:
            try:
                # Call callback method asynchronously to prevent deadlocks
                func = getattr(callback, event_name, None)
                if func:
                    try:
                        async_func = rpyc.async_(func)
                        async_func(*args)
                    except TypeError:
                        # Fallback se for um objeto local (como MagicMock nos testes unitários)
                        func(*args)
            except Exception as e:
                # Print connection errors locally on server console
                print(f"[{self.name}] Erro ao notificar {nickname} ({event_name}): {e}")

    def _cancel_timer(self, timer_name: str):
        timer = getattr(self, f"{timer_name}_timer", None)
        if timer:
            timer.cancel()
            setattr(self, f"{timer_name}_timer", None)

    def cleanup(self):
        # Cancel all timers to release threads
        self._cancel_timer("filling")
        self._cancel_timer("grace")
        self._cancel_timer("voting")
        self._cancel_timer("results")
