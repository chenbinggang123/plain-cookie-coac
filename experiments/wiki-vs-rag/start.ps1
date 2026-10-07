$bypass = @($env:NO_PROXY, "api.deepseek.com", "localhost", "127.0.0.1", "::1") |
    Where-Object { $_ } |
    Select-Object -Unique
$env:NO_PROXY = $bypass -join ","

python "$PSScriptRoot\server.py" --port 8765
