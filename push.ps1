# Читаем версию из файла VERSION
$version = Get-Content -Path "VERSION" -Raw | Trim

Write-Host "Пушу версию: $version" -ForegroundColor Cyan

# Добавляем все изменения
git add .

# Делаем коммит с названием версии
git commit -m "$version"

# Создаём тег с этой же версией (если такого ещё нет)
git tag -a "$version" -m "$version" 2>$null

# Пушим коммиты
git push

# Пушим теги
git push origin "$version"

Write-Host "Готово! Версия $version запушена на GitHub." -ForegroundColor Green
