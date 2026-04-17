import os
from dotenv import load_dotenv

#автоматически определяет путь к папке src
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_MODEL = "deepseek-r1:8b"

BRAIN_FILE = os.path.join(BASE_DIR, "school_brain_hybrid.pkl")
SYNONYMS_FILE = os.path.join(BASE_DIR, "synonyms.json")
USERS_FILE = os.path.join(BASE_DIR, "users.json")

LIMITS = {
    "student": 5,
    "teacher": 999999
}