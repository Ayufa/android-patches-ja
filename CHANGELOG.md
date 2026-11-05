# 変更履歴

このプロジェクトのバージョンは、バンドル全体に対する独立したセマンティックバージョニング（`vX.Y.Z`）で管理します。上流（crimera/piko、ryykitty/twitch-patched）のバージョンとは連動しません。方針は [docs/UPSTREAM.md](docs/UPSTREAM.md) を参照してください。

## [1.0.0] - 2026-11-05

- 初回リリース。X（NewX）パッチと Twitch パッチを1つの `.mpp` バンドルに統合（従来の Ayufa/piko-newx-ja と Ayufa/twitch-patched-ja を統合）。
- X 側: ビルド時に crimera/piko の `x-lite` 最新ソースを読み取り専用でクローンし、Piko 設定 UI の日本語訳（全486件）をオーバーレイして収録。
- Twitch 側: ryykitty/twitch-patched v1.5.0 ベースの日本語化ソース（パッチ名・説明とパッチ設定 UI を翻訳した全13パッチ）を `sources/twitch/` に保持し、ビルド時に注入して収録。
