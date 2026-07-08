# server/game_engine.py

import random
import unicodedata
from typing import List, Dict, Set, Tuple, Any
from shared.constants import ALPHABET, POINTS_UNIQUE, POINTS_REPEATED, POINTS_INVALID

def draw_letter(used_letters: Set[str]) -> str:
    """
    Sorteia uma letra do ALPHABET que ainda não foi usada.
    Se todas as letras já tiverem sido usadas, limpa o conjunto e sorteia novamente.
    """
    available = [c for c in ALPHABET if c not in used_letters]
    if not available:
        used_letters.clear()
        available = list(ALPHABET)
    letter = random.choice(available)
    used_letters.add(letter)
    return letter

def normalize_word(word: str) -> str:
    """
    Normaliza a palavra: remove espaços em branco nas bordas, converte para minúsculas
    e remove todos os acentos ortográficos.
    """
    if not word:
        return ""
    word = word.strip().lower()
    # NFKD separa caracteres acentuados em caractere base + acento
    nfkd_form = unicodedata.normalize('NFKD', word)
    # Filtra apenas os caracteres base (excluindo marcas de combinação)
    return "".join(c for c in nfkd_form if not unicodedata.combining(c))

def is_word_valid(word: str, letter: str) -> bool:
    """
    Verifica se a palavra começa com a letra correta (ignorando acentos e case).
    """
    norm_word = normalize_word(word)
    norm_letter = normalize_word(letter)
    if not norm_word or not norm_letter:
        return False
    return norm_word.startswith(norm_letter)

def tally_votes(
    players: List[str],
    categories: List[str],
    votes: Dict[str, Dict[str, Dict[str, bool]]],
    answers: Dict[str, Dict[str, str]]
) -> Dict[str, Dict[str, bool]]:
    """
    Consolida as votações de todos os jogadores.
    Para cada jogador e cada categoria, avalia se a maioria dos OUTROS jogadores votou
    como válida (True) ou inválida (False).
    Retorna um dicionário: player -> category -> is_approved (bool).
    """
    approvals = {p: {cat: True for cat in categories} for p in players}
    if len(players) < 2:
        return approvals

    for category in categories:
        for target_player in players:
            # Jogadores votantes (todos exceto o próprio dono da resposta)
            voters = [p for p in players if p != target_player]

            invalid_votes = 0
            valid_votes = 0

            for voter in voters:
                # Resgate do voto do voter
                voter_votes = votes.get(voter, {})
                cat_votes = voter_votes.get(category, {})
                # Por padrão (caso não enviado/voto nulo), o voto é válido (True)
                vote_is_valid = cat_votes.get(target_player, True)

                if not vote_is_valid:
                    invalid_votes += 1
                else:
                    valid_votes += 1

            # Uma palavra é inválida se a maioria dos jogadores votou CONTRA ela (invalid > valid)
            majority_needed = len(voters) / 2.0
            if invalid_votes > majority_needed:
                approvals[target_player][category] = False

    return approvals

def calculate_scores(
    players: List[str],
    categories: List[str],
    letter: str,
    answers: Dict[str, Dict[str, str]],
    approvals: Dict[str, Dict[str, bool]]
) -> Tuple[Dict[str, int], Dict[str, Dict[str, Dict[str, Any]]]]:
    """
    Calcula as pontuações da rodada.
    Retorna:
      - player_scores: nickname -> pontos da rodada
      - details: nickname -> categoria -> {word, points, valid, unique}
    """
    player_scores = {p: 0 for p in players}
    details = {p: {} for p in players}

    for category in categories:
        # Mapeia palavra normalizada -> lista de jogadores que a usaram
        word_to_players = {}
        player_valid_words = {}
        player_raw_words = {}

        # 1ª Passagem: validação básica (não vazio, letra correta, aprovada por votação)
        for player in players:
            raw_word = answers.get(player, {}).get(category, "").strip()
            is_valid_letter = is_word_valid(raw_word, letter)
            is_approved = approvals.get(player, {}).get(category, True)

            is_valid = bool(raw_word) and is_valid_letter and is_approved
            player_raw_words[player] = raw_word

            if is_valid:
                norm = normalize_word(raw_word)
                player_valid_words[player] = norm
                if norm not in word_to_players:
                    word_to_players[norm] = []
                word_to_players[norm].append(player)
            else:
                details[player][category] = {
                    "word": raw_word,
                    "points": POINTS_INVALID,
                    "valid": False,
                    "unique": False
                }

        # 2ª Passagem: atribuição dos pontos por categoria
        for player in players:
            raw_word = player_raw_words[player]
            if player in player_valid_words:
                norm = player_valid_words[player]
                # Verifica se é única
                if len(word_to_players[norm]) == 1:
                    pts = POINTS_UNIQUE
                    unique = True
                else:
                    pts = POINTS_REPEATED
                    unique = False

                player_scores[player] += pts
                details[player][category] = {
                    "word": raw_word,
                    "points": pts,
                    "valid": True,
                    "unique": unique
                }

    return player_scores, details

def determine_winner(accumulated_scores: Dict[str, int]) -> str:
    """
    Retorna o nickname do jogador com a maior pontuação acumulada.
    """
    if not accumulated_scores:
        return ""
    # Ordena e retorna o melhor
    sorted_players = sorted(accumulated_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_players[0][0]
