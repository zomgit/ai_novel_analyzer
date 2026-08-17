$ErrorActionPreference = 'Continue'
$baseUrl = 'http://newapi.openxz.cn/v1'
$key = 'G13BfnHF5kqs16iyLYyi04G5Ba0Sir0iLk1QI5BYdUxE8tAh'
$headers = @{ Authorization = "Bearer $key" }

function Test-InvokeChat($model, $promptText) {
    Write-Output ""
    $b = @{ model=$model; messages=@(@{role='user'; content=$promptText}); max_tokens=100 } | ConvertTo-Json -Depth 5
    try {
        $r = Invoke-RestMethod -Uri "$baseUrl/chat/completions" -Headers $headers -Method Post -ContentType 'application/json' -Body $b -TimeoutSec 120
        Write-Output ("OK: " + $r.model + ", reply: " + ($r.choices[0].message.content -replace '\s+', ' '))
        if ($r.usage) { Write-Output "usage:" $r.usage.prompt_tokens $r.usage.completion_tokens $r.usage.total_tokens }
    } catch {
        Write-Output "ERROR: " + $_.Exception.Message
    }
}

Write-Output "=== Chat Tests ==="
Test-InvokeChat 'deepseek-v3.2' 'Introduce yourself in one sentence.'
Test-InvokeChat 'glm-5' 'What is 2 plus 2? Answer only the number.'
Test-InvokeChat 'qwen3.7-plus' 'Name the capital of China. Only city name.'
