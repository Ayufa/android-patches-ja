# 日本語リソース（localization）

本家 crimera/piko の `x-lite` ブランチには、Piko設定UIの文字列
`patches/src/main/resources/addresources/values/newx/strings.xml`（486件）の
日本語訳が存在しません（Crowdin の対象にも含まれていません）。
このディレクトリはその日本語訳を保持し、ビルド時に `build_combined.py` の
`apply_japanese_localization()` が、クローンした本家ツリーの
`addresources/values-ja-rJP/newx/strings.xml` として差し込みます。

## ファイル

- `values-ja-rJP/newx/strings.xml` — Piko設定UI 全486文字列の日本語訳

## 更新手順（本家に新しい文字列が増えたら）

1. 本家 `values/newx/strings.xml` のキーと、このファイルのキーを比べる
   （ビルド時に未訳キーは "untranslated string(s)" としてログに出ます）。
2. 増えたキーを翻訳してこのファイルに追加する。**プレースホルダ
   （`%1$s`、`%2$d`、`%%` など）は英語版と完全一致**させること。
3. 訳が無いキーは Android のフォールバックで英語表示になるので、
   壊れることはありません。

## 用語の統一

- post → ポスト、timeline → タイムライン、For You → おすすめ、Following → フォロー中
- Repost → リポスト、Like → いいね、Bookmark → ブックマーク、Share → 共有
- Piko / NewX / Grok などの固有名詞は英語のまま
- `translatable="false"` の文字列は英語版をそのまま保持
