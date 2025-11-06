#!/bin/bash

# 🔄 Скрипт обновления CRM
# Автор: CRM Team
# Дата: $(date)

set -e

echo "🔄 Начинаем обновление CRM..."

# 1. Создаем резервную копию перед обновлением
echo "💾 Создаем резервную копию..."
./backup.sh

# 2. Останавливаем сервисы
echo "🛑 Останавливаем сервисы..."
docker-compose down

# 3. Обновляем код из Git (если используется)
if [ -d ".git" ]; then
    echo "📥 Обновляем код из Git..."
    git pull origin main
fi

# 4. Обновляем Docker образы
echo "🐳 Обновляем Docker образы..."
docker-compose pull

# 5. Пересобираем и запускаем сервисы
echo "🔨 Пересобираем и запускаем сервисы..."
docker-compose up -d --build

# 6. Ждем запуска сервисов
echo "⏳ Ждем запуска сервисов..."
sleep 15

# 7. Проверяем статус
echo "📊 Проверяем статус сервисов..."
docker-compose ps

# 8. Проверяем логи
echo "📋 Проверяем логи..."
docker-compose logs --tail=20 crm-app

# 9. Проверяем доступность приложения
echo "🌐 Проверяем доступность приложения..."
if curl -f http://localhost:8000/ > /dev/null 2>&1; then
    echo "✅ Приложение доступно!"
else
    echo "❌ Приложение недоступно! Проверьте логи."
    docker-compose logs crm-app
    exit 1
fi

echo ""
echo "🎉 Обновление завершено успешно!"
echo "📱 Приложение доступно по адресу: http://your-domain.com"
echo ""
echo "📋 Полезные команды:"
echo "   docker-compose logs -f          # Просмотр логов"
echo "   docker-compose restart          # Перезапуск"
echo "   docker-compose down             # Остановка"
echo ""
