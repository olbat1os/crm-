# Скрипт для загрузки обновленного booking.html на сервер
# Сервер: root@72.60.182.59
# Директория: crm-

$SERVER = "root@72.60.182.59"
$APP_DIR = "/root/crm-"  # Уточните точный путь, если отличается

Write-Host "🚀 Загрузка обновленного booking.html на сервер..." -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""

# Файл для загрузки
$file = "templates/booking.html"

if (Test-Path $file) {
    Write-Host "📤 Загрузка файла: $file" -ForegroundColor Yellow
    Write-Host "   На сервер: ${SERVER}:${APP_DIR}/$file" -ForegroundColor Cyan
    
    # Копируем файл через SCP
    scp $file "${SERVER}:${APP_DIR}/$file"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Файл успешно загружен!" -ForegroundColor Green
    } else {
        Write-Host "   ✗ Ошибка загрузки файла" -ForegroundColor Red
        Write-Host "   Проверьте подключение к серверу и путь" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "✗ Файл не найден: $file" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🔧 Перезапуск Docker контейнера..." -ForegroundColor Yellow
Write-Host ""

# Перезапуск контейнера
Write-Host "Выполняю команду на сервере..." -ForegroundColor Cyan
ssh $SERVER "cd crm- && docker-compose restart crm-app"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Контейнер перезапущен!" -ForegroundColor Green
} else {
    Write-Host "⚠️ Ошибка при перезапуске. Попробуйте пересобрать:" -ForegroundColor Yellow
    Write-Host "   ssh $SERVER 'cd crm- && docker-compose up -d --build crm-app'" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "📋 Для проверки логов выполните:" -ForegroundColor Yellow
Write-Host "   ssh $SERVER 'cd crm- && docker-compose logs --tail=50 crm-app'" -ForegroundColor Cyan
Write-Host ""
Write-Host "✅ Готово!" -ForegroundColor Green

