import json
import os

with open(os.environ.get("NILLION_DB_CONFIG_FILEPATH", ".nildb.config.json")) as fh:
    CONFIG = json.load(fh)
