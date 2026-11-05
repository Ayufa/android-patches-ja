<p align="center">
  <a href="https://morphe.software/add-source?github=Ayufa/android-patches-ja">
    <img src="assets/add-to-morphe.svg" alt="Add to Morphe" height="48">
  </a>
</p>

# android-patches-ja（Android Patches JA）

X（旧Twitter）と Twitch の [Morphe](https://morphe.software/) パッチを **1つのパッチバンドル（`.mpp`）にまとめた、非公式の日本語化バンドル** です。

もとは別々に公開していた2つの日本語化プロジェクトを統合したものです。

| 対象アプリ | パッチの出どころ | 日本語化の方式 |
| --- | --- | --- |
| X（`com.twitter.android`） | [crimera/piko](https://github.com/crimera/piko) の `x-lite` ブランチ（NewX） | Piko設定UIの文字列リソースをオーバーレイで差し替え |
| Twitch（`tv.twitch.android.app`） | [ryykitty/twitch-patched](https://github.com/ryykitty/twitch-patched) | ソース内の表示文字列を直接翻訳したコピーを同梱 |

パッチ本体の機能は各本家そのままです。本家へプルリクエストや Issue などの書き込みは一切しません（取り込みは読み取り専用の一方向のみ。詳しくは [docs/UPSTREAM.md](docs/UPSTREAM.md)）。

## 収録パッチ

- **X（NewX）**: 広告除去、ブランディング復元、ダウンロード解放、タイムライン／プロフィールのカスタマイズなど、本家 x-lite の全パッチ（リリース時点の件数は Releases の `patches-list.json` を参照）。対応 X バージョンは本家 x-lite の指定どおりです。
- **Twitch**: BTTV、FFZ、7TVのエモート／お気に入りエモート／配信を再読み込み／削除されたメッセージを表示／UI設定／広告ブロック（配信中・クライアント要求・フィード）／Turboプロモーションとサブスク割引バナーの非表示／ボーナスチャンネルポイント自動受け取り／再生の診断／Twitch APKを検査、ほか全13パッチ。対応 Twitch は 31.8.0（安定版）と 31.9.0_BETA（実験的対応）です。

Morphe Patcher 2.0.0 以上が必要です。再署名したアプリでは Google Play の課金は使えません。

## 使い方

1. 上のボタンから Morphe にこのリポジトリをパッチソースとして追加します。
2. 対応バージョンの X または Twitch 公式APKを選び、使いたいパッチを選択して適用・インストールします。

[Releases](https://github.com/Ayufa/android-patches-ja/releases) に `.mpp` パッチバンドル（`patches-<バージョン>.mpp`）と `patches-list.json`（収録パッチ一覧）が含まれます。端末／アプリの言語が日本語の場合に、日本語化した部分が日本語で表示されます。

## 仕組み（ビルド時に1つへ統合）

ビルド（`build_combined.py`、GitHub Actions で実行）は次の流れです。

1. 本家 `crimera/piko` の `x-lite` ブランチの**最新ソースを読み取り専用でクローン**し、NewX 以外のパッチ（Instagram／旧Twitter向け等）を取り除きます。
2. `localization/values-ja-rJP/` の日本語リソース（Piko設定UI 全486件）を重ねます。
3. このリポジトリに保持する Twitch 側の翻訳済みソース（`sources/twitch/`）を、パッチ定義・拡張機能・リソースごとビルドツリーへ注入します。
4. バンドル情報（名前・説明・配布元）をこのプロジェクトのものに書き換え、バージョンを設定して、1つの `.mpp` としてビルドします。

ビルド時の小さな適応（プラグイン世代差の吸収など）の内容は [docs/UPSTREAM.md](docs/UPSTREAM.md) に明記しています。

## 翻訳の範囲

- ✅ Piko設定UI（`values/newx/strings.xml` 全486件）
- ✅ Twitch のパッチ名・説明（全13パッチ＋対応バージョンの説明）、パッチ設定画面のUI文字列、React Native 側の表示文字列
- ⬜ X 側のパッチ名・説明（パッチ定義に埋め込まれているため、本家どおり英語のまま）
- ⬜ 拡張機能コード内に直書きされた一部のトースト文字列（英語のまま）
- 英語のままにするもの: 設定キーなどの内部識別子、ブランド名・プロバイダー名、内部エラーやログの文字列

詳しくは [docs/LOCALIZATION.md](docs/LOCALIZATION.md) を参照してください。

## バージョン方針

このバンドルは **独自のセマンティックバージョニング**（タグ `vX.Y.Z`）で管理し、上流（Piko／twitch-patched）のバージョンとは連動しません。初回は v1.0.0 です。上流の更新を取り込んだら内容に応じてバージョンを上げてリリースします。手順と方針は [docs/UPSTREAM.md](docs/UPSTREAM.md) にあります。

## 本家への配慮

- 本家リポジトリ（crimera/piko、crimera/piko-newx、ryykitty/twitch-patched）への書き込みは一切しません。本家は読み取り専用（fetch／clone のみ）で参照します。
- クレジットとライセンスは本家に従います（GPL-3.0。本家の NOTICE にある Morphe の名称制限もそのまま保持しています）。

## ライセンス

[GPL-3.0](LICENSE)。本家および上流プロジェクトの帰属表示は [NOTICE](NOTICE) と `sources/twitch/` 内の各ファイルに保持しています。このプロジェクトは X、Twitch、Morphe の各プロジェクトとは無関係です。

# Credits

- [crimera](https://github.com/crimera) - Piko / piko-newx 本家
- [ryykitty](https://github.com/ryykitty) - twitch-patched 本家
- [morphe](https://github.com/MorpheApp) - patcher
- [revanced](https://github.com/ReVanced) - previous patcher
