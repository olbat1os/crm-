# Команды для загрузки всех обновленных файлов на сервер
# Сервер: root@72.60.182.59
# Директория: crm-

$SERVER = "root@72.60.182.59"
$APP_DIR = "/root/crm-"

Write-Host "📤 Загрузка всех обновленных файлов..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Список всех файлов для загрузки
$files = @(
    # Templates
    "templates/booking.html",
    "templates/clients.html",
    "templates/client_detail.html",
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
    
    # App files
    "app/main.py"
)

Write-Host "Загружаю файлы..." -ForegroundColor Yellow
Write-Host ""

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "  → $file" -ForegroundColor Cyan
        scp $file "${SERVER}:${APP_DIR}/$file"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    ✓ Успешно" -ForegroundColor Green
        } else {
            Write-Host "    ✗ Ошибка" -ForegroundColor Red
        }
    } else {
        Write-Host "  ✗ Не найден: $file" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "🔄 Перезапуск Docker контейнера..." -ForegroundColor Yellow
ssh $SERVER "cd crm- && docker-compose restart crm-app"

Write-Host ""
Write-Host "✅ Готово!" -ForegroundColor Green

