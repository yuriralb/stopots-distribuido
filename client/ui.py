# client/ui.py

import os
import sys
import time
import select
import termios
import tty
from typing import List, Dict, Any, Tuple, Optional
from client.service import ClientState
from client.connection import ServerConnection
from shared.constants import DEFAULT_CATEGORIES, MIN_PLAYERS

# Cores ANSI para deixar o terminal premium
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

def clear_screen():
    # Limpa a tela e posiciona o cursor no topo
    print("\033[H\033[J", end="")

def input_with_timer_and_stop_event(prompt: str, stop_event: Any, timeout_at: float) -> Optional[str]:
    """
    Lê uma entrada do usuário no Linux de forma não-bloqueante caractere a caractere.
    Atualiza o cronômetro visual em tempo real no prompt.
    Retorna o texto digitado, ou None se o tempo expirou ou o STOP foi acionado no servidor.
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    buffer = ""
    try:
        # Define modo cbreak (lê caractere a caractere sem esperar newline, mas preserva sinais como Ctrl+C)
        tty.setcbreak(fd)
        
        while not stop_event.is_set():
            time_left = max(0, int(timeout_at - time.time()))
            if time_left <= 0:
                break
            
            # Desenha o prompt com o timer (cor azul) e o buffer digitado
            sys.stdout.write(f"\r\033[K[{BLUE}Tempo: {time_left}s{RESET}] {prompt}{buffer}")
            sys.stdout.flush()
            
            # Monitora a entrada do stdin com timeout curto para checar stop_event e atualizar timer
            rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
            if rlist:
                char = sys.stdin.read(1)
                if char == '\n' or char == '\r':
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    return buffer.strip()
                elif char in ('\x7f', '\x08'):  # Backspace
                    buffer = buffer[:-1]
                elif char == '\x03':  # Ctrl+C
                    raise KeyboardInterrupt()
                elif ord(char) >= 32:  # Caracteres imprimíveis
                    buffer += char
        
        sys.stdout.write("\n")
        sys.stdout.flush()
        return buffer.strip() if buffer else None
    finally:
        # Restaura configurações normais do terminal
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


class TerminalUI:
    def __init__(self, state: ClientState, conn: ServerConnection):
        self.state = state
        self.conn = conn

    def show_banner(self):
        print(f"{CYAN}{BOLD}" + "=" * 55)
        print("          STOPOTS — JOGO DE ADEDONHA ONLINE (RPyC)     ")
        print("=" * 55 + f"{RESET}")

    def show_main_menu(self):
        while True:
            clear_screen()
            self.show_banner()
            print(f"{BOLD}1.{RESET} Criar Sala")
            print(f"{BOLD}2.{RESET} Listar Salas Disponíveis")
            print(f"{BOLD}3.{RESET} Entrar em uma Sala")
            print(f"{BOLD}4.{RESET} Sair")
            print("-" * 55)
            choice = input(f"{BOLD}Escolha uma opção (1-4): {RESET}").strip()
            
            if choice == "1":
                self.action_create_room()
            elif choice == "2":
                self.action_list_rooms()
            elif choice == "3":
                self.action_join_room()
            elif choice == "4":
                print("Obrigado por jogar STOPOTS!")
                self.conn.disconnect()
                sys.exit(0)
            else:
                print(f"{RED}Opção inválida!{RESET}")
                time.sleep(1)

    def action_create_room(self):
        clear_screen()
        self.show_banner()
        print(f"{BOLD}=== CRIAR SALA ==={RESET}\n")
        
        nickname = input("Digite seu Nickname: ").strip()
        if not nickname:
            print(f"{RED}Nickname não pode ser vazio!{RESET}")
            time.sleep(1.5)
            return

        room_name = input("Nome da Sala: ").strip()
        if not room_name:
            print(f"{RED}Nome da sala não pode ser vazio!{RESET}")
            time.sleep(1.5)
            return

        print(f"\nCategorias padrão: {', '.join(DEFAULT_CATEGORIES)}")
        use_custom = input("Deseja criar categorias personalizadas? (s/N): ").strip().lower()
        
        categories = DEFAULT_CATEGORIES
        if use_custom == "s":
            custom_cats = input("Digite as categorias separadas por vírgula: ").strip()
            if custom_cats:
                categories = [c.strip() for c in custom_cats.split(",") if c.strip()]
        
        rounds_input = input("Número de Rodadas (Padrão 5): ").strip()
        num_rounds = 5
        if rounds_input.isdigit():
            num_rounds = int(rounds_input)

        print("\nCriando sala no servidor...")
        if self.conn.create_room(room_name, categories, num_rounds, nickname):
            print(f"{GREEN}Sala criada com sucesso!{RESET}")
            time.sleep(1)
            self.show_lobby()
        else:
            print(f"{RED}Erro ao criar sala. Verifique se o nome já está em uso.{RESET}")
            time.sleep(2)

    def action_list_rooms(self):
        clear_screen()
        self.show_banner()
        print(f"{BOLD}=== SALAS DISPONÍVEIS ==={RESET}\n")
        
        rooms = self.conn.list_rooms()
        if not rooms:
            print("Nenhuma sala aberta no momento.")
            input("\nPressione Enter para voltar...")
            return

        # Cabeçalho da tabela
        print(f"{BOLD}{'Sala':<20} | {'Host':<15} | {'Jogadores':<10} | {'Rodadas':<8}{RESET}")
        print("-" * 60)
        for r in rooms:
            print(f"{r['name']:<20} | {r['host']:<15} | {r['player_count']:<10} | {r['num_rounds']:<8}")
        print("-" * 60)
        
        join_choice = input("\nDigite o nome da sala para entrar ou pressione Enter para voltar: ").strip()
        if join_choice:
            nickname = input("Digite seu Nickname: ").strip()
            if not nickname:
                print(f"{RED}Nickname inválido!{RESET}")
                time.sleep(1.5)
                return
            
            print("\nEntrando na sala...")
            if self.conn.join_room(join_choice, nickname):
                print(f"{GREEN}Entrou na sala!{RESET}")
                time.sleep(1)
                self.show_lobby()
            else:
                print(f"{RED}Não foi possível entrar na sala. Nome do jogador ou da sala inválidos.{RESET}")
                time.sleep(2)

    def action_join_room(self):
        clear_screen()
        self.show_banner()
        print(f"{BOLD}=== ENTRAR EM SALA ==={RESET}\n")
        
        room_name = input("Nome da Sala: ").strip()
        if not room_name:
            print(f"{RED}Nome da sala não pode ser vazio!{RESET}")
            time.sleep(1.5)
            return

        nickname = input("Digite seu Nickname: ").strip()
        if not nickname:
            print(f"{RED}Nickname não pode ser vazio!{RESET}")
            time.sleep(1.5)
            return

        print("\nConectando à sala...")
        if self.conn.join_room(room_name, nickname):
            print(f"{GREEN}Conectado com sucesso!{RESET}")
            time.sleep(1)
            self.show_lobby()
        else:
            print(f"{RED}Erro ao entrar na sala. Pode estar cheia, com partida em andamento ou inexistente.{RESET}")
            time.sleep(2)

    def show_lobby(self):
        last_players = []
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while True:
                with self.state.lock:
                    current_players = list(self.state.players)
                    is_host = self.state.is_host
                    room_name = self.state.room_name
                    game_started = self.state.game_started_event.is_set()
                    cancelled = self.state.cancelled_event.is_set()
                
                if game_started:
                    break
                if cancelled:
                    print(f"\n{RED}Partida cancelada: {self.state.cancelled_reason}{RESET}")
                    time.sleep(2)
                    return
                
                # Só limpa e redesenha a tela se houver mudança na lista de jogadores
                if current_players != last_players:
                    clear_screen()
                    self.show_banner()
                    print(f"{BOLD}Sala:{RESET} {room_name} | {BOLD}Status:{RESET} Aguardando Jogadores")
                    print("-" * 55)
                    print(f"{BOLD}Jogadores conectados ({len(current_players)}):{RESET}")
                    for p in current_players:
                        role = f"{MAGENTA}(Host){RESET}" if p == current_players[0] else ""
                        print(f"  • {p} {role}")
                    print("-" * 55)
                    if is_host:
                        print(f"{GREEN}Pressione 'I' para Iniciar a Partida{RESET} (mínimo {MIN_PLAYERS} jogadores)")
                        print("Pressione 'S' para Sair e fechar a sala.")
                    else:
                        print("Aguardando o host iniciar a partida...")
                        print("Pressione 'S' para Sair da sala.")
                    last_players = current_players
                
                # Aguarda tecla sem bloquear por muito tempo
                rlist, _, _ = select.select([sys.stdin], [], [], 0.5)
                if rlist:
                    char = sys.stdin.read(1).lower()
                    if char == 'i' and is_host:
                        if len(current_players) >= MIN_PLAYERS:
                            self.conn.start_game()
                        else:
                            # Notifica erro localmente sem travar
                            sys.stdout.write(f"\r{RED}Erro: Mínimo de {MIN_PLAYERS} jogadores.{RESET}")
                            sys.stdout.flush()
                            time.sleep(1.5)
                            last_players = [] # força redesenhar
                    elif char == 's':
                        self.conn.leave_room()
                        return
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
        # Iniciando fluxo principal do jogo
        self.run_game_loop()

    def run_game_loop(self):
        while True:
            # 1. Aguarda início da rodada pelo servidor
            self.state.round_started_event.wait()
            
            with self.state.lock:
                if self.state.cancelled_event.is_set():
                    break
                letter = self.state.current_letter
                round_num = self.state.round_number
                total_rounds = self.state.total_rounds
                time_limit = self.state.time_limit
                categories = list(self.state.players) # não, as categorias da sala
                # Na verdade as categorias estão salvas na sala, mas precisamos passá-las ou tê-las no estado local
                
            # Recupera categorias do setup original
            with self.state.lock:
                categories = list(self.state.all_answers.get(self.state.nickname, {}).keys())
                # Se ainda não estiver preenchido o dict local de respostas vazias, criamos
                if not categories:
                    # Buscamos as categorias do estado, mas espere, a conexão ou o RPyC salvou no state?
                    # Vamos garantir que salvamos 'categories' no ClientState ao criar/entrar.
                    # Sim, vamos olhar para 'self.state.all_answers' ou adicionar no ClientState.
                    # Vamos adicionar categories no ClientState para segurança.
                    categories = self.state.categories
            
            self.state.round_started_event.clear()
            
            clear_screen()
            print(f"{CYAN}{BOLD}" + "=" * 55)
            print(f"               RODADA {round_num} DE {total_rounds}             ")
            print("=" * 55 + f"{RESET}")
            print(f"Letra Sorteada: {YELLOW}{BOLD}{letter}{RESET}")
            print(f"Categorias: {', '.join(categories)}")
            print("-" * 55)
            
            # 2. Fase de preenchimento das respostas
            answers = self.run_filling_phase(categories, letter, time_limit)
            
            # Envia as respostas ao servidor
            self.conn.submit_answers(answers)
            
            # 3. Aguarda fase de votação iniciar
            clear_screen()
            print("Aguardando finalização do preenchimento de todos os jogadores...")
            
            # Aguarda evento de votação
            self.state.voting_started_event.wait()
            self.state.voting_started_event.clear()
            
            # 4. Fase de Votação
            votes = self.run_voting_phase(categories)
            
            # Envia os votos ao servidor
            self.conn.submit_votes(votes)
            
            clear_screen()
            print("Aguardando finalização da votação de todos os jogadores...")
            
            # 5. Aguarda resultados da rodada
            self.state.results_received_event.wait()
            self.state.results_received_event.clear()
            
            # Exibe o placar da rodada
            self.show_round_results()
            
            # Espera 10 segundos visualmente para iniciar a próxima rodada
            for i in range(10, 0, -1):
                if self.state.game_over_event.is_set() or self.state.cancelled_event.is_set():
                    break
                sys.stdout.write(f"\rPróxima rodada inicia em {i}s... ")
                sys.stdout.flush()
                time.sleep(1)
            print()
            
            # Checa se o jogo acabou
            if self.state.game_over_event.is_set():
                self.state.game_over_event.clear()
                self.show_game_over()
                break
                
            if self.state.cancelled_event.is_set():
                print(f"\n{RED}Partida interrompida: {self.state.cancelled_reason}{RESET}")
                input("\nPressione Enter para voltar ao menu...")
                self.state.cancelled_event.clear()
                break

    def run_filling_phase(self, categories: List[str], letter: str, time_limit: int) -> Dict[str, str]:
        answers = {cat: "" for cat in categories}
        cat_idx = 0
        num_cats = len(categories)
        timeout_at = time.time() + time_limit
        
        while not self.state.stop_event.is_set() and time.time() < timeout_at:
            # Imprime resumo do preenchimento atual
            clear_screen()
            self.show_banner()
            print(f"Letra Sorteada: {YELLOW}{BOLD}{letter}{RESET} | Digite {BOLD}/stop{RESET} para parar (todas preenchidas)")
            print("-" * 55)
            for cat in categories:
                print(f" • {BOLD}{cat:<12}:{RESET} {answers[cat]}")
            print("-" * 55)
            
            if cat_idx < num_cats:
                cat = categories[cat_idx]
                prompt = f"Preencha [{cat}]: "
                ans = input_with_timer_and_stop_event(prompt, self.state.stop_event, timeout_at)
                
                if ans is None:
                    # Timeout ou stop externo acionado
                    break
                
                if ans.lower() == "/stop":
                    all_filled = all(v != "" for v in answers.values())
                    if all_filled:
                        self.conn.request_stop(answers)
                    else:
                        print(f"\n{RED}Preencha todas as categorias antes de acionar o STOP!{RESET}")
                        time.sleep(1.5)
                else:
                    # Valida se a palavra começa com a letra
                    # Fazemos validação local amigável (apenas avisa, mas deixa gravar para evitar frustração)
                    if ans and not ans.lower().strip().startswith(letter.lower()):
                        print(f"\n{YELLOW}Aviso: A palavra não começa com '{letter}'!{RESET}")
                        time.sleep(1.0)
                    answers[cat] = ans
                    cat_idx += 1
            else:
                # Revisão final
                print("\nTodas as categorias preenchidas!")
                print("Opções:")
                print(" - Digite o número (1 a N) da categoria para alterar")
                print(" - Digite '/stop' para acionar o STOP")
                print(" - Pressione Enter para aguardar o fim do tempo")
                
                prompt = "Escolha: "
                choice = input_with_timer_and_stop_event(prompt, self.state.stop_event, timeout_at)
                
                if choice is None:
                    break
                
                if choice.lower() == "/stop":
                    all_filled = all(v != "" for v in answers.values())
                    if all_filled:
                        self.conn.request_stop(answers)
                    else:
                        print(f"\n{RED}Preencha todas as categorias antes de dar STOP!{RESET}")
                        time.sleep(1.5)
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < num_cats:
                        cat_idx = idx
                elif choice == "":
                    # Fica aguardando fim do tempo
                    print("Aguardando fim do tempo...")
                    while not self.state.stop_event.is_set() and time.time() < timeout_at:
                        time.sleep(0.2)
                    break
                    
        # Se foi interrompido por STOP ou timeout, mostra aviso
        if self.state.stop_event.is_set():
            who = self.state.who_stopped
            print(f"\n{RED}{BOLD}STOP! Rodada encerrada por: {who}{RESET}")
            time.sleep(2)
            
        return answers

    def run_voting_phase(self, categories: List[str]) -> Dict[str, Dict[str, bool]]:
        votes = {cat: {} for cat in categories}
        
        with self.state.lock:
            all_answers = dict(self.state.all_answers)
            players = list(self.state.players)
            nickname = self.state.nickname
            time_limit = self.state.time_limit
            
        timeout_at = time.time() + time_limit
        interrupted = False
        
        for cat in categories:
            if interrupted:
                break
            
            clear_screen()
            self.show_banner()
            print(f"{BOLD}=== FASE DE VOTAÇÃO: {cat.upper()} ==={RESET}")
            print(f"Avalie as palavras dos oponentes. Pressione Enter para VÁLIDO.")
            print("-" * 55)
            
            for player in players:
                if player == nickname:
                    continue
                
                word = all_answers.get(player, {}).get(cat, "").strip()
                if not word:
                    # Palavra em branco é automaticamente inválida
                    votes[cat][player] = False
                    print(f" • {player}: {RED}[Em branco - Inválida]{RESET}")
                    continue
                
                prompt = f"Jogador '{player}' escreveu '{word}'. É válida? [V/i]: "
                vote_str = input_with_timer_and_stop_event(prompt, self.state.stop_event, timeout_at)
                
                if vote_str is None or time.time() >= timeout_at:
                    interrupted = True
                    break
                
                # Se digitar 'i', é inválido. Caso contrário, válido.
                votes[cat][player] = vote_str.lower() != "i"
                status_color = GREEN if votes[cat][player] else RED
                status_text = "Válido" if votes[cat][player] else "Inválido"
                print(f" -> Voto registrado: {status_color}{status_text}{RESET}")
                
        return votes

    def show_round_results(self):
        clear_screen()
        self.show_banner()
        
        with self.state.lock:
            res = dict(self.state.round_results)
            
        if not res:
            print("Erro ao carregar resultados.")
            return
            
        round_num = res["round_number"]
        total_rounds = res["total_rounds"]
        letter = res["letter"]
        player_scores = res["player_scores"]
        accumulated_scores = res["accumulated_scores"]
        ranking = res["ranking"]
        details = res["details"]
        
        print(f"{BOLD}=== RESULTADO DA RODADA {round_num} DE {total_rounds} (Letra '{letter}') ==={RESET}\n")
        
        # Detalhamento de respostas por jogador
        for player, cats_data in details.items():
            print(f"{BOLD}{player}{RESET}:")
            for cat, data in cats_data.items():
                word = data["word"]
                pts = data["points"]
                valid = data["valid"]
                unique = data["unique"]
                
                if not word:
                    status = f"{RED}Em branco{RESET}"
                elif not valid:
                    status = f"{RED}Inválida (Voto/Letra){RESET}"
                elif unique:
                    status = f"{GREEN}Válida e Única (+10 pts){RESET}"
                else:
                    status = f"{YELLOW}Válida mas Repetida (+5 pts){RESET}"
                
                print(f"  • {cat:<12}: '{word}' -> {status}")
            print(f"  Total da rodada: {BOLD}{player_scores[player]} pts{RESET}")
            print("-" * 55)
            
        # Scoreboard
        print(f"\n{BOLD}=== SCOREBOARD ACUMULADO ==={RESET}")
        print(f"{BOLD}{'Posição':<8} | {'Jogador':<20} | {'Rodada':<10} | {'Acumulado':<10}{RESET}")
        print("-" * 55)
        for idx, (p, total) in enumerate(ranking):
            pos = idx + 1
            pts_round = player_scores.get(p, 0)
            print(f"{pos:<8} | {p:<20} | {pts_round:<10} | {total:<10}")
        print("-" * 55)

    def show_game_over(self):
        clear_screen()
        self.show_banner()
        print(f"{GREEN}{BOLD}=" * 55)
        print("                PARTIDA CONCLUÍDA!             ")
        print("=" * 55 + f"{RESET}\n")
        
        with self.state.lock:
            ranking = list(self.state.final_ranking)
            
        if ranking:
            winner = ranking[0][0]
            print(f"🏆 {BOLD}O VENCEDOR É: {YELLOW}{winner}{RESET} com {BOLD}{ranking[0][1]} pontos!{RESET}\n")
            print(f"{BOLD}=== RANKING FINAL ==={RESET}")
            print(f"{BOLD}{'Pos':<5} | {'Jogador':<25} | {'Pontos':<10}{RESET}")
            print("-" * 45)
            for idx, (p, score) in enumerate(ranking):
                pos = idx + 1
                medal = "🥇 " if pos == 1 else "🥈 " if pos == 2 else "🥉 " if pos == 3 else "   "
                print(f"{medal}{pos:<2} | {p:<25} | {score:<10}")
            print("-" * 45)
        else:
            print("Não houve ranking final disponível.")
            
        input("\nPressione Enter para voltar ao menu principal...")
        self.conn.disconnect()
