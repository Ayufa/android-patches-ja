#!/usr/bin/env python3
"""Compose the Japanese release notes from build metadata + summary."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    metadata = json.loads(Path(args.metadata).read_text(encoding="utf-8"))
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))

    version = metadata["version"]
    x_versions = "、".join(metadata.get("x_supported_versions", []))
    one_patch = metadata.get("one_patch_per_app") or {}
    x_info = one_patch.get("x") or {}
    twitch_info = one_patch.get("twitch") or {}
    lines = [
        f"X (NewX) パッチと Twitch パッチを1つの `.mpp` にまとめた"
        f"日本語化バンドル `patches-{version}.mpp` をリリースします。",
        "",
        "## 収録パッチ（アプリごとに1つ）",
        "",
        "v1.1.0 から、Morphe のパッチ一覧には機能ごとの細かいパッチではなく、"
        "アプリ単位の統合パッチだけが表示されます。"
        "個別機能のオン・オフは、適用後のアプリ内設定画面"
        "（X は NewX 設定、Twitch は「パッチ設定」）で行います。",
        "",
        f"- X: 「X（NewX）日本語化パッチ」"
        f"（NewX の機能パッチ {x_info.get('included')} 件を内包。"
        f"対応 X バージョン: {x_versions}）",
        f"- X（マウント用）: 「X（NewX）日本語化パッチ（マウント用）」"
        f"（マウントインストールで使える機能パッチ {x_info.get('mount_included')} 件のみ。"
        "マウントでは設定画面など標準インストールが必要な機能が使えないため、"
        "X のみマウント用が別にあります。通常のインストールでは使いません）",
        f"- Twitch: 「Twitch 日本語化パッチ」1件"
        f"（Twitch の機能パッチ {twitch_info.get('included')} 件を内包。"
        "対応 Twitch バージョン: 31.8.0 安定版 / 31.9.0_BETA 実験的対応）",
        "",
        "### 統合に含まれない機能（v1.0.0 では任意選択だったもの）",
        "",
        "次の4機能は、アプリ内設定で無効化できず、全員へ一律適用すると"
        "アプリの見た目や動作が変わってしまうため、統合パッチには含めていません"
        "（コード自体はバンドル内に残りますが実行されません）。",
        "",
        "- NewX: Clone（パッケージ名／アプリ名の変更）",
        "- NewX: Restore Twitter branding（旧 Twitter ブランディングへの置き換え）",
        "- NewX: Log HLS audio renditions（診断ログ。オフにする設定なし）",
        "- Twitch: 再生の診断（再生トレース。オフにする設定なし）",
        "",
        "逆に、従来は任意選択だった NewX の「Hide post dividers」"
        "「Browse tweet object」「Server error logging」と "
        "Twitch の「Twitch APKを検査」は、設定で切り替えできる"
        "（またはアプリを変更しない）ため統合パッチに含めました。",
        "",
        "## 日本語化",
        "",
        f"- Piko 設定 UI の日本語訳 {summary.get('ja_overlay_strings')} 件"
        "（リソースオーバーレイ）",
        "- Twitch 側はパッチ設定 UI などをソース直接翻訳",
        "",
        "## ビルド情報",
        "",
        f"- Piko (crimera/piko x-lite): {metadata.get('piko_commit')}",
        f"- Twitch (ryykitty/twitch-patched) ベース: "
        f"v{metadata.get('twitch_base_version')}",
        f"- Patcher-Version: {summary.get('manifest', {}).get('Patcher-Version')}",
        "",
        "Morphe への追加: https://morphe.software/add-source?github=Ayufa/android-patches-ja",
        "",
    ]
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"release notes written: {args.out}")


if __name__ == "__main__":
    main()
