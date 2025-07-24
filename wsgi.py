#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WSGI файл для запуска Telegram бота через ISPmanager
Замените 'ваш_домен' на ваш реальный домен
"""

import sys
import os
from datetime import datetime

# Добавляем путь к проекту
PROJECT_PATH = '/var/www/ваш_домен/data/www/ваш_домен'
sys.path.insert(0, PROJECT_PATH)

# Устанавливаем рабочую директорию
os.chdir(PROJECT_PATH)

# Загружаем переменные окружения
from dotenv import load_dotenv
load_dotenv()

# Импортируем приложение бота
try:
    from bot import application
    print("✅ Telegram бот успешно импортирован")
except ImportError as e:
    print(f"❌ Ошибка импорта бота: {e}")
    # Создаем заглушку для WSGI
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def index():
        return "Telegram Bot - Ошибка импорта"
    
    @app.route('/health')
    def health():
        return "Bot Status: Error"
else:
    # Создаем WSGI приложение
    app = application

# Функция для проверки здоровья приложения
@app.route('/health')
def health_check():
    """Проверка здоровья приложения."""
    try:
        # Проверяем, что бот работает
        return {
            "status": "healthy",
            "bot": "running",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# Главная страница
@app.route('/')
def index():
    """Главная страница."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Telegram Language Learning Bot</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 600px; margin: 0 auto; }
            .status { padding: 10px; border-radius: 5px; margin: 10px 0; }
            .success { background-color: #d4edda; color: #155724; }
            .info { background-color: #d1ecf1; color: #0c5460; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Telegram Language Learning Bot</h1>
            <div class="status success">
                ✅ Бот работает и готов к использованию
            </div>
            <div class="status info">
                📱 Найдите бота в Telegram и начните изучение языков!
            </div>
            <p>
                <strong>Возможности:</strong><br>
                • Сохранение слов с хештегами<br>
                • Создание и управление категориями<br>
                • Экспорт списков в PDF<br>
                • Многоязычная поддержка<br>
                • Система регистрации пользователей
            </p>
            <p>
                <strong>Статус:</strong> 
                <a href="/health">Проверить здоровье приложения</a>
            </p>
        </div>
    </body>
    </html>
    """

if __name__ == '__main__':
    print("🚀 Запуск WSGI сервера...")
    app.run(host='0.0.0.0', port=8000, debug=False) 