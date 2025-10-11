# 🚀 CRM System - Система управления клиентами

## 📋 Описание

Современная CRM система для управления клиентами, резервациями и маркетингом. Разработана с использованием FastAPI, SQLModel и PostgreSQL.

## ✨ Возможности

- 👥 **Управление клиентами**: Полная база данных клиентов с детальной информацией
- 📅 **Система резерваций**: Планирование и управление бронированиями
- 📊 **Аналитика**: Статистика посещений, расходов и активности клиентов
- 🏷️ **Теги и категории**: Гибкая система классификации клиентов
- 🗺️ **Геолокация**: Отображение клиентов на карте
- 📱 **Адаптивный дизайн**: Работает на всех устройствах
- 🔒 **Безопасность**: Аутентификация и авторизация

## 🛠️ Технологии

- **Backend**: FastAPI, Python 3.11
- **База данных**: PostgreSQL, SQLModel
- **Frontend**: HTML, CSS, JavaScript, Jinja2
- **Контейнеризация**: Docker, Docker Compose
- **Веб-сервер**: Nginx
- **Язык интерфейса**: Сербский

## 🚀 Быстрый старт

### Локальная разработка

1. **Клонируйте репозиторий**
```bash
git clone https://github.com/your-username/crm.git
cd crm
```

2. **Настройте окружение**
```bash
cp env.example .env
# Отредактируйте .env файл
```

3. **Запустите с Docker**
```bash
docker-compose up -d
```

4. **Откройте приложение**
```
http://localhost:8000
```

### Развертывание на Hostinger VPS

Подробная инструкция в файле [HOSTINGER_DEPLOYMENT.md](HOSTINGER_DEPLOYMENT.md)

## 📁 Структура проекта

```
crm/
├── app/                    # Исходный код приложения
│   ├── main.py            # Главный файл FastAPI
│   ├── models.py          # Модели данных
│   ├── db.py              # Настройки базы данных
│   └── config.py          # Конфигурация
├── templates/             # HTML шаблоны
├── static/                # Статические файлы (CSS, JS, изображения)
├── docker-compose.yml     # Docker Compose конфигурация
├── Dockerfile            # Docker образ
├── nginx.conf            # Nginx конфигурация
├── requirements.txt      # Python зависимости
├── deploy.sh             # Скрипт развертывания
├── backup.sh             # Скрипт резервного копирования
├── update.sh             # Скрипт обновления
├── env.example           # Пример настроек
└── README.md             # Документация
```

## ⚙️ Конфигурация

### Основные настройки в .env:

```env
# Безопасность
SECRET_KEY=your-very-secure-secret-key
APP_PASSWORD=your-secure-password

# База данных
DATABASE_URL=postgresql://user:password@localhost:5432/crm_db

# Локализация
LOCALE=sr
TIMEZONE=Europe/Belgrade
```

## 🔧 Управление

### Полезные команды:

```bash
# Запуск
docker-compose up -d

# Остановка
docker-compose down

# Просмотр логов
docker-compose logs -f

# Перезапуск
docker-compose restart

# Обновление
./update.sh

# Резервное копирование
./backup.sh
```

## 📊 Мониторинг

### Health Check
```
GET /health
```

### Статус сервисов
```bash
docker-compose ps
```

## 🔒 Безопасность

- ✅ HTTPS с SSL сертификатами
- ✅ Rate limiting для API
- ✅ Security headers
- ✅ Аутентификация пользователей
- ✅ Защита от XSS и CSRF
- ✅ Безопасные пароли

## 📱 Доступ к приложению

После развертывания приложение доступно по адресу:
- **Локально**: http://localhost:8000
- **Продакшн**: https://your-domain.com

### Данные для входа:
- **Логин**: admin
- **Пароль**: (из файла .env)

## 🆘 Поддержка

### Устранение проблем:

1. **Приложение не запускается**
   ```bash
   docker-compose logs crm-app
   ```

2. **База данных недоступна**
   ```bash
   docker-compose exec db pg_isready -U crm_user
   ```

3. **Nginx не работает**
   ```bash
   docker-compose logs nginx
   ```

### Логи и отладка:
```bash
# Все логи
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f crm-app
docker-compose logs -f db
docker-compose logs -f nginx
```

## 📈 Производительность

### Рекомендуемые ресурсы:
- **RAM**: 2GB (минимум), 4GB (рекомендуется)
- **CPU**: 1 vCPU (минимум), 2 vCPU (рекомендуется)
- **Диск**: 20GB SSD (минимум), 50GB SSD (рекомендуется)

### Оптимизации:
- Gzip сжатие
- Кэширование статических файлов
- Connection pooling
- Health checks
- Rate limiting

## 🔄 Обновления

### Автоматическое обновление:
```bash
./update.sh
```

### Ручное обновление:
```bash
docker-compose down
git pull
docker-compose up -d --build
```

## 📋 Лицензия

Этот проект разработан для внутреннего использования.

## 👥 Команда

- **Разработка**: CRM Team
- **Поддержка**: admin@yourdomain.com

---

**🎉 Спасибо за использование нашей CRM системы!**