#!/bin/bash

# 🔄 Скрипт резервного копирования CRM
# Автор: CRM Team
# Дата: $(date)

set -e

# Настройки
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/crm/backups"
PROJECT_DIR="/opt/crm"
RETENTION_DAYS=7

# Создаем директорию для резервных копий
mkdir -p $BACKUP_DIR

echo "🔄 Начинаем резервное копирование CRM..."

# 1. Резервная копия базы данных PostgreSQL
echo "📊 Создаем резервную копию базы данных..."
docker-compose exec -T db pg_dump -U crm_user crm_db > $BACKUP_DIR/crm_db_$DATE.sql

# 2. Резервная копия SQLite (если используется)
if [ -f "$PROJECT_DIR/app.db" ]; then
    echo "📊 Создаем резервную копию SQLite..."
    cp $PROJECT_DIR/app.db $BACKUP_DIR/app_$DATE.db
fi

# 3. Резервная копия статических файлов
echo "📁 Создаем резервную копию статических файлов..."
tar -czf $BACKUP_DIR/static_$DATE.tar.gz -C $PROJECT_DIR static/

# 4. Резервная копия конфигурации
echo "⚙️ Создаем резервную копию конфигурации..."
tar -czf $BACKUP_DIR/config_$DATE.tar.gz -C $PROJECT_DIR .env docker-compose.yml nginx.conf

# 5. Создаем общий архив
echo "📦 Создаем общий архив..."
cd $BACKUP_DIR
tar -czf crm_full_backup_$DATE.tar.gz \
    crm_db_$DATE.sql \
    static_$DATE.tar.gz \
    config_$DATE.tar.gz \
    $(if [ -f "app_$DATE.db" ]; then echo "app_$DATE.db"; fi)

# 6. Удаляем временные файлы
rm -f crm_db_$DATE.sql static_$DATE.tar.gz config_$DATE.tar.gz
if [ -f "app_$DATE.db" ]; then
    rm -f app_$DATE.db
fi

# 7. Удаляем старые резервные копии
echo "🗑️ Удаляем старые резервные копии (старше $RETENTION_DAYS дней)..."
find $BACKUP_DIR -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

# 8. Проверяем размер резервной копии
BACKUP_SIZE=$(du -h $BACKUP_DIR/crm_full_backup_$DATE.tar.gz | cut -f1)

echo ""
echo "✅ Резервное копирование завершено!"
echo "📦 Файл: crm_full_backup_$DATE.tar.gz"
echo "📏 Размер: $BACKUP_SIZE"
echo "📁 Расположение: $BACKUP_DIR"
echo ""

# 9. Отправляем уведомление (опционально)
if command -v mail &> /dev/null; then
    echo "Резервная копия CRM создана: $BACKUP_SIZE" | mail -s "CRM Backup $DATE" admin@yourdomain.com
fi

echo "🔄 Следующее резервное копирование: $(date -d '+1 day' '+%Y-%m-%d %H:%M')"
