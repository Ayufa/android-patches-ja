# 本家への追従方法（android-patches-ja）

このリポジトリは、次の2つの本家プロジェクトのパッチを1つの `.mpp` バンドルにまとめた日本語化プロジェクトです。

- X 側: [crimera/piko](https://github.com/crimera/piko) の `x-lite` ブランチ（NewX）。ビルダーの系譜は [crimera/piko-newx](https://github.com/crimera/piko-newx)。
- Twitch 側: [ryykitty/twitch-patched](https://github.com/ryykitty/twitch-patched)（ベースは v1.5.0）。

どちらも出どころが別で追従の形も違うため、側ごとに方法を分けています。本家には迷惑をかけないため、次のルールを絶対とします。

## 絶対ルール

- 本家リポジトリへのプルリクエスト、Issue、コメント、マージなど、書き込みは一切しない。
- 本家の参照は読み取り専用のみ。git リモートとして登録する場合は push URL を `DISABLED-NO-PUSH-TO-UPSTREAM` に設定して誤 push を防ぐ。ビルド時のクローンも読み取り専用で、使い捨ての作業ツリーに対してのみ行う。
- 変更の流れは一方向のみ: 本家 → このリポジトリ。

## X 側（Piko / NewX）: ビルド時クローン＋オーバーレイ

- パッチ本体のソースはこのリポジトリに保持しません。ビルド（`build_combined.py`）のたびに、本家 `crimera/piko` の `x-lite` ブランチの最新を浅いクローンで取得し、NewX 以外（Instagram／旧 Twitter 向けパッチと拡張）を取り除いてからビルドします。したがって X 側は常に本家の最新に追従します。
- 日本語化はリソースのオーバーレイのみです。`localization/values-ja-rJP/newx/strings.xml`（Piko 設定 UI 全486件）を、クローンしたツリーの `addresources/values-ja-rJP/` へコピーします。パッチ本体のコードには一切手を入れません。
- ビルドスクリプト自体は本家 `crimera/piko-newx` のビルダー（Ayufa/piko-newx-ja で日本語化したもの）が原型です。本家ビルダーに変更があった場合は、差分を確認したうえで `build_combined.py` に取り込みます。
- 本家に新しい文字列が増えたら、ビルドログに未訳キーが表示されます。翻訳を追加する手順は `localization/README.md` にあります。

## Twitch 側: 翻訳済みソースのコピーを保持

- 本家には文字列リソースの仕組みが無くオーバーレイができないため、`sources/twitch/` に本家のソースツリー（パッチ定義・拡張機能・共有 API・スクリプト・設定）をコピーし、表示文字列を直接翻訳した状態で保持します（方式の詳細は `docs/LOCALIZATION.md` と `sources/twitch/docs/LOCALIZATION.md`）。
- 取り込み手順（本家 `main` のみが対象。本家の `dev` は参照だけにとどめ、こちらには作りません）:
  1. 本家を読み取り専用で取得する（例: `git remote add upstream-twitch https://github.com/ryykitty/twitch-patched.git` とし、push URL は無効化して `git fetch upstream-twitch`）。
  2. 本家の変更を `sources/twitch/` へ反映する（サブツリーへの差分適用／手作業マージ）。
  3. 日本語化はソース内の文字列を直接書き換えているため、本家が同じ行を変更すると競合します。競合したら本家の新しい英語文字列を確認し、日本語訳を付け直して解消します。翻訳行以外で解釈に迷う競合が出たら、取り込みを中止してユーザーに報告します。
  4. 翻訳済み文字列を検証するテスト（`sources/twitch/` 内の `UiFeatureRegistryTest`、`SettingsSearchTest`、`scripts/tests/`）の期待値も、日本語化に合わせて更新します。
  5. 取り込みコミットには規約型 `i18n` を使います。
- 本家のバージョンタグはこのリポジトリには取り込みません。このリポジトリのバージョニングは独立です（後述）。`sources/twitch/CHANGELOG.md` の先頭が、取り込み元の本家バージョンを示します。

## ビルド時の適応（使い捨てツリー内のみ）

統合ビルドでは、本家 Piko のビルドツリー（Morphe Gradle プラグイン 1.3.4 系）へ Twitch 側を注入するため、次の小さな適応をビルドのたびに使い捨てツリー内で行います。保持しているソース自体は変更しません。

- `extensions/twitch/build.gradle.kts` から、プラグイン 2.0.0 系の `extension { name = ... }` ブロックを取り除く（1.3.4 系はモジュールパスから同じ名前 `extensions/twitch.mpe` を導出するため）。
- `extensions/proguard-rules.pro` に `-keep class dev.twitchpatches.**` を追加する（本家の keep 対象は `app.morphe.**` 等のみで、Twitch 拡張のクラス名参照を守るため）。
- `patches/build.gradle.kts` の `about` ブロック（バンドル名・説明・配布元・作者・ライセンス）を、このプロジェクトの値に書き換える。
- バージョンは `gradle.properties` の `version` を、このリポジトリのリリースバージョンに設定する。

## リリースとバージョニング

- バージョニングは **このバンドル独自のセマンティックバージョニング**（`vX.Y.Z`）で、上流のバージョンとは連動しません。初回は v1.0.0 です。
  - 上流のどちらかの更新取り込みや翻訳の追加・修正: 内容に応じて patch / minor を上げます。
  - 収録パッチの大きな追加・削除や対応アプリの変更: minor（互換性が壊れる場合は major）を上げます。
- リリース手順:
  1. バージョンを決め、`main` の対象コミットにタグ `vX.Y.Z` を付けて push します（または Actions の Release ワークフローを手動実行し、`publish_release` を有効にします）。
  2. CI が `build_combined.py` で単一バンドルをビルドし、`scripts/verify_bundle.py` で両パッチの収録と日本語化を検証してから、GitHub Release に `patches-<X.Y.Z>.mpp` と `patches-list.json` を公開します。
  3. CI が `patches-bundle.json`（最新リリースのメタデータ）を `main` にコミットします。
- リリースノートには今回の変更内容（特に不具合修正と、上流取り込み・翻訳の追加分）を記載します。

## 本家が公式に日本語対応した場合

- どちらかの本家が対象部分の公式な日本語訳を提供し始めたら、その側の日本語化は役目を終えます。その時点でユーザーに知らせ、その側の追従方法の見直し（オーバーレイ／コピーの廃止）を検討します。
