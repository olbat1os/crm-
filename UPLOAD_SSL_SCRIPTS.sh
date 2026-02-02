#!/bin/bash
# Скрипт для загрузки SSL скриптов на сервер (для Linux/Mac)
# Использование: ./UPLOAD_SSL_SCRIPTS.sh

SERVER="root@72.60.182.59"
REMOTE_DIR="/root/crm-"

echo "🚀 Загрузка SSL скриптов на сервер..."
echo "=================================="
echo ""

# Файлы для загрузки
files=(
    "renew_ssl.sh"
    "setup_ssl_auto_renew.sh"
)

echo "📤 Загрузка файлов..."
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  → $file"
        scp "$file" "${SERVER}:${REMOTE_DIR}/$file"
        if [ $? -eq 0 ]; then
            echo "    ✓ Успешно загружен"
        else
            echo "    ✗ Ошибка загрузки"
        fi
    else
        echo "  ✗ Файл не найден: $file"
    fi
done

echo ""
echo "🔧 Установка прав на выполнение..."
ssh $SERVER "cd $REMOTE_DIR && chmod +x renew_ssl.sh setup_ssl_auto_renew.sh"

echo ""
echo "✅ Готово! Скрипты загружены на сервер."
echo ""
echo "📋 Теперь на сервере выполните:"
echo "   cd crm-"
echo "   ./renew_ssl.sh yourdomain.com your@email.com"
echo ""
