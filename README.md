# MilkyDawn Preset Dev

LLM (Claude) を使って [MilkyDawn](https://github.com/TANOSHIT) オーディオビジュアライザーのビジュアルプリセットを作成するための MCP サーバー。

Claude Code や Claude Desktop から自然言語でプリセットを生成し、実行中のビジュアライザーでリアルタイムプレビューできます。

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install mcp
```

### 2. MilkyDawn のパスを設定

デフォルトでは同じ親ディレクトリの `MilkyDawn/` フォルダを参照します。
別の場所にある場合は `.mcp.json` で環境変数 `MILKYDAWN_DIR` を設定:

```json
{
  "mcpServers": {
    "milkydawn": {
      "type": "stdio",
      "command": "python",
      "args": ["mcp_server.py"],
      "env": {
        "MILKYDAWN_DIR": "C:\\path\\to\\MilkyDawn"
      }
    }
  }
}
```

### 3. Claude Code で使う

このリポジトリをプロジェクトとして開くだけで、`.mcp.json` が自動認識されます。

## 使い方

MilkyDawn ビジュアライザーを起動した状態で、Claude Code に指示するだけ:

```
「オーロラが揺れるプリセットを作って」
「FFTスペクトラムを円形に表示するモードを作って」
「既存の Spectrum プリセットをベースに、色が虹色に変化するバージョンを作って」
```

Claude は自動的に:
1. `get_api_reference` で API 仕様を確認
2. `write_preset` でプリセットを作成
3. `reload_visualizer` でビジュアライザーにリロード指示
4. `select_preset` で作成したプリセットをプレビュー

## MCP ツール一覧

| ツール | 説明 |
|---|---|
| `list_presets` | プリセット一覧を取得 |
| `read_preset` | 既存プリセットのソースコードを読む |
| `write_preset` | プリセットを作成/上書き |
| `delete_preset` | プリセットを削除 |
| `reload_visualizer` | ビジュアライザーにモード再読み込みを指示 |
| `select_preset` | 指定プリセットに切り替え |
| `get_api_reference` | EYESY プリセット API リファレンスを取得 |

## プリセットの書き方

プリセットは `presets/<NAME>/main.py` に `setup()` と `draw()` の2関数を定義するだけ:

```python
import pygame
import math

def setup(screen, etc):
    global phase
    phase = 0.0

def draw(screen, etc):
    global phase
    etc.color_picker_bg(etc.knob5)  # 画面クリア（必須）
    color = etc.color_picker(etc.knob1)

    cx, cy = etc.xres // 2, etc.yres // 2
    radius = int(etc.knob2 * min(cx, cy))

    for i in range(100):
        amp = etc.audio_normalized[i] * etc.knob4
        angle = phase + i * math.pi * 2 / 100
        r = radius + int(amp * 100)
        x = cx + int(r * math.cos(angle))
        y = cy + int(r * math.sin(angle))
        pygame.draw.circle(screen, color, (x, y), 3)

    phase += 0.02 + etc.rms * 0.1
```

詳しい API 仕様は `get_api_reference` ツールで確認できます。

## License

MIT
