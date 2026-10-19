$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12をインストールするか，既存の.venvを利用してください．' }
& "$PSScriptRoot/.venv/Scripts/python.exe" -m pip install -r "$PSScriptRoot/requirements.txt"
if ($LASTEXITCODE -ne 0) { throw '依存ライブラリのインストールに失敗しました．' }
