$ErrorActionPreference = 'Continue'
$baseUrl = 'http://newapi.openxz.cn/v1'
$key = 'G13BfnHF5kqs16iyLYyi04G5Ba0Sir0iLk1QI5BYdUxE8tAh'
$headers = @{ Authorization = "Bearer $key" }

function Invoke-Chat($model, $content, $extra) {
    Write-Output ""
    Write-Output ("=== Chat test: $model ===")
    $payload = @{
        model = $model
        messages = @( @{ role = 'user'; content = $content } )
        max_tokens = 120
    }
    if ($extra) { foreach ($k in $extra.Keys) { $payload[$k] = $extra[$k] } }
    $body = $payload | ConvertTo-Json -Depth 6
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $resp = Invoke-RestMethod -Uri "$baseUrl/chat/completions" -Headers $headers -Method Post -ContentType 'application/json' -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 120
        $sw.Stop()
        Write-Output ("HTTP OK, latency: " + $sw.ElapsedMilliseconds + ' ms')
        Write-Output ('model field : ' + $resp.model)
        Write-Output ('finish_reason: ' + $resp.choices[0].finish_reason)
        Write-Output ('reply       : ' + ($resp.choices[0].message.content -replace '\s+', ' '))
        if ($resp.usage) {
            Write-Output ('usage       : prompt=' + $resp.usage.prompt_tokens + ', completion=' + $resp.usage.completion_tokens + ', total=' + $resp.usage.total_tokens)
        }
    } catch {
        $sw.Stop()
        Write-Output ('ERROR after ' + $sw.ElapsedMilliseconds + ' ms: ' + $_.Exception.Message)
        if ($_.Exception.Response) {
            $sr = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            Write-Output $sr.ReadToEnd()
        }
    }
}

# Test 1: basic Chinese chat
Invoke-Chat 'deepseek-v3.2' '用一句话介绍你自己。' $null

# Test 2: another model, reasoning-style
Invoke-Chat 'kimi-k2.5' '3个苹果加5个橘子共有几个水果？只回答数字。' $null

# Test 3: streaming mode (SSE)
Write-Output ""
Write-Output '=== Streaming test: glm-5 ==='
$sbody = @{
    model = 'glm-5'
    messages = @( @{ role = 'user'; content = '请用一句话说明什么是神经网络。' } )
    max_tokens = 80
    stream = $true
} | ConvertTo-Json -Depth 6
$sw2 = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $req = [System.Net.HttpWebRequest]::Create("$baseUrl/chat/completions")
    $req.Method = 'POST'
    $req.ContentType = 'application/json'
    $req.Headers.Add('Authorization', "Bearer $key")
    $req.Timeout = 120000
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($sbody)
    $req.ContentLength = $bytes.Length
    $rs = $req.GetRequestStream(); $rs.Write($bytes, 0, $bytes.Length); $rs.Close()
    $resp = $req.GetResponse()
    $reader = New-Object System.IO.StreamReader($resp.GetResponseStream(), [System.Text.Encoding]::UTF8)
    $chunks = 0; $text = ''
    while (-not $reader.EndOfStream) {
        $line = $reader.ReadLine()
        if ($line.StartsWith('data: ')) {
            $data = $line.Substring(6)
            if ($data -eq '[DONE]') { break }
            $chunks++
            try {
                $j = $data | ConvertFrom-Json
                if ($j.choices[0].delta.content) { $text += $j.choices[0].delta.content }
            } catch {}
        }
    }
    $sw2.Stop()
    $resp.Close()
    Write-Output ("STREAM OK, chunks: " + $chunks + ', latency: ' + $sw2.ElapsedMilliseconds + ' ms')
    Write-Output ('reply       : ' + ($text -replace '\s+', ' '))
} catch {
    Write-Output ('STREAM ERROR: ' + $_.Exception.Message)
}

# Test 4: a qwen model
Invoke-Chat 'qwen3.7-plus' '回答：中国的首都是哪里？只回答城市名。' $null
