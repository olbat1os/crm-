# 🚀 Развертывание CRM на Hostinger VPS

## 📋 Требования

### Минимальные требования VPS:
- **RAM**: 2GB (рекомендуется 4GB)
- **CPU**: 1 vCPU (рекомендуется 2 vCPU)
- **Диск**: 20GB SSD
- **ОС**: Ubuntu 20.04 LTS или новее

### Рекомендуемый тариф Hostinger:
- **VPS 1**: 1 vCPU, 4GB RAM, 50GB SSD - $3.99/месяц
- **VPS 2**: 2 vCPU, 8GB RAM, 100GB SSD - $8.99/месяц

## 🔧 Подготовка сервера

### 1. Подключение к серверу
```bash
ssh root@your-server-ip
```

### 2. Обновление системы
```bash
apt update && apt upgrade -y
```

### 3. Установка необходимых пакетов
```bash
apt install -y curl wget git unzip
```

### 4. Настройка файрвола
```bash
ufw allow 22    # SSH
ufw allow 80    # HTTP
ufw allow 443   # HTTPS
ufw enable
```

## 📁 Загрузка проекта

### Способ 1: Через Git (рекомендуется)
```bash
# Создаем директорию для проекта
mkdir -p /opt/crm
cd /opt/crm

# Клонируем репозиторий (замените на ваш URL)
git clone https://github.com/your-username/crm.git .

# Или загружаем архив
wget https://github.com/your-username/crm/archive/main.zip
unzip main.zip
mv crm-main/* .
rm -rf crm-main main.zip
```

### Способ 2: Через SCP
```bash
# На локальной машине
scp -r ./crm/* root@your-server-ip:/opt/crm/
```

## ⚙️ Настройка проекта

### 1. Создание файла конфигурации
```bash
cd /opt/crm
cp env.example .env
nano .env
```

### 2. Обязательные настройки в .env:
```env
# Генерируем безопасный SECRET_KEY
SECRET_KEY=$(openssl rand -hex 32)

# Устанавливаем безопасный пароль
APP_PASSWORD=your-very-secure-password-here

# Настройки для PostgreSQL
DATABASE_URL=postgresql://crm_user:crm_password@db:5432/crm_db
```

### 3. Генерация SECRET_KEY
```bash
# Генерируем случайный SECRET_KEY
openssl rand -hex 32
```

## 🐳 Развертывание с Docker

### 1. Запуск развертывания
```bash
chmod +x deploy.sh
./deploy.sh
```

### 2. Проверка статуса
```bash
docker-compose ps
docker-compose logs -f
```

## 🌐 Настройка домена и SSL

### 1. Настройка DNS
В панели управления доменом добавьте A-запись:
```
A    @    your-server-ip
A    www  your-server-ip
```

### 2. Установка SSL сертификата
```bash
# Устанавливаем Certbot
apt install -y certbot python3-certbot-nginx

# Получаем SSL сертификат
certbot --nginx -d your-domain.com -d www.your-domain.com
```

### 3. Обновление nginx.conf для домена
```bash
nano nginx.conf
```

Замените `server_name _;` на `server_name your-domain.com www.your-domain.com;`

## 📊 Мониторинг и обслуживание

### Полезные команды:
```bash
# Просмотр логов
docker-compose logs -f crm-app

# Перезапуск сервисов
docker-compose restart

# Обновление приложения
docker-compose down
git pull
docker-compose up -d --build

# Резервное копирование базы данных
docker-compose exec db pg_dump -U crm_user crm_db > backup.sql

# Восстановление из резервной копии
docker-compose exec -T db psql -U crm_user crm_db < backup.sql
```

### Автоматическое резервное копирование:
```bash
# Создаем скрипт резервного копирования
nano /opt/crm/backup.sh
```

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/crm/backups"
mkdir -p $BACKUP_DIR

# Создаем резервную копию базы данных
docker-compose exec -T db pg_dump -U crm_user crm_db > $BACKUP_DIR/crm_db_$DATE.sql

# Удаляем старые резервные копии (старше 7 дней)
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete

echo "Резервная копия создана: crm_db_$DATE.sql"
```

```bash
chmod +x /opt/crm/backup.sh

# Добавляем в crontab (ежедневно в 2:00)
crontab -e
# Добавляем строку:
0 2 * * * /opt/crm/backup.sh
```

## 🔒 Безопасность

### 1. Настройка SSH ключей
```bash
# На локальной машине
ssh-keygen -t rsa -b 4096
ssh-copy-id root@your-server-ip

# Отключаем парольную аутентификацию
nano /etc/ssh/sshd_config
# Устанавливаем: PasswordAuthentication no
systemctl restart ssh
```

### 2. Настройка fail2ban
```bash
apt install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban
```

### 3. Регулярные обновления
```bash
# Создаем скрипт обновления
nano /opt/crm/update.sh
```

```bash
#!/bin/bash
apt update && apt upgrade -y
docker-compose pull
docker-compose up -d --build
```

## 🚨 Устранение проблем

### Приложение не запускается:
```bash
# Проверяем логи
docker-compose logs crm-app

# Проверяем конфигурацию
docker-compose config

# Пересобираем контейнеры
docker-compose down
docker-compose up -d --build --force-recreate
```

### База данных не работает:
```bash
# Проверяем статус PostgreSQL
docker-compose exec db pg_isready -U crm_user

# Подключаемся к базе данных
docker-compose exec db psql -U crm_user crm_db
```

### Nginx не работает:
```bash
# Проверяем конфигурацию
nginx -t

# Перезапускаем Nginx
docker-compose restart nginx
```

## 📱 Доступ к приложению

После успешного развертывания ваше приложение будет доступно по адресу:
- **HTTP**: http://your-domain.com
- **HTTPS**: https://your-domain.com

### Данные для входа:
- **Логин**: admin
- **Пароль**: (из файла .env)

## ✅ Чек-лист развертывания

- [ ] VPS сервер настроен
- [ ] Docker и Docker Compose установлены
- [ ] Проект загружен на сервер
- [ ] Файл .env настроен
- [ ] SECRET_KEY изменен
- [ ] APP_PASSWORD изменен
- [ ] Docker контейнеры запущены
- [ ] Приложение доступно по HTTP
- [ ] Домен настроен
- [ ] SSL сертификат установлен
- [ ] Файрвол настроен
- [ ] Резервное копирование настроено

**🎉 Поздравляем! Ваша CRM система успешно развернута на Hostinger VPS!**
