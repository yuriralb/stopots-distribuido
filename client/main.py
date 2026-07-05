# client/main.py

import sys
from client.service import ClientState
from client.connection import ServerConnection
from client.ui import TerminalUI
from shared.constants import SERVER_PORT

def main():
    # Inicializa o estado local do cliente
    state = ClientState()
    
    # Inicializa a camada de conexão
    conn = ServerConnection(state)
    
    # Inicializa a interface de usuário
    ui = TerminalUI(state, conn)
    
    print("=" * 55)
    print("        INICIALIZANDO CLIENTE ADEDONALD (RPyC)")
    print("=" * 55)
    
    # Pede o endereço do servidor
    host = input("Digite o IP do servidor (Padrão: localhost): ").strip()
    if not host:
        host = "localhost"
        
    print(f"Conectando ao servidor em {host}:{SERVER_PORT}...")
    if not conn.connect(host, SERVER_PORT):
        print("Não foi possível conectar ao servidor. Verifique se ele está rodando.")
        sys.exit(1)
        
    try:
        # Abre o menu principal
        ui.show_main_menu()
    except KeyboardInterrupt:
        print("\n[Cliente] Recebido sinal de interrupção (Ctrl+C). Encerrando...")
    finally:
        # Garante desconexão limpa
        conn.disconnect()
        print("[Cliente] Desconectado e finalizado.")

if __name__ == "__main__":
    main()
