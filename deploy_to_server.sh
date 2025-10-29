#!/bin/bash

# LovaCRM v1.1 - Deploy to Server Script
# Сервер: root@72.60.182.59

echo "🚀 LovaCRM v1.1 - Deploy to Server"
echo "=================================="

# Настройки
SERVER="root@72.60.182.59"
APP_DIR="/var/www/lovacrm"
REPO_URL="https://github.com/olbat1os/crm-.git"
BRANCH="feature/lovacrm-v1.1"

echo "📡 Подключение к серверу: $SERVER"
echo "📁 Директория приложения: $APP_DIR"
echo "🌿 Ветка: $BRANCH"
echo ""

# Подключение к серверу и выполнение команд
ssh $SERVER << EOF
    echo "🔧 Обновление системы..."
    apt update -y
    
    echo "📦 Установка необходимых пакетов..."
    apt install -y python3 python3-pip python3-venv git nginx
    
    echo "📁 Создание директории приложения..."
    mkdir -p $APP_DIR
    cd $APP_DIR
    
    echo "📥 Клонирование репозитория..."
    if [ -d ".git" ]; then
        echo "🔄 Обновление существующего репозитория..."
        git fetch origin
        git checkout $BRANCH
        git pull origin $BRANCH
    else
        echo "📥 Клонирование нового репозитория..."
        git clone $REPO_URL .
        git checkout $BRANCH
    fi
    
    echo "🐍 Создание виртуального окружения..."
    python3 -m venv venv
    source venv/bin/activate
    
    echo "📦 Установка зависимостей..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    echo "⚙️ Настройка конфигурации..."
    cp env.example email_config.env
    echo "EMAIL_ENABLED=true" >> email_config.env
    echo "EMAIL_SMTP_SERVER=smtp.gmail.com" >> email_config.env
    echo "EMAIL_SMTP_PORT=587" >> email_config.env
    echo "EMAIL_USERNAME=lovacrmhelp@gmail.com" >> email_config.env
    echo "EMAIL_PASSWORD=rroshnuyzjcgwnvk" >> email_config.env
    echo "EMAIL_FROM_NAME=LovaCRM" >> email_config.env
    echo "EMAIL_FROM_ADDRESS=noreply@lovacrm.com" >> email_config.env
    echo "ADMIN_EMAIL=lovacrmhelp@gmail.com" >> email_config.env
    
    echo "🗄️ Инициализация базы данных..."
    python -c "from app.db import create_db_and_tables; create_db_and_tables()"
    
    echo "🌐 Настройка Nginx..."
    cat > /etc/nginx/sites-available/lovacrm << 'NGINX_EOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /static/ {
        alias $APP_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
NGINX_EOF
    
    ln -sf /etc/nginx/sites-available/lovacrm /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl reload nginx
    
    echo "🔄 Настройка systemd сервиса..."
    cat > /etc/systemd/system/lovacrm.service << 'SERVICE_EOF'
[Unit]
Description=LovaCRM Application
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE_EOF
    
    systemctl daemon-reload
    systemctl enable lovacrm
    systemctl restart lovacrm
    
    echo "✅ Проверка статуса сервиса..."
    systemctl status lovacrm --no-pager
    
    echo "🌐 Проверка доступности приложения..."
    sleep 5
    curl -f http://localhost:8000/health || echo "⚠️ Health check failed"
    
    echo ""
    echo "🎉 Деплой завершен!"
    echo "🌐 Приложение доступно по адресу: http://72.60.182.59"
    echo "📊 Статус сервиса: systemctl status lovacrm"
    echo "📋 Логи: journalctl -u lovacrm -f"
EOF

echo ""
echo "✅ Деплой завершен!"
echo "🌐 LovaCRM доступен по адресу: http://72.60.182.59"
echo ""
echo "📋 Полезные команды для управления:"
echo "  ssh $SERVER 'systemctl status lovacrm'"
echo "  ssh $SERVER 'journalctl -u lovacrm -f'"
echo "  ssh $SERVER 'systemctl restart lovacrm'"

