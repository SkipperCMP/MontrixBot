# git_push_version_v2.ps1
# Авто-коммит + пуш + тег по содержимому файла VERSION
# Запускать ТОЛЬКО из корня репозитория (D:\Projects\MontrixBot)

$ErrorActionPreference = "Stop"

function Fail($msg) {
    Write-Host ""
    Write-Host "ОШИБКА: $msg" -ForegroundColor Red
    exit 1
}

Write-Host "=== MontrixBot Git Push v2 ===" -ForegroundColor Cyan
Write-Host "Текущая папка: $(Get-Location)" -ForegroundColor DarkGray

# --- ШАГ 0. Проверка, что мы в git-репозитории ---
if (-not (Test-Path ".git")) {
    Fail "Текущая папка не является git-репозиторием (.git не найден). Запусти скрипт из D:\Projects\MontrixBot."
}

# --- ШАГ 1. Прочитать версию из файла VERSION ---
$versionFile = "VERSION"

if (-not (Test-Path $versionFile)) {
    Fail "Файл VERSION не найден!"
}

$version = Get-Content $versionFile -Raw
$version = $version.Trim()

if ([string]::IsNullOrWhiteSpace($version)) {
    Fail "Файл VERSION пустой или содержит только пробелы."
}

Write-Host "Версия из файла VERSION: $version" -ForegroundColor Cyan

# --- Вспомогательная функция для git-команд ---
function Run-Git($args, $stepName) {
    Write-Host ""
    Write-Host ">>> $stepName" -ForegroundColor Yellow
    git @args
    if ($LASTEXITCODE -ne 0) {
        Fail "Git-команда '$($args -join " ")' завершилась с ошибкой (код $LASTEXITCODE). Проверь вывод выше."
    }
}

# --- ШАГ 2. Добавить все изменения ---
Run-Git @("add", ".") "Шаг 2: git add ."

# --- ШАГ 3. Создать коммит ---
Run-Git @("commit", "-m", $version) "Шаг 3: git commit -m '$version'"

# --- ШАГ 4. Отправить на GitHub ---
Run-Git @("push") "Шаг 4: git push"

# --- ШАГ 5. Создать тег (если отсутствует) и отправить его ---
Write-Host ""
Write-Host ">>> Шаг 5: проверка тега" -ForegroundColor Yellow

$existingTag = git tag -l $version
if ($LASTEXITCODE -ne 0) {
    Fail "Не удалось получить список тегов (git tag -l)."
}

if ([string]::IsNullOrWhiteSpace($existingTag)) {
    Write-Host "Тег $version не найден — создаю..." -ForegroundColor Cyan
    Run-Git @("tag", "-a", $version, "-m", $version) "Создание тега $version"
    Run-Git @("push", "origin", $version) "Отправка тега $version на origin"
    Write-Host "Создан и отправлен новый тег: $version" -ForegroundColor Green
} else {
    Write-Host "Тег $version уже существует — пропускаю создание и отправку." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== ГОТОВО: коммит и тег для $version успешно отправлены на GitHub ===" -ForegroundColor Green
