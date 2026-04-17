import datetime
import re

def log(message):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}")

def clean_deepseek_think(text):
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

def normalize_word(word):
    word = word.lower().strip()
    if len(word) > 5: return word[:-2]
    elif len(word) > 4: return word[:-1]
    return word

def text_to_tokens(text):
    clean = re.sub(r'[^а-яa-z0-9\s]', '', text.lower())
    return [normalize_word(w) for w in clean.split()]