# 日本語化の方針と範囲（android-patches-ja）

このリポジトリの日本語化は、対象ごとに方式が異なります。

## X 側（Piko / NewX）: リソースオーバーレイ方式

本家 `crimera/piko` の `x-lite` ブランチには、Piko 設定 UI の文字列
`patches/src/main/resources/addresources/values/newx/strings.xml`（486件）の
日本語訳が存在しません（Crowdin の対象にも含まれていません）。
このリポジトリではその日本語訳を `localization/values-ja-rJP/newx/strings.xml`
に保持し、ビルド時にクローンした本家ツリーの
`addresources/values-ja-rJP/newx/strings.xml` として差し込みます
（`build_combined.py` の `apply_japanese_localization()`）。

- 翻訳するもの: Piko 設定 UI の表示文字列 全486件。
- Morphe のパッチ一覧に表示される名前・説明: v1.1.0 以降は傘パッチ「X（NewX）日本語化パッチ」のみが表示され、その名前と説明は日本語で保持します（`umbrella/NewXCombinedPatch.kt`）。機能パッチ個別の名前・説明はビルド時に取り除かれるため表示されません（本家どおり英語のまま保持、という従来方針に変更はありません）。
- 翻訳しないもの: 拡張機能コード内に直書きされた一部のトースト文字列（英語のまま）。共有文字列（`values/shared`）は本家に既存の日本語訳を利用します。
- 未訳のキーは Android のフォールバックで英語表示になります（壊れることはありません）。更新手順と用語の統一は `localization/README.md` にあります。

## Twitch 側: ソース直接翻訳方式

本家 `ryykitty/twitch-patched` のパッチには Android の文字列リソース
（strings.xml）の仕組みが無く、表示文字列はすべてソースコード内に直接
書かれています。そのためオーバーレイはできず、**コピー側リポジトリ
（`sources/twitch/`）で文字列を直接翻訳する** 方式を取ります。
本家の更新を取り込むたびに、翻訳行で競合が起きる可能性があります
（対処は `docs/UPSTREAM.md`）。

翻訳するもの（ユーザーに見える表示文字列のみ）:

- パッチ設定画面（拡張機能の Java コード）: 設定項目名と説明、セクション名10件、検索まわり、ツールバー、お気に入りの追加・削除ラベル、削除済みメッセージのラベル「（削除済み）」など。
- Morphe のパッチ選択画面（パッチ定義の Kotlin コード）: 全13パッチの名前と説明、対応バージョンの説明、Twitch 本体の設定一覧に出る入口名「パッチ設定」。なお v1.1.0 以降、Morphe の一覧に実際に表示されるのは傘パッチ「Twitch 日本語化パッチ」の名前と説明（`umbrella/TwitchCombinedPatch.kt`、日本語で保持）のみで、機能パッチ個別の名前・説明はビルド時に取り除かれるため表示されません。ソース側の翻訳自体は本家への忠実度のため維持します（詳細は `docs/UPSTREAM.md` の「アプリごとに1パッチ」）。
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
- X 側の用語統一（post → ポスト、timeline → タイムライン等）は `localization/README.md` にあります。
