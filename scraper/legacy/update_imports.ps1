# Import Update Script for File Reorganization
# Run this from apps/scraper directory

Write-Host "Updating imports in test files..." -ForegroundColor Cyan

# Define replacements
$replacements = @(
    @{Old="from crex_scraper_python.circuit_breaker import"; New="from src.core.circuit_breaker import"},
    @{Old="from crex_scraper_python.retry_utils import"; New="from src.core.retry_utils import"},
    @{Old="from crex_scraper_python.scraper_context import"; New="from src.core.scraper_context import"},
    @{Old="from crex_scraper_python.scraper_state import"; New="from src.core.scraper_state import"},
    @{Old="from crex_scraper_python.cleanup_orphans import"; New="from src.core.cleanup_orphans import"},
    @{Old="from crex_scraper_python.db_pool import"; New="from src.persistence.db_pool import"},
    @{Old="from crex_scraper_python.config import"; New="from src.config import"},
    @{Old="import crex_scraper_python.scraper_context"; New="import src.core.scraper_context"},
    @{Old="from crex_scraper_python.persistence.batch_writer import"; New="from src.persistence.batch_writer import"}
)

# Get all test files
$testFiles = Get-ChildItem -Path "crex_scraper_python\tests" -Recurse -Filter "*.py"

$updatedCount = 0
foreach ($file in $testFiles) {
    $content = Get-Content $file.FullName -Raw
    $originalContent = $content
    
    foreach ($replacement in $replacements) {
        $content = $content -replace [regex]::Escape($replacement.Old), $replacement.New
    }
    
    if ($content -ne $originalContent) {
        Set-Content -Path $file.FullName -Value $content -NoNewline
        Write-Host "Updated: $($file.Name)" -ForegroundColor Green
        $updatedCount++
    }
}

Write-Host "Total files updated: $updatedCount" -ForegroundColor Yellow
