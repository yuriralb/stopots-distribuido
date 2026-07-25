# shared/constants.py

FILL_TIME_PER_CATEGORY = 20  # segundos
VOTE_TIME_PER_CATEGORY = 15  # segundos
POINTS_UNIQUE = 10
POINTS_REPEATED = 5
POINTS_INVALID = 0
MIN_PLAYERS = 2
DEFAULT_CATEGORIES = ["Nome", "Animal", "Fruta", "Cidade", "Objeto", "Cor"]
# Exclui K, W e Y
ALPHABET = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in ("K", "W", "Y")]
SERVER_PORT = 18861
GRACE_PERIOD = 5  # tempo bônus depois de um pedido de STOP!
