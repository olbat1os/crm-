# Скрипт для загрузки всех 25 обновленных файлов на сервер
# Сервер: root@72.60.182.59
# Директория: crm-

$SERVER = "root@72.60.182.59"
$APP_DIR = "/root/crm-"

Write-Host "🚀 Загрузка всех 25 обновленных файлов на сервер..." -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""

# Список всех 25 файлов
$files = @(
    # Templates с favicon (21 файл)
    "templates/booking_base.html",
    "templates/clients_base.html",
    "templates/client_detail_base.html",
    "templates/dashboard_base.html",
    "templates/admin_base.html",
    "templates/settings_base.html",
    "templates/marketing_base.html",
    "templates/login_base.html",
    "templates/login_page_base.html",
    "templates/map_base.html",
    "templates/landing.html",
    "templates/error.html",
    "templates/admin_login.html",
    "templates/admin_login_new.html",
    "templates/admin_verify_code.html",
    "templates/admin_dashboard.html",
    "templates/admin_businesses.html",
    "templates/admin_business_detail.html",
    "templates/admin_business_edit.html",
    "templates/admin_settings.html",
    "templates/admin_pending.html",
    
    # Основные файлы с изменениями (4 файла)
    "templates/booking.html",
    "templates/clients.html",
    "templates/client_detail.html",
    "app/main.py"
)

$successCount = 0
$failCount = 0
$notFoundCount = 0

Write-Host "📤 Загрузка файлов..." -ForegroundColor Yellow
Write-Host ""

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "  → $file" -ForegroundColor Cyan
        scp $file "${SERVER}:${APP_DIR}/$file"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    ✓ Успешно загружен" -ForegroundColor Green
            $successCount++
        } else {
            Write-Host "    ✗ Ошибка загрузки" -ForegroundColor Red
            $failCount++
        }
    } else {
        Write-Host "  ✗ Файл не найден: $file" -ForegroundColor Gray
        $notFoundCount++
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Статистика:" -ForegroundColor Yellow
Write-Host "  ✓ Успешно: $successCount" -ForegroundColor Green
Write-Host "  ✗ Ошибки: $failCount" -ForegroundColor Red
Write-Host "  ? Не найдено: $notFoundCount" -ForegroundColor Gray
Write-Host ""

Write-Host "🔄 Перезапуск Docker контейнера..." -ForegroundColor Yellow
ssh $SERVER "cd crm- && docker-compose restart crm-app"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Контейнер перезапущен!" -ForegroundColor Green
} else {
    Write-Host "⚠️ Ошибка при перезапуске. Попробуйте пересобрать:" -ForegroundColor Yellow
    Write-Host "   ssh $SERVER 'cd crm- && docker-compose up -d --build crm-app'" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "✅ Готово! Файлы загружены." -ForegroundColor Green
Write-Host ""
Write-Host "📋 Для проверки логов выполните:" -ForegroundColor Yellow
Write-Host "   ssh $SERVER 'cd crm- && docker-compose logs --tail=50 crm-app'" -ForegroundColor Cyan
Write-Host ""

