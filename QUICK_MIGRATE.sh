#!/bin/bash
# Быстрый скрипт для поиска базы данных и выполнения миграции

CONTAINER="crm--crm-app-1"

echo "🔍 Поиск базы данных..."

# Проверяем volumes
echo "Проверка volumes контейнера:"
docker inspect ${CONTAINER} | grep -A 10 Mounts

echo ""
echo "Поиск .db файлов в контейнере:"
docker exec ${CONTAINER} find / -name "*.db" -type f 2>/dev/null | head -5

echo ""
echo "Проверка переменных окружения:"
docker exec ${CONTAINER} env | grep -i -E "db|database|sqlite"

echo ""
echo "Проверка docker-compose.yml для volumes:"
cd /root/crm- && grep -A 5 "volumes:" docker-compose.yml

echo ""
echo "Если база данных в volume, найдите путь:"
docker volume ls | grep crm

