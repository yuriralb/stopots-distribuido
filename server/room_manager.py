# server/room_manager.py

import threading
from typing import Dict, List, Optional, Any
from server.room import Room

class RoomManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.rooms: Dict[str, Room] = {}

    def create_room(self, name: str, host: str, categories: List[str], num_rounds: int) -> Optional[Room]:
        with self.lock:
            if name in self.rooms:
                return None
            room = Room(name, host, categories, num_rounds)
            self.rooms[name] = room
            return room

    def list_rooms(self) -> List[Dict[str, Any]]:
        with self.lock:
            lobby_rooms = []
            for room in list(self.rooms.values()):
                info = room.get_info()
                # Exibe apenas salas no lobby que ainda não iniciaram a partida
                if info.status == "LOBBY":
                    lobby_rooms.append(info.to_dict())
            return lobby_rooms

    def get_room(self, name: str) -> Optional[Room]:
        with self.lock:
            return self.rooms.get(name)

    def remove_room(self, name: str):
        with self.lock:
            if name in self.rooms:
                room = self.rooms.pop(name)
                room.cleanup()

    def clean_room_if_needed(self, room_name: str):
        """
        Remove a sala se ela estiver vazia (0 jogadores) ou se já tiver começado a partida
        e possuir apenas 1 ou menos jogadores restantes.
        """
        with self.lock:
            if room_name in self.rooms:
                room = self.rooms[room_name]
                with room.lock:
                    num_players = len(room.players)
                    status = room.state
                
                if num_players == 0:
                    del self.rooms[room_name]
                    room.cleanup()
                    print(f"[RoomManager] Sala '{room_name}' limpa e removida do sistema.")
