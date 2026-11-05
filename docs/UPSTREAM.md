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
- 日本語化はリソースのオーバーレイのみです。`localization/values-ja-rJP/newx/strings.xml`（Piko 設定 UI 全486件）を、クローンしたツリーの `addresources/values-ja-rJP/` へコピーします。保持する形ではパッチ本体のコードに手を入れません（ビルド時の使い捨てツリー内だけで行う「アプリごとに1パッチ」化の宣言書き換えを除く。後述）。
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

## アプリごとに1パッチ（v1.1.0〜、マウント用のみ例外あり）

v1.1.0 から、Morphe のパッチ一覧には機能ごとのパッチではなく、アプリ単位の統合パッチ（傘パッチ）だけを表示します（Twitch は「Twitch 日本語化パッチ」1件、X は標準インストール用「X（NewX）日本語化パッチ」とマウント用「X（NewX）日本語化パッチ（マウント用）」の2件。理由は後述）。個別機能のオン・オフは、適用後のアプリ内設定画面（NewX 設定／Twitch「パッチ設定」）で行います。仕組みは次のとおりです。

- Morphe の PatchLoader は、名前（`name`）を持つパッチだけを一覧に載せます。名前の無いパッチは一覧に出ませんが、他のパッチから依存（`dependsOn`）されれば通常どおり実行されます（morphe-patcher 2.0.0 の `Patch` の KDoc と `PatchLoader` の実装で確認）。
- そこで、名前付きの「傘パッチ」を用意し（`umbrella/` に保持）、その `dependsOn` に各アプリの機能パッチを並べます。
- ビルド時（使い捨てツリー内のみ）に、全機能パッチの宣言から `name` / `description` 引数を取り除き、依存専用パッチに変えます（`build_combined.py` の `apply_one_patch_per_app`）。保持しているソース（`sources/twitch/` 等）は変更しません。
- 傘パッチの `dependsOn` 一覧が、そのまま「含める機能パッチ」の台帳です。ビルドは、本家側で見つかった名前付きパッチの集合が「傘パッチの一覧＋除外リスト（後述）」と一致しないと失敗します。本家がパッチを追加・削除・改名したら、日次同期は自動でやり過ごさず、次の判断をしてから傘パッチか除外リストを更新してください。
  - 標準で有効なパッチ、またはアプリ内設定で切り替えできる任意パッチ → 傘パッチの `dependsOn` に追加する。
  - 任意パッチ（本家で `default = false`）で、アプリ内設定で無効化できず、一律適用するとアプリの見た目・動作が変わるもの → `build_combined.py` の `COMBINED_EXCLUDED_PATCHES` に理由付きで追加する。

### X にだけマウント用傘パッチがある理由（v1.1.0 の不具合と v1.1.1 の修正）

- マウントインストール（root で本家アプリに被せる方式）では、設定画面・追加コンポーネント・パッケージ変更を伴うパッチは使えません。本家 NewX のほぼ全機能パッチは設定まわりの都合でマウント不可を自ら宣言しており（`unsupportedOnMount`）、マウントで使えるのは「Unlock downloads」と「Unlock color customization」の2件だけです（v1.0.0 時点）。
- 本家の検証テスト `SettingsAggregateValidationTest`（piko のテストスイート）は「選択可能なパッチの中に、マウントで使えるものと標準インストール専用のものが両方あること」を要求します。X を標準用傘パッチ1件だけにするとこのテストが落ち、`generatePatchesList`（テストに依存）が止まって `patches-list.json` が生成されません。v1.1.0 はこのため patches-list.json 欠落のまま公開されてしまいました（ビルド内ではベストエフォート扱いで握り潰されていた）。v1.1.1 でマウント用傘パッチ（上記2件のみを内包）を追加して解消し、CI の検証ステップでも patches-list.json が無ければ失敗させるようにしました。
- マウント用傘パッチのメンバーは「`unsupportedOnMount` を宣言せず、設定コントリビューション DSL を使わず、依存先にも標準インストール専用パッチが無い」機能パッチです。`build_combined.py` がこの規則で計算した集合と傘の `dependsOn` が一致しないとビルドが失敗します。本家が新しいマウント対応パッチを増やしたら、計算結果に合わせてマウント用傘も更新してください。
- 標準用傘パッチは、本家の機能パッチと同様に `unsupportedOnMount(default = true)` を宣言し、マウントでは選択不可にしています。通常インストールで両方の傘が選択されても、共通の依存パッチは1回だけ実行されるため問題ありません。
- 除外中（傘パッチに含めない）のは次の4件です。コード自体はバンドル内に残りますが、実行されません。
  - `clonePatch`（NewX: Clone）: パッケージ名／アプリ名をパッチのオプションで変更する。一律適用すると全員のアプリが複製版になり、一覧に出ないパッチのオプションは Morphe Manager で設定できない。
  - `bringBackTwitterPatch`（NewX: Restore Twitter branding）: アプリ名・アイコン・スプラッシュのリソースを旧 Twitter 仕様に置き換える。リソースは実行時に切り替えできない。
  - `newXAudioRenditionDiagnosticsPatch`（NewX: Log HLS audio renditions）: 診断ログのフック。オフにする設定が無い。
  - `inspectPlaybackPatch`（Twitch: 再生の診断）: 再生 HTTP クライアントへのラップとトレースフック。オフにする設定が無い。
- 逆に、任意パッチでも次は傘パッチに含めています（アプリ内設定で切り替え可能、またはアプリ自体を変更しないため）。
  - NewX: Browse tweet object（設定トグルあり。初期値オン、設定でオフ可）、Hide post dividers（設定トグルあり。初期値オフ）、Server error logging（設定トグルあり。初期値オン、設定でオフ可）。
  - Twitch: Twitch APKを検査（パッチ適用時の検証とログのみで、アプリを変更しない）。

## ビルド時の適応（使い捨てツリー内のみ）

統合ビルドでは、本家 Piko のビルドツリー（Morphe Gradle プラグイン 1.3.4 系）へ Twitch 側を注入するため、次の小さな適応をビルドのたびに使い捨てツリー内で行います。保持しているソース自体は変更しません。

- `extensions/twitch/build.gradle.kts` から、プラグイン 2.0.0 系の `extension { name = ... }` ブロックを取り除く（1.3.4 系はモジュールパスから同じ名前 `extensions/twitch.mpe` を導出するため）。
- `extensions/proguard-rules.pro` に `-keep class dev.twitchpatches.**` を追加する（本家の keep 対象は `app.morphe.**` 等のみで、Twitch 拡張のクラス名参照を守るため）。
- `patches/build.gradle.kts` の `about` ブロック（バンドル名・説明・配布元・作者・ライセンス）を、このプロジェクトの値に書き換える。
- バージョンは `gradle.properties` の `version` を、このリポジトリのリリースバージョンに設定する。
- アプリごとに1パッチ化: 全機能パッチ宣言の `name` / `description` 引数の除去と、傘パッチ2ファイルの注入（上記「アプリごとに1パッチ」参照）。

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
