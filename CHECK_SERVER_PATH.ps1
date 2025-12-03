# Скрипт для проверки пути на сервере перед загрузкой
# Сервер: root@72.60.182.59

$SERVER = "root@72.60.182.59"

Write-Host "🔍 Проверка структуры на сервере..." -ForegroundColor Yellow
Write-Host ""

Write-Host "1. Проверка директорий в /root:" -ForegroundColor Cyan
ssh $SERVER "ls -la /root/ | grep -E '^d.*crm'"

Write-Host ""
Write-Host "2. Поиск директории crm-:" -ForegroundColor Cyan
ssh $SERVER "find /root -maxdepth 2 -name '*crm*' -type d 2>/dev/null"

Write-Host ""
Write-Host "3. Проверка текущей директории Docker:" -ForegroundColor Cyan
ssh $SERVER "docker ps --format '{{.Names}}' | grep crm"

Write-Host ""
Write-Host "4. Проверка docker-compose.yml:" -ForegroundColor Cyan
ssh $SERVER "find /root -name 'docker-compose.yml' -type f 2>/dev/null | head -1 | xargs dirname"

Write-Host ""
Write-Host "✅ После определения правильного пути, обновите команды в DEPLOY_25_FILES.txt" -ForegroundColor Green

