# client/connection.py

import rpyc
from typing import List, Dict, Optional, Any
from client.service import ClientCallbackService, ClientState

class ServerConnection:
    def __init__(self, state: ClientState):
        self.state = state
        self.conn: Optional[rpyc.Connection] = None
        self.bg_thread: Optional[rpyc.BgServingThread] = None
        self._host: str = "localhost"
        self._port: int = 18861

    def connect(self, host: str, port: int) -> bool:
        self._host = host
        self._port = port
        try:
            # Estabelece conexão com o servidor passando nosso serviço de callback
            self.conn = rpyc.connect(
                host,
                port,
                service=ClientCallbackService(self.state),
                config={
                    "allow_public_attrs": True,
                    "allow_all_attrs": True
                }
            )
            # BgServingThread atua em background tratando requisições remotas (callbacks)
            # vindas do servidor enquanto a thread da UI principal aguarda input do usuário.
            self.bg_thread = rpyc.BgServingThread(self.conn)
            return True
        except Exception as e:
            print(f"Erro ao conectar ao servidor {host}:{port}: {e}")
            self.conn = None
            self.bg_thread = None
            return False

    def reconnect(self) -> bool:
        """Reconecta ao servidor, recriando a conexão RPyC do zero."""
        self._close_connection()
        self.state.reset_all()
        return self.connect(self._host, self._port)

    def _close_connection(self):
        """Fecha a conexão RPyC e o BgServingThread de forma segura."""
        if self.bg_thread:
            try:
                self.bg_thread.stop()
            except Exception:
                pass
            self.bg_thread = None

        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def _is_connection_alive(self) -> bool:
        """Verifica se a conexão RPyC ainda está funcional."""
        if not self.conn:
            return False
        try:
            self.conn.ping()
            return True
        except Exception:
            return False

    def _ensure_connection(self) -> bool:
        """Garante que existe uma conexão ativa, reconectando se necessário."""
        if self._is_connection_alive():
            return True
        print("[Conexão] Conexão perdida. Reconectando ao servidor...")
        return self.reconnect()

    def disconnect(self):
        # Tenta notificar o servidor sobre a saída antes de fechar a conexão
        if self.conn and self.state.nickname:
            try:
                self.conn.root.leave_room(self.state.nickname)
            except Exception:
                pass

        self._close_connection()
        self.state.reset_all()

    def create_room(self, name: str, categories: List[str], num_rounds: int, nickname: str) -> bool:
        if not self._ensure_connection():
            return False
        try:
            success = self.conn.root.create_room(name, categories, num_rounds, nickname)
            if success:
                self.state.nickname = nickname
                self.state.room_name = name
                self.state.is_host = True
                self.state.categories = list(categories)
                with self.state.lock:
                    if nickname not in self.state.players:
                        self.state.players.append(nickname)
                return True
            return False
        except Exception as e:
            print(f"Erro ao criar sala: {e}")
            return False

    def list_rooms(self) -> List[Dict[str, Any]]:
        if not self._ensure_connection():
            return []
        try:
            # Converte a resposta do RPyC em uma lista nativa do Python
            return [dict(room) for room in self.conn.root.list_rooms()]
        except Exception as e:
            print(f"Erro ao listar salas: {e}")
            return []

    def join_room(self, name: str, nickname: str) -> bool:
        if not self._ensure_connection():
            return False
        try:
            res = self.conn.root.join_room(name, nickname)
            if res is not None:
                self.state.nickname = nickname
                self.state.room_name = name
                self.state.is_host = False
                self.state.categories = list(res["categories"])
                # Popula a lista de jogadores com todos os que já estão na sala
                with self.state.lock:
                    self.state.players = list(res["players"])
                return True
            return False
        except Exception as e:
            print(f"Erro ao entrar na sala: {e}")
            return False

    def leave_room(self):
        # Captura o nickname antes de limpar o estado
        nickname = self.state.nickname
        if not self.conn or not nickname:
            self.state.reset_all()
            return
        try:
            self.conn.root.leave_room(nickname)
        except Exception as e:
            print(f"Erro ao sair da sala: {e}")
        finally:
            self.state.reset_all()

    def start_game(self) -> bool:
        if not self.conn or not self.state.is_host:
            return False
        try:
            return self.conn.root.start_game(self.state.nickname)
        except Exception as e:
            print(f"Erro ao iniciar partida: {e}")
            return False

    def submit_answers(self, answers: Dict[str, str]):
        if not self.conn:
            return
        try:
            # Envia as respostas convertendo para dict nativo
            self.conn.root.submit_answers(self.state.nickname, dict(answers))
        except Exception as e:
            print(f"Erro ao submeter respostas: {e}")

    def request_stop(self, answers: Dict[str, str]) -> bool:
        if not self.conn:
            return False
        try:
            return self.conn.root.request_stop(self.state.nickname, dict(answers))
        except Exception as e:
            print(f"Erro ao solicitar STOP: {e}")
            return False

    def submit_votes(self, votes: Dict[str, Dict[str, bool]]):
        if not self.conn:
            return
        try:
            # Converte o payload de votos aninhados para dict nativo do Python
            native_votes = {cat: dict(p_votes) for cat, p_votes in votes.items()}
            self.conn.root.submit_votes(self.state.nickname, native_votes)
        except Exception as e:
            print(f"Erro ao enviar votos: {e}")

