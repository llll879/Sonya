"""Сервер Сони для Render: /chat (Gemini), /tts (Fish Audio), сайт на /."""
import hmac
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response

APP_TOKEN = os.getenv("APP_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
FISH_API_KEY = os.getenv("FISH_API_KEY", "")
FISH_VOICE_ID = os.getenv("FISH_VOICE_ID", "")
FISH_MODEL = os.getenv("FISH_MODEL", "s2.1-pro")

STATIC = Path(__file__).parent / "static"
app = FastAPI()

# Функции управления телефоном (нужны только нативному приложению, шаг 4.2).
TOOLS = [{
    "functionDeclarations": [
        {
            "name": "open_app",
            "description": "Открыть приложение на телефоне пользователя по названию (например: YouTube, Telegram, WhatsApp, Настройки, Камера).",
            "parameters": {"type": "OBJECT", "properties": {"name": {"type": "STRING", "description": "Название приложения"}}, "required": ["name"]},
        },
        {
            "name": "read_screen",
            "description": "Прочитать, что сейчас на экране телефона: список элементов с номерами [N], их тип (кнопка, текст, поле ввода, переключатель) и надпись. Вызывай перед нажатием по номеру и после действий, чтобы проверить результат.",
            "parameters": {"type": "OBJECT", "properties": {}},
        },
        {
            "name": "tap",
            "description": "Нажать на элемент экрана: либо по надписи (text), либо по номеру из последнего read_screen (index). Номер действителен только для последнего прочитанного экрана.",
            "parameters": {"type": "OBJECT", "properties": {"text": {"type": "STRING", "description": "Надпись на элементе"}, "index": {"type": "INTEGER", "description": "Номер элемента из read_screen"}}},
        },
        {
            "name": "press_button",
            "description": "Нажать системную кнопку телефона.",
            "parameters": {"type": "OBJECT", "properties": {"button": {"type": "STRING", "description": "back, home, recents, notifications или quick_settings"}}, "required": ["button"]},
        },
    ]
}]


def system_prompt(name: str, with_tools: bool) -> str:
    s = (
        f"Тебя зовут {name}. Ты дружелюбный голосовой ассистент. Отвечай по-русски, "
        "коротко и естественно, без markdown и списков — твой ответ будут озвучивать."
    )
    if with_tools:
        s += (
            " Ты можешь управлять телефоном пользователя через функции. Действуй по шагам: "
            "открыл приложение → read_screen → нажал → read_screen, чтобы убедиться. "
            "Не выдумывай, что видно на экране — только то, что вернул read_screen. "
            "Если действие не удалось, скажи об этом честно. Когда закончишь, коротко ответь текстом."
        )
    return s


def check_token(request: Request) -> None:
    got = request.headers.get("x-app-token", "").encode()
    if not APP_TOKEN or not hmac.compare_digest(got, APP_TOKEN.encode()):
        raise HTTPException(401, "Неверный токен")


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.post("/chat")
async def chat(request: Request):
    check_token(request)
    if not GEMINI_API_KEY:
        raise HTTPException(500, "На сервере не задан GEMINI_API_KEY")
    data = await request.json()
    contents = data.get("contents") or []
    name = data.get("assistantName") or "Соня"
    with_tools = data.get("tools", True)  # сайт шлёт tools=false

    body = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system_prompt(name, with_tools)}]},
    }
    if with_tools:
        body["tools"] = TOOLS

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    async with httpx.AsyncClient(timeout=80) as client:
        r = await client.post(url, json=body, headers={"x-goog-api-key": GEMINI_API_KEY})
    if r.status_code != 200:
        raise HTTPException(502, f"Gemini {r.status_code}: {r.text[:300]}")

    j = r.json()
    cands = j.get("candidates") or []
    if not cands:
        raise HTTPException(502, f"Gemini не вернул ответ: {str(j.get('promptFeedback', ''))[:200]}")

    # content отдаём как есть (с functionCall и thoughtSignature) — приложение вернёт его обратно
    content = cands[0].get("content") or {}
    content.setdefault("role", "model")
    parts = content.get("parts") or []
    if not parts:
        parts = content["parts"] = [{"text": "Не получилось ответить, попробуй ещё раз."}]

    text = "".join(p.get("text", "") for p in parts if "text" in p and not p.get("thought"))
    calls = []
    for p in parts:
        fc = p.get("functionCall")
        if fc:
            item = {"name": fc.get("name"), "args": fc.get("args") or {}}
            if fc.get("id"):
                item["id"] = fc["id"]
            calls.append(item)
    return {"content": content, "text": text, "functionCalls": calls}


@app.post("/tts")
async def tts(request: Request):
    check_token(request)
    if not FISH_API_KEY:
        raise HTTPException(501, "Озвучка на сервере не настроена (нет FISH_API_KEY)")
    data = await request.json()
    text = (data.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "Пустой текст")
    body = {"text": text, "format": "mp3"}
    if FISH_VOICE_ID:
        body["reference_id"] = FISH_VOICE_ID
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.fish.audio/v1/tts",
            json=body,
            headers={"Authorization": f"Bearer {FISH_API_KEY}", "model": FISH_MODEL},
        )
    if r.status_code != 200:
        raise HTTPException(502, f"Fish Audio {r.status_code}: {r.text[:200]}")
    return Response(content=r.content, media_type="audio/mpeg")
