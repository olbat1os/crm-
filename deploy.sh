#!/bin/bash

# 🚀 Скрипт развертывания CRM на VPS Hostinger
# Автор: CRM Team
# Дата: $(date)

set -e  # Остановка при ошибке

echo "🚀 Начинаем развертывание CRM на Hostinger VPS..."

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Устанавливаем..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    sudo usermod -aG docker $USER
    echo "✅ Docker установлен. Перезайдите в систему для применения изменений."
    exit 1
fi

# Проверяем наличие Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен. Устанавливаем..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose установлен."
fi

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден. Создаем из примера..."
    cp env.example .env
    echo "⚠️  ВАЖНО: Отредактируйте файл .env перед продолжением!"
    echo "   - Измените SECRET_KEY на случайную строку"
    echo "   - Измените APP_PASSWORD на безопасный пароль"
    echo "   - Настройте DATABASE_URL для PostgreSQL"
    exit 1
fi

# Останавливаем существующие контейнеры
echo "🛑 Останавливаем существующие контейнеры..."
docker-compose down

# Собираем и запускаем контейнеры
echo "🔨 Собираем и запускаем контейнеры..."
docker-compose up -d --build

# Ждем запуска базы данных
echo "⏳ Ждем запуска базы данных..."
sleep 10

# Проверяем статус сервисов
echo "📊 Проверяем статус сервисов..."
docker-compose ps

# Проверяем логи
echo "📋 Последние логи приложения:"
docker-compose logs --tail=20 crm-app

echo ""
echo "🎉 Развертывание завершено!"
echo ""
echo "📱 Ваше приложение доступно по адресу:"
echo "   http://your-server-ip"
echo ""
echo "🔐 Данные для входа:"
echo "   Логин: admin"
echo "   Пароль: (из файла .env)"
echo ""
echo "📋 Полезные команды:"
echo "   docker-compose logs -f          # Просмотр логов"
echo "   docker-compose restart          # Перезапуск"
echo "   docker-compose down             # Остановка"
echo "   docker-compose up -d --build    # Обновление"
echo ""
echo "🔒 Не забудьте настроить файрвол:"
echo "   sudo ufw allow 22    # SSH"
echo "   sudo ufw allow 80    # HTTP"
echo "   sudo ufw allow 443   # HTTPS"
echo "   sudo ufw enable"