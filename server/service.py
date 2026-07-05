# server/service.py

import rpyc
from typing import List, Dict, Any

class AdedonaldService(rpyc.Service):
    room_manager = None  # Definido na inicialização do servidor

    def on_connect(self, conn):
        self._conn = conn
        self.nickname = None
        self.room_name = None
        print(f"[Service] Conexão recebida de: {conn}")

    def on_disconnect(self, conn):
        if self.nickname and self.room_name:
            print(f"[Service] Conexão perdida com {self.nickname} da sala '{self.room_name}'")
            room = self.room_manager.get_room(self.room_name)
            if room:
                room.remove_player(self.nickname)
                self.room_manager.clean_room_if_needed(self.room_name)
            self.nickname = None
            self.room_name = None

    def exposed_create_room(self, name: str, categories: List[str], num_rounds: int, nickname: str) -> bool:
        if not self.room_manager:
            return False
        
        # Cria a sala com o nickname como host
        room = self.room_manager.create_room(name, nickname, categories, num_rounds)
        if not room:
            return False
            
        # Conecta o host
        callback = self._conn.root
        success = room.add_player(nickname, callback)
        if success:
            self.nickname = nickname
            self.room_name = name
            print(f"[Service] Sala '{name}' criada pelo host '{nickname}'.")
            return True
        else:
            self.room_manager.remove_room(name)
            return False

    def exposed_list_rooms(self) -> List[Dict[str, Any]]:
        if not self.room_manager:
            return []
        return self.room_manager.list_rooms()

    def exposed_join_room(self, room_name: str, nickname: str) -> Any:
        if not self.room_manager:
            return None
            
        room = self.room_manager.get_room(room_name)
        if not room:
            return None
            
        callback = self._conn.root
        success = room.add_player(nickname, callback)
        if success:
            self.nickname = nickname
            self.room_name = room_name
            print(f"[Service] Jogador '{nickname}' entrou na sala '{room_name}'.")
            # Retorna categorias e lista de jogadores atualmente na sala
            with room.lock:
                current_players = list(room.players.keys())
            return {"categories": list(room.categories), "players": current_players}
        return None

    def exposed_leave_room(self, nickname: str):
        if self.room_name and self.nickname == nickname:
            room = self.room_manager.get_room(self.room_name)
            if room:
                room.remove_player(nickname)
                self.room_manager.clean_room_if_needed(self.room_name)
            print(f"[Service] Jogador '{nickname}' saiu voluntariamente da sala '{self.room_name}'.")
            self.nickname = None
            self.room_name = None

    def exposed_start_game(self, nickname: str) -> bool:
        if not self.room_name:
            return False
        room = self.room_manager.get_room(self.room_name)
        if not room:
            return False
        return room.start_game(nickname)

    def exposed_submit_answers(self, nickname: str, answers: Dict[str, str]):
        if not self.room_name:
            return
        room = self.room_manager.get_room(self.room_name)
        if room:
            room.submit_answers(nickname, answers)

    def exposed_request_stop(self, nickname: str, answers: Dict[str, str]) -> bool:
        if not self.room_name:
            return False
        room = self.room_manager.get_room(self.room_name)
        if room:
            return room.request_stop(nickname, answers)
        return False

    def exposed_submit_votes(self, nickname: str, votes: Dict[str, Dict[str, bool]]):
        if not self.room_name:
            return
        room = self.room_manager.get_room(self.room_name)
        if room:
            room.submit_votes(nickname, votes)
