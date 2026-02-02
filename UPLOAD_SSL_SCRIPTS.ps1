# Скрипт для загрузки SSL скриптов на сервер
# Сервер: root@72.60.182.59
# Директория: /root/crm-

$SERVER = "root@72.60.182.59"
$REMOTE_DIR = "/root/crm-"

Write-Host "🚀 Загрузка SSL скриптов на сервер..." -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green
Write-Host ""

# Файлы для загрузки
$files = @(
    "renew_ssl.sh",
    "setup_ssl_auto_renew.sh"
)

Write-Host "📤 Загрузка файлов..." -ForegroundColor Yellow
foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "  → $file" -ForegroundColor Cyan
        scp $file "${SERVER}:${REMOTE_DIR}/$file"
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
Write-Host "🔧 Установка прав на выполнение..." -ForegroundColor Yellow
ssh $SERVER "cd $REMOTE_DIR && chmod +x renew_ssl.sh setup_ssl_auto_renew.sh"

Write-Host ""
Write-Host "✅ Готово! Скрипты загружены на сервер." -ForegroundColor Green
Write-Host ""
Write-Host "📋 Теперь на сервере выполните:" -ForegroundColor Yellow
Write-Host "   cd crm-" -ForegroundColor Cyan
Write-Host "   ./renew_ssl.sh yourdomain.com your@email.com" -ForegroundColor Cyan
Write-Host ""
