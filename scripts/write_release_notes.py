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
    lines = [
        f"X (NewX) パッチと Twitch パッチを1つの `.mpp` にまとめた"
        f"日本語化バンドル `patches-{version}.mpp` をリリースします。",
        "",
        "## 収録パッチ",
        "",
        f"- X (NewX): {summary.get('newx_patch_count')} パッチ"
        f"（対応 X バージョン: {x_versions}）",
        f"- Twitch: {summary.get('twitch_patch_count')} パッチ"
        "（対応 Twitch バージョン: 31.8.0 安定版 / 31.9.0_BETA 実験的対応）",
        "",
        "## 日本語化",
        "",
        f"- Piko 設定 UI の日本語訳 {summary.get('ja_overlay_strings')} 件"
        "（リソースオーバーレイ）",
        "- Twitch 側はパッチ名・説明とパッチ設定 UI をソース直接翻訳",
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
