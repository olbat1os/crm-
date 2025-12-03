#!/bin/bash
# Команды для копирования файлов внутрь Docker контейнера
# Выполните эти команды на сервере (вы уже там: root@srv1037394:~/crm-#)

# 1. Проверяем имя контейнера
echo "Проверка контейнера..."
docker ps | grep crm-app

# 2. Копируем все файлы внутрь контейнера
CONTAINER_NAME="crm--crm-app-1"  # Или используйте имя из docker ps

echo "Копирование templates..."
docker cp /root/crm-/templates/booking_base.html ${CONTAINER_NAME}:/app/templates/booking_base.html
docker cp /root/crm-/templates/clients_base.html ${CONTAINER_NAME}:/app/templates/clients_base.html
docker cp /root/crm-/templates/client_detail_base.html ${CONTAINER_NAME}:/app/templates/client_detail_base.html
docker cp /root/crm-/templates/dashboard_base.html ${CONTAINER_NAME}:/app/templates/dashboard_base.html
docker cp /root/crm-/templates/admin_base.html ${CONTAINER_NAME}:/app/templates/admin_base.html
docker cp /root/crm-/templates/settings_base.html ${CONTAINER_NAME}:/app/templates/settings_base.html
docker cp /root/crm-/templates/marketing_base.html ${CONTAINER_NAME}:/app/templates/marketing_base.html
docker cp /root/crm-/templates/login_base.html ${CONTAINER_NAME}:/app/templates/login_base.html
docker cp /root/crm-/templates/login_page_base.html ${CONTAINER_NAME}:/app/templates/login_page_base.html
docker cp /root/crm-/templates/map_base.html ${CONTAINER_NAME}:/app/templates/map_base.html
docker cp /root/crm-/templates/landing.html ${CONTAINER_NAME}:/app/templates/landing.html
docker cp /root/crm-/templates/error.html ${CONTAINER_NAME}:/app/templates/error.html
docker cp /root/crm-/templates/admin_login.html ${CONTAINER_NAME}:/app/templates/admin_login.html
docker cp /root/crm-/templates/admin_login_new.html ${CONTAINER_NAME}:/app/templates/admin_login_new.html
docker cp /root/crm-/templates/admin_verify_code.html ${CONTAINER_NAME}:/app/templates/admin_verify_code.html
docker cp /root/crm-/templates/admin_dashboard.html ${CONTAINER_NAME}:/app/templates/admin_dashboard.html
docker cp /root/crm-/templates/admin_businesses.html ${CONTAINER_NAME}:/app/templates/admin_businesses.html
docker cp /root/crm-/templates/admin_business_detail.html ${CONTAINER_NAME}:/app/templates/admin_business_detail.html
docker cp /root/crm-/templates/admin_business_edit.html ${CONTAINER_NAME}:/app/templates/admin_business_edit.html
docker cp /root/crm-/templates/admin_settings.html ${CONTAINER_NAME}:/app/templates/admin_settings.html
docker cp /root/crm-/templates/admin_pending.html ${CONTAINER_NAME}:/app/templates/admin_pending.html
docker cp /root/crm-/templates/booking.html ${CONTAINER_NAME}:/app/templates/booking.html
docker cp /root/crm-/templates/clients.html ${CONTAINER_NAME}:/app/templates/clients.html
docker cp /root/crm-/templates/client_detail.html ${CONTAINER_NAME}:/app/templates/client_detail.html

echo "Копирование app..."
docker cp /root/crm-/app/main.py ${CONTAINER_NAME}:/app/app/main.py

echo "Перезапуск контейнера..."
docker-compose restart crm-app

echo "Готово! Проверьте изменения."

