param([int]$Count = 8, [string]$Image = 'D:\rob-memory\outputs\agentvln_hunter_20261108_vlm_deploy\straight_frame\rgb.png', [switch]$NoCache)
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($Image))
$body = @{
  model = 'qwen-vl'
  max_tokens = 16
  temperature = 0
  cache_prompt = (-not $NoCache)
  messages = @(@{
    role = 'user'
    content = @(
      @{ type = 'text'; text = '这张图里有几个蓝色箱子？只回答数字。' },
      @{ type = 'image_url'; image_url = @{ url = "data:image/png;base64,$b64" } }
    )
  })
} | ConvertTo-Json -Depth 8 -Compress
$lat = @()
for ($i = 1; $i -le $Count; $i++) {
  $sw = [Diagnostics.Stopwatch]::StartNew()
  try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:18081/v1/chat/completions' -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 180
    $sw.Stop()
    $lat += [pscustomobject]@{ i = $i; ms = [int]$sw.ElapsedMilliseconds; answer = ($r.choices[0].message.content -replace '\s+',' ') }
  } catch {
    $sw.Stop()
    $lat += [pscustomobject]@{ i = $i; ms = [int]$sw.ElapsedMilliseconds; answer = ('ERR ' + $_.Exception.Message) }
  }
}
$lat | ConvertTo-Json -Compress
