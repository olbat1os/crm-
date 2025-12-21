# Правильный скрипт для загрузки файлов с проверкой Docker volume
# Сервер: root@72.60.182.59

$SERVER = "root@72.60.182.59"

Write-Host "🔍 Определение правильного пути для загрузки..." -ForegroundColor Yellow
Write-Host ""

# 1. Находим имя контейнера
Write-Host "Поиск Docker контейнера..." -ForegroundColor Cyan
$containerName = ssh $SERVER "docker ps --format '{{.Names}}' | grep crm | head -1"
Write-Host "Контейнер: $containerName" -ForegroundColor Green

if (-not $containerName) {
    Write-Host "❌ Контейнер не найден!" -ForegroundColor Red
    exit 1
}

# 2. Проверяем, где находятся файлы в контейнере
Write-Host ""
Write-Host "Проверка структуры внутри контейнера..." -ForegroundColor Cyan
ssh $SERVER "docker exec $containerName ls -la /app/templates/ | head -5"

# 3. Проверяем volumes
Write-Host ""
Write-Host "Проверка volumes контейнера..." -ForegroundColor Cyan
$mounts = ssh $SERVER "docker inspect $containerName --format '{{json .Mounts}}' | ConvertFrom-Json"
$mounts | ForEach-Object {
    Write-Host "  Source: $($_.Source)" -ForegroundColor Cyan
    Write-Host "  Destination: $($_.Destination)" -ForegroundColor Cyan
    Write-Host ""
}

# 4. Определяем путь для загрузки
Write-Host "========================================" -ForegroundColor Green
Write-Host "ВАРИАНТ 1: Если volume примонтирован с хоста" -ForegroundColor Yellow
Write-Host "Копируйте файлы напрямую в Source путь (см. выше)" -ForegroundColor Cyan
Write-Host ""
Write-Host "ВАРИАНТ 2: Если volume не примонтирован" -ForegroundColor Yellow
Write-Host "Копируйте файлы внутрь контейнера" -ForegroundColor Cyan
Write-Host ""

$method = Read-Host "Выберите метод (1 - volume на хосте, 2 - внутрь контейнера)"

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

if ($method -eq "1") {
    # Вариант 1: Копирование в volume на хосте
    $volumePath = Read-Host "Введите путь к volume на хосте (например: /var/lib/docker/volumes/crm_data/_data)"
    
    Write-Host ""
    Write-Host "📤 Загрузка файлов в volume..." -ForegroundColor Yellow
    
    foreach ($file in $files) {
        if (Test-Path $file) {
            $remotePath = "$volumePath/$file"
            Write-Host "  → $file -> $remotePath" -ForegroundColor Cyan
            
            # Создаем директорию если нужно
            $dir = Split-Path $remotePath -Parent
            ssh $SERVER "mkdir -p $dir"
            
            scp $file "${SERVER}:$remotePath"
            if ($LASTEXITCODE -eq 0) {
                Write-Host "    ✓ Успешно" -ForegroundColor Green
            }
        }
    }
    
    Write-Host ""
    Write-Host "🔄 Перезапуск контейнера..." -ForegroundColor Yellow
    ssh $SERVER "docker restart $containerName"
    
} elseif ($method -eq "2") {
    # Вариант 2: Копирование внутрь контейнера
    Write-Host ""
    Write-Host "📤 Загрузка файлов внутрь контейнера..." -ForegroundColor Yellow
    
    foreach ($file in $files) {
        if (Test-Path $file) {
            Write-Host "  → $file" -ForegroundColor Cyan
            
            # Загружаем на сервер во временную директорию
            $tempFile = "/tmp/$(Split-Path $file -Leaf)"
            scp $file "${SERVER}:$tempFile"
            
            if ($LASTEXITCODE -eq 0) {
                # Копируем внутрь контейнера
                $containerPath = "/app/$file"
                ssh $SERVER "docker cp $tempFile ${containerName}:$containerPath"
                
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "    ✓ Успешно загружено в контейнер" -ForegroundColor Green
                } else {
                    Write-Host "    ✗ Ошибка копирования в контейнер" -ForegroundColor Red
                }
                
                # Удаляем временный файл
                ssh $SERVER "rm -f $tempFile"
            }
        }
    }
    
    Write-Host ""
    Write-Host "🔄 Перезапуск контейнера..." -ForegroundColor Yellow
    ssh $SERVER "docker restart $containerName"
}

Write-Host ""
Write-Host "✅ Готово!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Проверка логов:" -ForegroundColor Yellow
Write-Host "   ssh $SERVER 'docker logs --tail=50 $containerName'" -ForegroundColor Cyan

