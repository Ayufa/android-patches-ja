# 日本語化の方針と範囲（android-patches-ja）

両側とも「本家をクローンし、言語だけを日本語にする」方式で、翻訳済みソースのコピーを保持します（X 側: `sources/piko/`、Twitch 側: `sources/twitch/`）。

## X 側（Piko / NewX）: ソース直接翻訳方式

本家 `crimera/piko` の `x-lite` ブランチには、Piko 設定 UI の文字列
`patches/src/main/resources/addresources/values/newx/strings.xml`（486件）の
日本語訳が存在しません（Crowdin の対象にも含まれていません）。
v1.1.x まではこの日本語訳をオーバーレイとして保持していましたが、
v1.2.0 からは Twitch 側と同じくソースのコピーを保持する方式に統一し、
翻訳はすべてコピー（`sources/piko/`）の中で完結します。

翻訳するもの:

- Piko 設定 UI の表示文字列 全486件: `sources/piko/patches/src/main/resources/addresources/values-ja-rJP/newx/strings.xml` に実ファイルとして保持します（本家に無い日本語リソースの追加）。
- Morphe のパッチ一覧に表示される名前・説明: パッチ宣言（Kotlin ソース）の `name` / `description` 全52件を日本語に書き換えています。設定 UI 側に同じ機能の訳がある場合は、そちらに合わせます。
- 未訳のキーは Android のフォールバックで英語表示になります（壊れることはありません）。

翻訳しないもの:

- 拡張機能コード内に直書きされた一部のトースト文字列（英語のまま）。
- パッチのオプション（`stringOption` 等）のラベル・説明（英語のまま）。
- 設定キーなどの内部識別子、ブランド名・プロバイダー名、内部エラーやログの文字列。
- 共有文字列（`values/shared`）は本家に既存の日本語訳を利用します。

### X 側の更新手順（本家に新しい文字列が増えたら）

1. 本家 `values/newx/strings.xml` のキーと、`sources/piko/` の日本語ファイルのキーを比べます（ビルド時に未訳キーは "untranslated string(s)" としてログに出ます）。
2. 増えたキーを翻訳して日本語ファイルに追加します。**プレースホルダ（`%1$s`、`%2$d`、`%%` など）は英語版と完全一致**させてください。
3. 本家がパッチ宣言の名前・説明を変えたり、新しいパッチを足したりしたら、その名前・説明も日本語に訳してコピーへ反映し、`scripts/verify_bundle.py` の `EXPECTED_PATCHES` を更新します。

### X 側の用語の統一

- post → ポスト、timeline → タイムライン、For You → おすすめ、Following → フォロー中
- Repost → リポスト、Like → いいね、Bookmark → ブックマーク、Share → 共有
- Piko / NewX / Grok などの固有名詞は英語のまま
- `translatable="false"` の文字列は英語版をそのまま保持

## Twitch 側: ソース直接翻訳方式

本家 `ryykitty/twitch-patched` のパッチには Android の文字列リソース
（strings.xml）の仕組みが無く、表示文字列はすべてソースコード内に直接
書かれています。そのためオーバーレイはできず、**コピー側リポジトリ
（`sources/twitch/`）で文字列を直接翻訳する** 方式を取ります。
本家の更新を取り込むたびに、翻訳行で競合が起きる可能性があります
（対処は `docs/UPSTREAM.md`）。

翻訳するもの（ユーザーに見える表示文字列のみ）:

- パッチ設定画面（拡張機能の Java コード）: 設定項目名と説明、セクション名10件、検索まわり、ツールバー、お気に入りの追加・削除ラベル、削除済みメッセージのラベル「（削除済み）」など。
- Morphe のパッチ選択画面（パッチ定義の Kotlin コード）: 全13パッチの名前と説明、対応バージョンの説明、Twitch 本体の設定一覧に出る入口名「パッチ設定」。
- React Native 側の表示文字列: お気に入り、再読み込みのトーストとラベル、エモート種別ラベル、UI 設定への入口。

翻訳しないもの:

- 設定キー、SharedPreferences のキー、URL スキームなどの内部識別子（互換性のため絶対に変えない）
- ブランド名・サービス名・プロバイダー名: Twitch、BTTV、7TV、FrankerFaceZ、Twitch Turbo など（ハイプトレイン等、カタカナ表記が自然なものは訳す）
- 例外メッセージ、ログ、内部エラー文字列（診断用で、コード側で参照される場合もあるため）
- テストコード内のダミー文字列

翻訳済み文字列を検証するテスト（`UiFeatureRegistryTest`、`SettingsSearchTest`、`scripts/tests/` の React Native 系）は、期待値を日本語に合わせて更新しています。対象ファイルの詳細な対応表は `sources/twitch/docs/LOCALIZATION.md` に保持しています。

## 表記の方針

- 設定名は簡潔に（Twitch 本家の「簡潔なラベル」方針に合わせる）。
- 説明文は元の文末ピリオドに合わせて「。」で終える。
- 件数表示は「{全体}件中{一部}件を非表示中です。」のように、日本語の語順に入れ替える（コード側の文字列連結の順序も合わせて変更している）。
