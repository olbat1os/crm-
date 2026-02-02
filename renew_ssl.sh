#!/bin/bash

# Скрипт для обновления SSL сертификата Let's Encrypt
# Использование: ./renew_ssl.sh yourdomain.com your@email.com
# ВАЖНО: Этот скрипт НЕ удаляет существующие сертификаты, только обновляет их

set -e

DOMAIN=$1
EMAIL=$2

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Использование: ./renew_ssl.sh yourdomain.com your@email.com"
    exit 1
fi

echo "Обновление SSL сертификата для домена: $DOMAIN"

# Переходим в папку проекта
cd /root/crm- || cd ~/crm- || { echo "Не найдена папка crm-"; exit 1; }

# СОЗДАЕМ РЕЗЕРВНУЮ КОПИЮ существующих сертификатов (если они есть)
if [ -f "ssl/cert.pem" ] && [ -f "ssl/key.pem" ]; then
    echo "Создание резервной копии существующих сертификатов..."
    BACKUP_DIR="ssl_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    cp ssl/cert.pem "$BACKUP_DIR/cert.pem.backup" 2>/dev/null || true
    cp ssl/key.pem "$BACKUP_DIR/key.pem.backup" 2>/dev/null || true
    echo "Резервная копия создана в: $BACKUP_DIR"
fi

# Устанавливаем certbot если его нет
if ! command -v certbot &> /dev/null; then
    echo "Установка certbot..."
    apt-get update
    apt-get install -y certbot
fi

# Останавливаем nginx контейнер временно для получения сертификата
echo "Остановка nginx контейнера..."
docker-compose stop nginx

# Получаем новый сертификат (certbot автоматически обновит существующий или создаст новый)
echo "Получение/обновление SSL сертификата..."
if certbot certificates | grep -q "$DOMAIN"; then
    echo "Существующий сертификат найден, обновляем..."
    certbot renew --cert-name "$DOMAIN" --quiet
else
    echo "Создание нового сертификата..."
    certbot certonly --standalone \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        -d "$DOMAIN" \
        --preferred-challenges http
fi

# Проверяем, что сертификаты получены успешно
if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ] || [ ! -f "/etc/letsencrypt/live/$DOMAIN/privkey.pem" ]; then
    echo "ОШИБКА: Не удалось получить сертификаты!"
    echo "Восстанавливаем из резервной копии..."
    if [ -d "$BACKUP_DIR" ]; then
        cp "$BACKUP_DIR/cert.pem.backup" ssl/cert.pem 2>/dev/null || true
        cp "$BACKUP_DIR/key.pem.backup" ssl/key.pem 2>/dev/null || true
    fi
    docker-compose start nginx
    exit 1
fi

# Копируем сертификаты в папку ssl (ПЕРЕЗАПИСЫВАЕМ только если успешно получены новые)
echo "Копирование новых сертификатов..."
mkdir -p ssl
cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ssl/cert.pem
cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ssl/key.pem

# Устанавливаем правильные права доступа
chmod 644 ssl/cert.pem
chmod 600 ssl/key.pem

# Запускаем nginx обратно
echo "Запуск nginx контейнера..."
docker-compose start nginx

# Проверяем срок действия нового сертификата
echo ""
echo "✅ SSL сертификат успешно обновлен!"
echo "📅 Срок действия:"
openssl x509 -in ssl/cert.pem -noout -dates 2>/dev/null || echo "Не удалось проверить даты"
echo ""
echo "🌐 Проверьте работу сайта: https://$DOMAIN"
echo "💾 Резервная копия сохранена в: $BACKUP_DIR (если была создана)"
