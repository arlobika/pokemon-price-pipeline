# config.py
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]
SETS = os.environ.get("SETS", "base1").split(",")