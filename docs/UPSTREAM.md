# 本家への追従方法（android-patches-ja）

このリポジトリは、次の2つの本家プロジェクトのパッチを1つの `.mpp` バンドルにまとめた日本語化プロジェクトです。

- X 側: [crimera/piko](https://github.com/crimera/piko) の `x-lite` ブランチ（NewX）。ビルダーの系譜は [crimera/piko-newx](https://github.com/crimera/piko-newx)。
- Twitch 側: [ryykitty/twitch-patched](https://github.com/ryykitty/twitch-patched)（ベースは v1.5.0）。

両側とも「本家をクローンし、言語だけを日本語にする」方式です。翻訳済みソースのコピーをこのリポジトリに保持し、ビルドはそのコピーをそのままビルドするだけです（v1.2.0 で統一。経緯は後述）。本家には迷惑をかけないため、次のルールを絶対とします。

## 絶対ルール

- 本家リポジトリへのプルリクエスト、Issue、コメント、マージなど、書き込みは一切しない。
- 本家の参照は読み取り専用のみ。git リモートとして登録する場合は push URL を `DISABLED-NO-PUSH-TO-UPSTREAM` に設定して誤 push を防ぐ。
- 変更の流れは一方向のみ: 本家 → このリポジトリ。

## 両側共通: 翻訳済みソースのコピーを保持

- 本家のソースツリーをコピーし、表示文字列を日本語化した状態で保持します（X 側は `sources/piko/`、Twitch 側は `sources/twitch/`）。コピー元の本家コミットは各コピーの記録ファイル（X 側: `sources/piko/UPSTREAM_BASE.md`、Twitch 側: `sources/twitch/CHANGELOG.md` の先頭）に残します。
- ビルド（`build_combined.py`）は、X 側のコピー（Piko ツリー）をビルドホストとして使い捨てディレクトリへコピーし、Twitch 側のコピーを注入して1つの `.mpp` をビルドします。ビルド時に本家をクローンすることはありません。また、パッチの追加・統合・改名などの「仕掛け」は一切しません。本家のパッチがそのまま、機能ごとに Morphe の一覧へ出ます。
- 本家のバージョンタグはこのリポジトリには取り込みません。このリポジトリのバージョニングは独立です（後述）。

## X 側（Piko / NewX）: sources/piko/

- 本家 `crimera/piko` の `x-lite` ブランチのツリーから、NewX 以外（Instagram／旧 Twitter 向けパッチと拡張）を取り除いたコピーを保持します（取り除いた範囲は `sources/piko/UPSTREAM_BASE.md` に記載）。
- 日本語化はコピーの中で完結します。
  - Piko 設定 UI の文字列: 本家には日本語リソースが無いため、`sources/piko/patches/src/main/resources/addresources/values-ja-rJP/newx/strings.xml`（全486件）を実ファイルとして保持します。
  - Morphe の一覧に表示されるパッチ名・説明: パッチ宣言（Kotlin ソース）の中の `name` / `description` を日本語に書き換えています（全52件）。方針は `docs/LOCALIZATION.md`。
- 取り込み手順（本家 `x-lite` のみが対象）:
  1. 本家を読み取り専用で取得する（浅いクローン、または push URL を無効化したリモートからの fetch）。
  2. 本家の変更を `sources/piko/` へ反映する（差分適用／手作業マージ）。取り除いた範囲（Instagram／旧 Twitter 向け）は引き続き含めません。
  3. 日本語化はソース内の文字列を直接書き換えているため、本家が同じ行を変更すると競合します。競合したら本家の新しい英語文字列を確認し、日本語訳を付け直して解消します。翻訳行以外で解釈に迷う競合が出たら、取り込みを中止してユーザーに報告します。
  4. 本家に新しい表示文字列が増えたら翻訳して追加します（設定 UI の文字列は英語版 `values/newx/strings.xml` のキーと比較。パッチ名・説明は宣言を確認）。未訳のキーはビルドログに表示され、実行時は英語にフォールバックします。
  5. 本家がパッチを追加・削除・改名したら、`scripts/verify_bundle.py` の `EXPECTED_PATCHES`（アプリごとの日本語名の一覧）も合わせて更新します。新しいパッチの名前・説明には日本語訳を付けます。
  6. `sources/piko/UPSTREAM_BASE.md` のベースコミットを更新します。コミットは規約型 `i18n` を使います。

## Twitch 側: sources/twitch/

- 本家には文字列リソースの仕組みが無くオーバーレイができないため、`sources/twitch/` に本家のソースツリー（パッチ定義・拡張機能・共有 API・スクリプト・設定）をコピーし、表示文字列を直接翻訳した状態で保持します（方式の詳細は `docs/LOCALIZATION.md` と `sources/twitch/docs/LOCALIZATION.md`）。
- 取り込み手順（本家 `main` のみが対象。本家の `dev` は参照だけにとどめ、こちらには作りません）:
  1. 本家を読み取り専用で取得する（例: `git remote add upstream-twitch https://github.com/ryykitty/twitch-patched.git` とし、push URL は無効化して `git fetch upstream-twitch`）。
  2. 本家の変更を `sources/twitch/` へ反映する（サブツリーへの差分適用／手作業マージ）。
  3. 日本語化はソース内の文字列を直接書き換えているため、本家が同じ行を変更すると競合します。競合したら本家の新しい英語文字列を確認し、日本語訳を付け直して解消します。翻訳行以外で解釈に迷う競合が出たら、取り込みを中止してユーザーに報告します。
  4. 翻訳済み文字列を検証するテスト（`sources/twitch/` 内の `UiFeatureRegistryTest`、`SettingsSearchTest`、`scripts/tests/`）の期待値も、日本語化に合わせて更新します。
  5. 本家がパッチを追加・削除・改名したら、`scripts/verify_bundle.py` の `EXPECTED_PATCHES` も合わせて更新し、新しいパッチの名前・説明には日本語訳を付けます。
  6. 取り込みコミットには規約型 `i18n` を使います。

## v1.1.x の傘パッチ構成について（v1.2.0 で廃止）

v1.1.0〜v1.1.1 では、Morphe の一覧を「アプリごとに1パッチ」にするために、ビルド時に全機能パッチの名前を取り除いて依存専用化し、傘パッチ（旧 `umbrella/`）から一括で引く構成にしていました。しかしこの構成では、機能パッチが1つでも失敗すると傘全体が失敗し、残りの機能もろとも適用されませんでした。実際に、X 12.39.0-prod.01 で本家 CanonicalUrls（正規URLを開く機能）が本家側の未検証により失敗し、NewX の全49機能が適用できない事態になりました（本家は 12.39.0-prod.01 対応を宣言しましたが、その変更は対応バージョン文字列の追加のみで、この機能の厳密な照合は 12.39.0-alpha.03 まででしか検証されていません）。

このため 2026-11-05 に本人が「クローン＋翻訳のみに戻す」と判断し、v1.2.0 で現在の方式（本家のパッチをそのまま個別収録）に戻しました。個別収録では、壊れたパッチはそのパッチだけが失敗し、Morphe で個別に外すこともできます。副作用として、v1.1.x の傘に含めていなかった4機能（NewX: クローン／Twitterブランディングに戻す／HLS音声レンディションのログ、Twitch: 再生の診断）は、通常の任意選択パッチ（本家の初期状態のまま）として戻っています。

なお CanonicalUrls の 12.39.0-prod.01 非互換そのものは本家側の問題で、構成を戻しても直りません。本家 `x-lite` に修正が入れば、日次同期が取り込んで新しい版を出します。

## 既知の問題: X 12.39.0-prod.01 と本家の厳密照合（requireExactlyOne）

2026-11-05 の実機確認（Galaxy SCG37 / Android 17、Morphe Manager 2.4.0、v1.2.0 バンドル）で、X 12.39.0-prod.01 に対して次の2件が失敗しました。どちらも本家 NewX の resolver が `requireExactlyOne`（候補がちょうど1件でなければ PatchException で fail-closed する、本家 `piko-patches-library` の共通ヘルパー）で落ちる同型の失敗です。本家は 12.39.0-prod.01 対応を宣言していますが、その変更は対応バージョン文字列の追加が中心で、厳密なバイトコード形状の照合は 12.38.0-prod.01 / 12.39.0-alpha.03 でしか検証されていません。prod ビルドの R8 差分で候補数が 0 や 2 になると落ちます。

- 「正規URLを直接開く」（CanonicalUrlsPatch）: `URL picker capability shape, found 0`（v1.1.1 の傘構成で観測）。
- 「メディアタブのデフォルト」（DefaultMediaTabPatch）: `combined profile timeline sub-tab seed, found 2`（v1.2.0 で観測、DefaultMediaTabPatch.kt:184）。組み合わせプロフィール画面のコンストラクタ内にある `MutableStateFlow(初期サブタブ)` の種呼び出しを一意に特定する照合で、prod ビルドでは候補が2件あります。このパッチには「写真タブのギャラリー表示」が依存するため、同パッチも一緒に適用できません。

日本語化レイヤーは無関係です。DefaultMediaTabPatch.kt の本家 340dd02 との差分は name / description の2行（145〜146行目）のみで、失敗箇所を含むロジックは本家と完全一致しています（2026-11-05 に diff で確認）。

リスク範囲: 一覧52件中35件が自ファイル内で `requireExactlyOne` / `requireAtMostOne` を呼び、さらに6件が共有 resolver（PostModels のモデル解決、TimelineFilter 系など）経由で同ヘルパーに依存します。ただし実機ラン（v1.2.0、デフォルト有効46件を適用）で失敗したのは上記「メディアタブのデフォルト」のみで、他の照合は prod ビルドでも一意に解決できています。過度に恐れる必要はありませんが、新しい X のバージョンでは同型の失敗が別のパッチで出る可能性があります。

本家の修正状況: 2026-11-05 時点で本家 `x-lite` の HEAD はベースと同じ 340dd02 のままで、修正コミットはありません。修正が入れば日次同期が自動で取り込みます。

12.39.0-prod.01 で全件グリーンにしたい場合は、「メディアタブのデフォルト」と「写真タブのギャラリー表示」（依存のため）を Morphe で外して適用してください。「正規URLを直接開く」は v1.2.0 の実機ランでは失敗として報告されませんでした（v1.1.1 の傘＝実行順序が異なる構成でのみ失敗を観測）。

## ビルド時の適応（使い捨てツリー内のみ）

統合ビルドでは、本家 Piko のビルドツリー（Morphe Gradle プラグイン 1.3.4 系）へ Twitch 側を注入するため、次の小さな適応をビルドのたびに使い捨てツリー内で行います。保持しているソース自体は変更しません。

- ビルドツリーへコピーした X 側の `patches-list.json`（本家自身の古いもの）を削除する（このビルドで生成した一覧だけを成果物にするため）。
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
  2. CI が `build_combined.py` で単一バンドルをビルドし、`scripts/verify_bundle.py` で両パッチの収録と日本語化を検証してから、GitHub Release に `patches-<X.Y.Z>.mpp` と `patches-list.json` を公開します。`patches-list.json` が生成されなかった場合は CI が失敗し、リリースされません。
  3. CI が `patches-bundle.json`（最新リリースのメタデータ）を `main` にコミットします。
- リリースノートには今回の変更内容（特に不具合修正と、上流取り込み・翻訳の追加分）を記載します。

## 本家が公式に日本語対応した場合

- どちらかの本家が対象部分の公式な日本語訳を提供し始めたら、その側の日本語化は役目を終えます。その時点でユーザーに知らせ、その側の追従方法の見直し（コピーの廃止）を検討します。
