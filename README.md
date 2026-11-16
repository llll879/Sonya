# Сервер Сони (Render) + сайт

Один сервис на Render отдаёт и API, и сайт:
- `/` — сайт (чат с голосом)
- `/chat` — Gemini (совместим с приложением Android)
- `/tts` — озвучка Fish Audio (если задан ключ)
- `/health` — для будилки

## Переменные окружения на Render
| Имя | Что |
|---|---|
| APP_TOKEN | твой пароль (впишешь его на сайте/в приложении) |
| GEMINI_API_KEY | ключ Google AI Studio |
| GEMINI_MODEL | необязательно, по умолчанию gemini-2.5-flash |
| FISH_API_KEY, FISH_VOICE_ID | необязательно; без них голос браузера |

## Деплой
1. Залей папку в GitHub-репозиторий.
2. Render → New → Web Service → репозиторий.
   Build: `pip install -r requirements.txt`
   Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Добавь переменные, Deploy. Сайт откроется по адресу `https://<имя>.onrender.com`.
