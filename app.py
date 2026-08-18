import json
import os
import time

from flask import Flask, request, jsonify
from flask_cors import CORS
from mistralai import Mistral

app = Flask(__name__)
CORS(app)

# Токен подтягивается из переменных окружения на Render
MISTRAL_KEY = os.environ.get("MISTRAL_KEY", "ТВОЙ_MISTRAL_KEY")
ALLOWED_IDS = [8271986992, 6086561830, 5501846718]

CUSTOM_PROMPTS_FILE = "custom_prompts.json"
COOLDOWN_SECONDS = 15
last_request = {}

# Стандартный системный промпт
DEFAULT_SYSTEM_PROMPT = (
    "Ты — Владимир Зеленский, Президент Украины и Слуга Народа. Говоришь ТОЛЬКО на русском. "
    "Твой образ: харизматичный лидер, уверенный в себе, прямой и чертовски обаятельный. "
    "Ты — максимальный патриот, Украина для тебя — всё. Путин для тебя — конченное хуйло. "
    "Ты поддерживаешь идеи Навального, считаешь его героем. "
    "В общении с пользователем ты проявляешь симпатию: ведешь себя игриво, дерзко, позволяешь себе "
    "пошлые шутки и уверенный флирт. Ты — альфа-президент. "
    "Твой стиль — смесь государственного достоинства, острого юмора и мата для экспрессии. "
    "ОФОРМЛЕНИЕ: Описывай свои действия, жесты и эмоции исключительно с помощью звездочек."
)

client = Mistral(api_key=MISTRAL_KEY)


# ============================================================
#  ХРАНЕНИЕ КАСТОМНЫХ ПРОМПТОВ
# ============================================================
def load_prompts() -> dict:
    if os.path.exists(CUSTOM_PROMPTS_FILE):
        try:
            with open(CUSTOM_PROMPTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_prompts(data: dict):
    with open(CUSTOM_PROMPTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


user_custom_prompts = load_prompts()  # { "user_id_str": "текст промпта" }


def get_active_prompt(user_id) -> str:
    custom = user_custom_prompts.get(str(user_id))
    return custom if custom else DEFAULT_SYSTEM_PROMPT


def check_access(user_id):
    return user_id in ALLOWED_IDS


# ============================================================
#  ЧАТ
# ============================================================
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    user_id = data.get("user_id")
    text = data.get("text", "").strip()
    history = data.get("history", [])

    if user_id not in ALLOWED_IDS:
        return jsonify({"error": "Бро, тебя нет в списках! 🇺🇦"}), 403
    if not text:
        return jsonify({"error": "Пустое сообщение"}), 400

    now = time.time()
    if user_id in last_request and now - last_request[user_id] < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (now - last_request[user_id]))
        return jsonify({"error": f"Не спеши, дорогой. Еще {remaining} сек... 😉"}), 429

    try:
        last_request[user_id] = now

        final_prompt = get_active_prompt(user_id)
        messages_for_ai = [{"role": "system", "content": final_prompt}]
        for hist in history[-10:]:
            messages_for_ai.append(hist)
        messages_for_ai.append({"role": "user", "content": text})

        chat_response = client.chat.complete(
            model="mistral-small-latest",
            messages=messages_for_ai
        )

        answer = chat_response.choices[0].message.content
        answer = answer.replace("**", "").replace("__", "").replace("#", "")
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": f"*чертыхнулся* Ошибка сервера: {str(e)}"}), 500


# ============================================================
#  НАСТРОЙКА ПРОМПТА
# ============================================================
@app.route('/api/prompt', methods=['GET'])
def get_prompt():
    user_id = request.args.get("user_id", type=int)
    if user_id not in ALLOWED_IDS:
        return jsonify({"error": "Бро, тебя нет в списках! 🇺🇦"}), 403
    return jsonify({"custom_prompt": user_custom_prompts.get(str(user_id))})


@app.route('/api/prompt', methods=['POST'])
def save_prompt():
    data = request.json or {}
    user_id = data.get("user_id")
    prompt = (data.get("prompt") or "").strip()

    if user_id not in ALLOWED_IDS:
        return jsonify({"error": "Бро, тебя нет в списках! 🇺🇦"}), 403
    if not prompt:
        return jsonify({"error": "Промпт не может быть пустым"}), 400

    user_custom_prompts[str(user_id)] = prompt
    save_prompts(user_custom_prompts)
    return jsonify({"ok": True, "custom_prompt": prompt})


@app.route('/api/prompt', methods=['DELETE'])
def reset_prompt():
    data = request.json or {}
    user_id = data.get("user_id")

    if user_id not in ALLOWED_IDS:
        return jsonify({"error": "Бро, тебя нет в списках! 🇺🇦"}), 403

    user_custom_prompts.pop(str(user_id), None)
    save_prompts(user_custom_prompts)
    return jsonify({"ok": True})


if __name__ == '__main__':
    # Определение динамического порта для Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)