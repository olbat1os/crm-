#!/bin/bash

# Скрипт для настройки автоматического обновления SSL сертификата
# Использование: ./setup_ssl_auto_renew.sh yourdomain.com your@email.com

set -e

DOMAIN=$1
EMAIL=$2

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Использование: ./setup_ssl_auto_renew.sh yourdomain.com your@email.com"
    exit 1
fi

echo "Настройка автоматического обновления SSL сертификата для домена: $DOMAIN"

# Создаем скрипт для обновления сертификата в контейнере
cat > /usr/local/bin/renew-ssl-cert.sh << 'EOF'
#!/bin/bash
set -e

DOMAIN="$1"
if [ -z "$DOMAIN" ]; then
    echo "Ошибка: не указан домен"
    exit 1
fi

cd /root/crm- || cd ~/crm- || { echo "Не найдена папка crm-"; exit 1; }

# СОЗДАЕМ РЕЗЕРВНУЮ КОПИЮ перед обновлением
if [ -f "ssl/cert.pem" ] && [ -f "ssl/key.pem" ]; then
    BACKUP_DIR="ssl_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    cp ssl/cert.pem "$BACKUP_DIR/cert.pem.backup" 2>/dev/null || true
    cp ssl/key.pem "$BACKUP_DIR/key.pem.backup" 2>/dev/null || true
fi

# Останавливаем nginx для обновления сертификата
docker-compose stop nginx

# Обновляем сертификат (certbot обновит только если срок истекает в течение 30 дней)
certbot renew --cert-name "$DOMAIN" --quiet || certbot renew --quiet

# Проверяем, что сертификаты обновлены успешно
if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ] && [ -f "/etc/letsencrypt/live/$DOMAIN/privkey.pem" ]; then
    # Копируем сертификаты в папку проекта (только если успешно обновлены)
    mkdir -p ssl
    cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ssl/cert.pem
    cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ssl/key.pem
    
    # Устанавливаем права доступа
    chmod 644 ssl/cert.pem
    chmod 600 ssl/key.pem
    
    # Запускаем nginx обратно
    docker-compose start nginx
    
    echo "$(date): SSL сертификат успешно обновлен для $DOMAIN" >> /var/log/ssl-renewal.log
else
    # Восстанавливаем из резервной копии при ошибке
    if [ -d "$BACKUP_DIR" ]; then
        cp "$BACKUP_DIR/cert.pem.backup" ssl/cert.pem 2>/dev/null || true
        cp "$BACKUP_DIR/key.pem.backup" ssl/key.pem 2>/dev/null || true
    fi
    docker-compose start nginx
    echo "$(date): ОШИБКА обновления SSL сертификата для $DOMAIN" >> /var/log/ssl-renewal.log
    exit 1
fi
EOF

chmod +x /usr/local/bin/renew-ssl-cert.sh

# Создаем cron задачу для автоматического обновления (каждый день в 3:00)
CRON_JOB="0 3 * * * /usr/local/bin/renew-ssl-cert.sh $DOMAIN >> /var/log/ssl-renewal.log 2>&1"

# Проверяем, есть ли уже такая задача
if crontab -l 2>/dev/null | grep -q "renew-ssl-cert.sh"; then
    echo "Cron задача уже существует, обновляю..."
    crontab -l 2>/dev/null | grep -v "renew-ssl-cert.sh" | crontab -
fi

# Добавляем новую задачу
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "Автоматическое обновление SSL сертификата настроено!"
echo "Сертификат будет обновляться каждый день в 3:00"
echo "Логи обновлений: /var/log/ssl-renewal.log"
