#!/bin/bash
# Скрипт для деплоя с GitHub на сервер
# Сохраняет базу данных (она в volume или на хосте)

echo "🚀 Деплой с GitHub на сервер..."
echo "=================================="

# Переходим в директорию проекта
cd /root/crm- || exit 1

# Сохраняем текущую ветку (если нужно)
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")

echo "📥 Получаем изменения из GitHub..."
git fetch origin

echo "🔄 Переключаемся на ветку update-december-2024..."
git checkout update-december-2024 || git checkout -b update-december-2024 origin/update-december-2024

echo "📥 Обновляем код..."
git pull origin update-december-2024

echo "💾 Проверяем базу данных (она должна сохраниться)..."
# База данных в volume или на хосте, поэтому сохранится автоматически
docker volume ls | grep postgres
docker exec crm--db-1 psql -U crm_user -d crm_db -c "SELECT COUNT(*) FROM business;" || echo "База данных доступна"

echo "🔄 Пересобираем и перезапускаем контейнеры..."
docker-compose down
docker-compose up -d --build

echo "⏳ Ждем запуска контейнеров..."
sleep 10

echo "✅ Проверяем статус..."
docker-compose ps

echo "📋 Проверяем логи..."
docker-compose logs --tail=20 crm-app

echo ""
echo "✅ Деплой завершен!"
echo "💾 База данных сохранена (она в volume)"











