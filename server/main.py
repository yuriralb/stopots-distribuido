# server/main.py

import rpyc
from rpyc.utils.server import ThreadedServer
from server.room_manager import RoomManager
from server.service import AdedonaldService
from shared.constants import SERVER_PORT

def main():
    print("=" * 65)
    print("       INICIANDO SERVIDOR ADEDONALD (ADEDONHA DISTRIBUÍDA)       ")
    print("=" * 65)
    
    # Instancia o gerenciador de salas
    room_manager = RoomManager()
    
    # Vincula o gerenciador de salas ao serviço RPyC
    AdedonaldService.room_manager = room_manager
    
    # Configura e inicia o servidor multithreaded
    server = ThreadedServer(
        AdedonaldService,
        port=SERVER_PORT,
        protocol_config={
            "allow_public_attrs": True,
            "allow_all_attrs": True
        }
    )
    
    print(f"Servidor ADEDONALD RPyC rodando com sucesso na porta {SERVER_PORT}...")
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[Servidor] Recebido sinal de interrupção (Ctrl+C).")
        print("[Servidor] Encerrando todas as salas e limpando recursos...")
        
        # Limpa todas as salas ativas
        with room_manager.lock:
            for name, room in list(room_manager.rooms.items()):
                room.cleanup()
            room_manager.rooms.clear()
            
        print("[Servidor] Servidor finalizado com sucesso.")

if __name__ == "__main__":
    main()
