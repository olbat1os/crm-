# Скрипт для загрузки обновленных файлов на сервер
# Сервер: root@72.60.182.59
# Директория: /var/www/lovacrm

$SERVER = "root@72.60.182.59"
$APP_DIR = "/var/www/lovacrm"

Write-Host "🚀 Загрузка файлов на сервер..." -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green
Write-Host ""

# Файлы для загрузки
$files = @(
    "templates/booking.html",
    "templates/client_detail.html",
    "templates/settings.html",
    "app/models.py",
    "app/main.py",
    "migrate_deposit_lead_source.py"
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
Write-Host "🔧 Выполнение миграции базы данных..." -ForegroundColor Yellow
ssh $SERVER "cd $APP_DIR && python3 migrate_deposit_lead_source.py"

Write-Host ""
Write-Host "🔄 Перезапуск приложения..." -ForegroundColor Yellow
ssh $SERVER "cd $APP_DIR && systemctl restart lovacrm || supervisorctl restart lovacrm || pkill -f uvicorn"

Write-Host ""
Write-Host "✅ Готово! Все файлы загружены и миграция выполнена." -ForegroundColor Green






