# shared/constants.py

FILL_TIME_PER_CATEGORY = 20  # seconds
VOTE_TIME_PER_CATEGORY = 15  # seconds
POINTS_UNIQUE = 10
POINTS_REPEATED = 5
POINTS_INVALID = 0
MIN_PLAYERS = 2
DEFAULT_CATEGORIES = ["Nome", "Animal", "Fruta", "Cidade", "Objeto", "Cor"]
# Exclude K, W, Y for Portuguese
ALPHABET = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in ("K", "W", "Y")]
SERVER_PORT = 18861
GRACE_PERIOD = 5  # extra seconds given after STOP to submit answers
