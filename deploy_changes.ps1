# Скрипт для загрузки обновленных файлов на сервер
# Сервер: root@72.60.182.59
# Директория: crm- (нужно уточнить точный путь)

$SERVER = "root@72.60.182.59"
$APP_DIR = "/root/crm-"  # Уточним точный путь при подключении

Write-Host "🚀 Загрузка обновленных файлов на сервер..." -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""

# Файлы для загрузки (измененные файлы)
$files = @(
    "app/auth.py",
    "app/main.py",
    "templates/admin_businesses_new.html",
    "templates/admin_dashboard_new.html",
    "templates/admin_business_detail_new.html"
)

Write-Host "📤 Загрузка файлов..." -ForegroundColor Yellow
foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "  → $file" -ForegroundColor Cyan
        scp $file "${SERVER}:${APP_DIR}/$file"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    ✓ Успешно загружен" -ForegroundColor Green
        } else {
            Write-Host "    ✗ Ошибка загрузки" -ForegroundColor Red
        }
    } else {
        Write-Host "  ✗ Файл не найден: $file" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "🔧 Подключение к серверу для перезапуска Docker..." -ForegroundColor Yellow
Write-Host "Выполните следующие команды на сервере:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  cd crm-" -ForegroundColor Cyan
Write-Host "  docker-compose restart crm-app" -ForegroundColor Cyan
Write-Host "  # или" -ForegroundColor Gray
Write-Host "  docker-compose up -d --build crm-app" -ForegroundColor Cyan
Write-Host ""
Write-Host "Или выполните автоматически:" -ForegroundColor Yellow
$auto = Read-Host "Выполнить перезапуск автоматически? (y/n)"
if ($auto -eq "y" -or $auto -eq "Y") {
    Write-Host "🔄 Перезапуск Docker контейнера..." -ForegroundColor Yellow
    ssh $SERVER "cd crm- && docker-compose restart crm-app"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Контейнер перезапущен!" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Попробуйте пересобрать контейнер:" -ForegroundColor Yellow
        Write-Host "   ssh $SERVER 'cd crm- && docker-compose up -d --build crm-app'" -ForegroundColor Cyan
    }
}

Write-Host ""
Write-Host "✅ Готово! Файлы загружены." -ForegroundColor Green
Write-Host ""
Write-Host "📋 Для проверки логов выполните:" -ForegroundColor Yellow
Write-Host "   ssh $SERVER 'cd crm- && docker-compose logs --tail=50 crm-app'" -ForegroundColor Cyan

