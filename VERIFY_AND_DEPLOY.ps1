# Скрипт для проверки пути и загрузки файлов в правильную директорию
# Сервер: root@72.60.182.59

$SERVER = "root@72.60.182.59"

Write-Host "🔍 Шаг 1: Проверка структуры на сервере..." -ForegroundColor Yellow
Write-Host ""

# Проверяем директории
Write-Host "Директории в /root:" -ForegroundColor Cyan
ssh $SERVER "ls -la /root/ | grep -E '^d.*crm'"

Write-Host ""
Write-Host "Поиск директории crm-:" -ForegroundColor Cyan
$crmPath = ssh $SERVER "find /root -maxdepth 2 -name '*crm*' -type d 2>/dev/null | head -1"
Write-Host "Найденный путь: $crmPath" -ForegroundColor Green

Write-Host ""
Write-Host "Проверка docker-compose.yml:" -ForegroundColor Cyan
$dockerPath = ssh $SERVER "find /root -name 'docker-compose.yml' -type f 2>/dev/null | head -1"
if ($dockerPath) {
    $dockerDir = ssh $SERVER "dirname '$dockerPath'"
    Write-Host "Docker директория: $dockerDir" -ForegroundColor Green
} else {
    Write-Host "docker-compose.yml не найден!" -ForegroundColor Red
}

Write-Host ""
Write-Host "Проверка Docker контейнера:" -ForegroundColor Cyan
$containerName = ssh $SERVER "docker ps --format '{{.Names}}' | grep crm | head -1"
Write-Host "Контейнер: $containerName" -ForegroundColor Green

Write-Host ""
Write-Host "Проверка volumes в docker-compose:" -ForegroundColor Cyan
ssh $SERVER "cd $dockerDir && grep -A 5 'volumes:' docker-compose.yml | head -10"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "ВАЖНО: Убедитесь, что путь правильный!" -ForegroundColor Yellow
Write-Host "Если Docker использует volume, файлы нужно копировать:" -ForegroundColor Yellow
Write-Host "1. В директорию на хосте (если volume примонтирован)" -ForegroundColor Cyan
Write-Host "2. Или внутрь контейнера (если volume не примонтирован)" -ForegroundColor Cyan
Write-Host ""

$confirm = Read-Host "Продолжить загрузку файлов? (y/n)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "Отменено." -ForegroundColor Red
    exit
}

Write-Host ""
Write-Host "📤 Шаг 2: Загрузка файлов..." -ForegroundColor Yellow
Write-Host ""

# Определяем путь (используем найденный или по умолчанию)
$APP_DIR = if ($dockerDir) { $dockerDir } else { "/root/crm-" }
Write-Host "Используемый путь: $APP_DIR" -ForegroundColor Green
Write-Host ""

# Список файлов
$files = @(
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
    "templates/booking.html",
    "templates/clients.html",
    "templates/client_detail.html",
    "app/main.py"
)

$successCount = 0
foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "  → $file" -ForegroundColor Cyan
        scp $file "${SERVER}:${APP_DIR}/$file"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    ✓ Успешно" -ForegroundColor Green
            $successCount++
        } else {
            Write-Host "    ✗ Ошибка" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "✅ Загружено: $successCount из $($files.Count) файлов" -ForegroundColor Green

Write-Host ""
Write-Host "🔍 Шаг 3: Проверка что файлы загружены..." -ForegroundColor Yellow
ssh $SERVER "ls -lh ${APP_DIR}/templates/booking.html"
ssh $SERVER "ls -lh ${APP_DIR}/app/main.py"

Write-Host ""
Write-Host "🔄 Шаг 4: Перезапуск Docker..." -ForegroundColor Yellow
ssh $SERVER "cd ${APP_DIR} && docker-compose restart crm-app"

Write-Host ""
Write-Host "✅ Готово!" -ForegroundColor Green

