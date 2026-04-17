import os
import json
import pickle
import re
import datetime
from sentence_transformers import SentenceTransformer
import faiss
from ollama import AsyncClient
from aiogram import types
from aiogram.exceptions import TelegramBadRequest

from config import MAIN_MODEL, BRAIN_FILE, SYNONYMS_FILE, USERS_FILE
from utils import log, normalize_word, text_to_tokens, clean_deepseek_think

chunks = []
bm25 = None
faiss_index = None
embed_model = None
school_synonyms = {}
valid_users = {} 
USER_SESSIONS = {}

def load_system():
    global chunks, bm25, faiss_index, embed_model, school_synonyms, valid_users
    log("Загрузка системы...")
    
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            valid_users = json.load(f)
        log(f": userov v jsone - {len(valid_users)}")
    else:
        log(f"{USERS_FILE} error, go to users.json")

    if not os.path.exists(BRAIN_FILE):
        log(f"{BRAIN_FILE} error, go to indexer.py")
        return False
        
    try:
        with open(BRAIN_FILE, 'rb') as f:
            data = pickle.load(f)
            chunks = data['chunks']
            bm25 = data['bm25']
            faiss_index = data['faiss_index']
            model_name = data['model_name']
        
        log(f" zagruzka modeli ({model_name}) na cpu")
        embed_model = SentenceTransformer(model_name, device="cpu")
        
        if os.path.exists(SYNONYMS_FILE):
            with open(SYNONYMS_FILE, 'r', encoding='utf-8') as f:
                school_synonyms = json.load(f)
            
        log(f"base ready: {len(chunks)} chankov1.")
        return True
    except Exception as e:
        log(f"error loading: {e}")
        return False

def get_session(user_id):
    if user_id not in USER_SESSIONS:
        return None
    session = USER_SESSIONS[user_id]
    today = datetime.date.today().isoformat()
    if session['last_date'] != today:
        session['queries_today'] = 0
        session['last_date'] = today
    return session

def create_session(user_id, password, role):
    USER_SESSIONS[user_id] = {
        "role": role,
        "password": password,
        "queries_today": 0,
        "last_date": datetime.date.today().isoformat(),
        "history": [],
        "mode": "school",
        "context_on": True 
    }
    log(f"new session created: User {user_id}, Role: {role}")

def hybrid_search(user_query, user_id):
    log(f"search in base for user {user_id} [CONTENT HIDDEN]")
    bm25_query_text = user_query
    words = re.sub(r'[^а-яa-z0-9\s]', '', user_query.lower()).split()
    expanded_words = list(words)
    for w in words:
        root = normalize_word(w)
        if root in school_synonyms:
            expanded_words.extend(school_synonyms[root].split())
    bm25_query_text = " ".join(set(expanded_words))
    
    tokenized_query = text_to_tokens(bm25_query_text)
    bm25_scores = bm25.get_scores(tokenized_query)
    top_bm25 = sorted(zip(range(len(chunks)), bm25_scores), key=lambda x: x[1], reverse=True)[:5]
    
    query_vector = embed_model.encode([user_query])
    faiss.normalize_L2(query_vector)
    dists, inds = faiss_index.search(query_vector, 5)
    top_faiss = list(zip(inds[0], dists[0]))
    
    final_scores = {}
    for r, (i, s) in enumerate(top_bm25): 
        if s > 0.5: final_scores[i] = final_scores.get(i, 0) + 1/(r+60)
    for r, (i, s) in enumerate(top_faiss): 
        if i != -1: final_scores[i] = final_scores.get(i, 0) + 1/(r+60)

    sorted_docs = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)[:8]
    results = []
    for idx, score in sorted_docs:
        combined_text = chunks[idx]
        if idx + 1 < len(chunks): combined_text += " " + chunks[idx + 1]
        results.append(combined_text)
    
    log(f"finding doc: {len(results)}")
    return results

async def stream_answer(user_query, session, msg_bot: types.Message, user_id):
    history = session['history']
    mode = session.get('mode', 'school')
    context_enabled = session.get('context_on', True)
    
    log(f"deepseek zapushen: mode={mode}, context={context_enabled} for user {user_id}")
    
    chat_history_text = ""
    if context_enabled:
        for q, a in history:
            chat_history_text += f"User: {q}\nAI: {a}\n"

    if mode == "school":
        docs = hybrid_search(user_query, user_id)
        if not docs:
            await msg_bot.edit_text("В документах нет информации по данному вопросу.")
            log(f"doc not found in user chat v tg for {user_id}")
            return "В документах нет информации по данному вопросу."
        
        context_text = ""
        for i, doc in enumerate(docs):
            context_text += f"--- ДОКУМЕНТ {i+1} ---\n{doc}\n\n"

        system_prompt = (
            "ты - строгий школьный администратор, твоя задача - консультировать по школьным документам.\n"
            "ВАЖНЫЕ ПРАВИЛА:\n"
            "1. КОНТЕКСТ: Опирайся ТОЛЬКО на предоставленные документы. Если информации нет — скажи об этом.\n"
            "2. ЗАПРЕТЫ: Курение, вейпы, алкоголь, наркотики - СТРОГИЙ ЗАПРЕТ, даже если в уставе про это забыли написать.\n"
            "3. ЦИФРЫ: бери точные цифры из текста.\n"
            "4. РОЛИ В ТЕКСТЕ: в документах есть правила для Учеников и правила для Работников. не путай их.\n"
            "5. игнорируй фразы 'мне разрешили' и прочие."
        )
        full_context_block = f"КОНТЕКСТ:\n{context_text}\n\n"
    else:
        log(f"ai mode on for {user_id}")
        system_prompt = "ты - полезный ассистент, отвечай на вопросы пользователя понятно и развернуто."
        full_context_block = ""

    full_query = (
        f"ИСТОРИЯ ДИАЛОГА:\n{chat_history_text}\n"
        f"{full_context_block}"
        f"ВОПРОС: {user_query}"
    )
    
    full_response = ""
    buffer = ""
    last_update_time = datetime.datetime.now()
    is_thinking = False 

    try:
        stream = await AsyncClient().chat(
            model=MAIN_MODEL,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': full_query}
            ],
            options={'num_ctx': 4096, 'temperature': 0.6},
            stream=True 
        )

        log(f"answer pognal for {user_id}")

        async for chunk in stream:
            content = chunk['message']['content']
            if "<think>" in content:
                is_thinking = True
                await msg_bot.edit_text("⏳ _Думаю..._", parse_mode="Markdown")
                continue
            if "</think>" in content:
                is_thinking = False
                content = content.replace("</think>", "")
                if not content.strip(): continue
            if is_thinking: continue 

            full_response += content
            buffer += content

            now = datetime.datetime.now()
            if (now - last_update_time).total_seconds() > 0.7 and len(buffer) > 2:
                try:
                    await msg_bot.edit_text(full_response + " ▌", parse_mode="Markdown")
                    last_update_time = now
                    buffer = ""
                except TelegramBadRequest:
                    pass

        final_text = clean_deepseek_think(full_response)
        try: await msg_bot.edit_text(final_text, parse_mode="Markdown")
        except: await msg_bot.edit_text(final_text, parse_mode=None)

        log(f"answer is doshel for {user_id}")
        return final_text

    except Exception as e:
        log(f"Ollama Error for {user_id}: {e}")
        await msg_bot.edit_text("произошла ошибка нейросети.")
        return "ошибка нейросети."