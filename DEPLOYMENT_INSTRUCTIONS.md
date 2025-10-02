# 🚀 Инструкция по развертыванию CRM на сербском сервере

## 📋 Что нужно на сервере

- Docker
- Docker Compose
- Git

## 📁 Файлы для развертывания

```
crm/
├── app/                 # Исходный код
├── templates/           # HTML шаблоны
├── static/             # Статические файлы
├── docker-compose.yml  # Docker конфигурация
├── Dockerfile         # Docker образ
├── nginx.conf         # Nginx конфигурация
├── requirements.txt   # Python зависимости
├── deploy.sh          # Скрипт развертывания
├── env.example        # Пример настроек
└── README.md          # Документация
```

## 🔧 Пошаговая инструкция

### 1. Загрузка на сервер

```bash
# Подключитесь к серверу
ssh username@server-ip

# Создайте папку
mkdir -p /opt/crm
cd /opt/crm

# Загрузите файлы (выберите один способ)
# Способ A: Через Git
git clone https://github.com/your-repo/crm.git .

# Способ B: Через SCP
scp -r ./crm/* username@server-ip:/opt/crm/
```

### 2. Настройка

```bash
# Создайте файл настроек
cp env.example .env

# Отредактируйте настройки
nano .env
```

**Обязательно измените в .env:**
```env
SECRET_KEY=your-very-secure-secret-key-32-chars-min
APP_PASSWORD=your-secure-password
LOCALE=sr
TIMEZONE=Europe/Belgrade
```

### 3. Развертывание

```bash
# Сделайте скрипт исполняемым
chmod +x deploy.sh

# Запустите развертывание
./deploy.sh
```

### 4. Проверка

```bash
# Проверьте статус
docker-compose ps

# Посмотрите логи
docker-compose logs -f
```

### 5. Доступ к приложению

- URL: `http://your-server-ip`
- Логин: `admin`
- Пароль: из .env файла

## 🔒 Безопасность

1. **Измените пароль по умолчанию**
2. **Настройте файрвол:**
```bash
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw enable
```

3. **Настройте SSL (рекомендуется):**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 📊 Управление

### Просмотр логов
```bash
docker-compose logs -f
```

### Остановка
```bash
docker-compose down
```

### Перезапуск
```bash
docker-compose restart
```

### Обновление
```bash
docker-compose down
git pull
docker-compose up -d --build
```

## 🚨 Устранение проблем

### Сервисы не запускаются
```bash
docker-compose logs
docker-compose config
```

### База данных не работает
```bash
docker-compose exec db pg_isready -U crm_user
```

### Приложение недоступно
```bash
netstat -tlnp | grep :80
```

## ✅ Чек-лист

- [ ] Docker установлен
- [ ] Файлы загружены
- [ ] .env настроен
- [ ] SECRET_KEY изменен
- [ ] APP_PASSWORD изменен
- [ ] deploy.sh выполнен
- [ ] Сервисы запущены
- [ ] Приложение доступно
- [ ] Вход работает
- [ ] Файрвол настроен

**🎉 Готово! CRM развернута на сербском сервере!**
