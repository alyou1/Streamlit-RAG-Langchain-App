import os
import sys
import json

#chemin absolu
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = os.path.dirname(BASE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Exemple : construire un chemin vers un fichier de config
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'config','config.json')
DATA_PATH = os.path.join(PROJECT_ROOT, 'data')


with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)