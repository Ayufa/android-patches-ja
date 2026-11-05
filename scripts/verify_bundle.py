#!/usr/bin/env python3
"""Verify a combined Android Patches JA bundle (.mpp).

Checks that the single bundle really contains both patch sets:

- bundle structure: patch classes dex plus all three extension
  payloads (newx, shared, twitch) and both resource sets
  (addresources with the Japanese overlay, reactnative/, hermes/).
- MANIFEST metadata points at this project and carries a
  Patcher-Version.
- the Japanese overlay holds the full Piko settings translation.
- patch inventory: when a patches-list.json from the build is given,
  every listed patch name must be present in classes.dex; names are
  grouped per app (``NewX:`` prefix = X, everything else = Twitch).

Writes a bundle-summary.json next to the bundle and exits non-zero
when any check fails.
"""

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

EXPECTED_EXTENSIONS = {
    "extensions/newx.mpe",
    "extensions/shared.mpe",
    "extensions/twitch.mpe",
}
JA_STRINGS_ENTRY = "addresources/values-ja-rJP/newx/strings.xml"
# Stable sample of translated Twitch patch names (see
# sources/twitch/patches-list history / LOCALIZATION docs). Used to
# sanity-check the dex even when no patches list was generated.
TWITCH_NAME_SAMPLES = [
    "BTTV、FFZ、7TVのエモート",
    "削除されたメッセージを表示",
    "配信中の広告をブロック",
]


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)
    print(f"FAIL: {message}")


def ok(message: str) -> None:
    print(f"ok: {message}")


def load_patch_names(patches_list_path: Path) -> list[str]:
    data = json.loads(patches_list_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        # Piko generator format: a plain list of names.
        return [str(item) for item in data]
    # Twitch generator format: {"patches": [{"name": ...}, ...]}.
    return [str(patch["name"]) for patch in data["patches"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", help="Path to the .mpp bundle")
    parser.add_argument("--version", default=None, help="Expected bundle version")
    parser.add_argument(
        "--patches-list",
        default=None,
        help="patches-list.json generated alongside the bundle",
    )
    parser.add_argument(
        "--summary",
        default=None,
        help="Where to write bundle-summary.json (default: next to the bundle)",
    )
    args = parser.parse_args()

    bundle_path = Path(args.bundle)
    failures: list[str] = []
    summary: dict = {"bundle": bundle_path.name}

    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())

        for entry in sorted(EXPECTED_EXTENSIONS):
            if entry in names:
                ok(f"extension payload present: {entry}")
            else:
                fail(f"missing extension payload: {entry}", failures)
        summary["extensions"] = sorted(names & EXPECTED_EXTENSIONS)

        if "classes.dex" in names:
            ok("classes.dex present")
            dex = archive.read("classes.dex")
        else:
            fail("classes.dex missing", failures)
            dex = b""
        summary["dex_bytes"] = len(dex)

        rn_assets = [n for n in names if n.startswith("reactnative/") and n.endswith(".js")]
        if len(rn_assets) >= 20:
            ok(f"reactnative assets present: {len(rn_assets)} js files")
        else:
            fail(f"reactnative assets incomplete: {len(rn_assets)} js files", failures)
        summary["reactnative_js_files"] = len(rn_assets)

        if any(n.startswith("hermes/") for n in names):
            ok("hermes assets present")
        else:
            fail("hermes assets missing", failures)

        if JA_STRINGS_ENTRY in names:
            ja_xml = archive.read(JA_STRINGS_ENTRY).decode("utf-8")
            string_count = len(re.findall(r"<string\s+name=", ja_xml))
            if string_count >= 400:
                ok(f"Japanese overlay present: {string_count} strings")
            else:
                fail(f"Japanese overlay too small: {string_count} strings", failures)
            if not re.search(r"[\u3040-\u30ff]", ja_xml):
                fail("Japanese overlay contains no kana", failures)
            summary["ja_overlay_strings"] = string_count
        else:
            fail(f"Japanese overlay missing: {JA_STRINGS_ENTRY}", failures)

        manifest = archive.read("META-INF/MANIFEST.MF").decode("utf-8")
        # Unfold continuation lines of the JAR manifest format.
        manifest = manifest.replace("\r\n ", "").replace("\n ", "")
        fields = dict(
            line.split(": ", 1) for line in manifest.splitlines() if ": " in line
        )
        summary["manifest"] = fields
        if fields.get("Name") == "Android Patches JA":
            ok("MANIFEST Name is Android Patches JA")
        else:
            fail(f"MANIFEST Name is {fields.get('Name')!r}", failures)
        if args.version and fields.get("Version") != args.version:
            fail(
                f"MANIFEST Version is {fields.get('Version')!r}, "
                f"expected {args.version!r}",
                failures,
            )
        if fields.get("Patcher-Version"):
            ok(f"Patcher-Version: {fields['Patcher-Version']}")
        else:
            fail("MANIFEST has no Patcher-Version", failures)

    newx_names: list[str] = []
    twitch_names: list[str] = []
    if args.patches_list:
        all_names = load_patch_names(Path(args.patches_list))
        newx_names = [n for n in all_names if n.startswith("NewX:")]
        twitch_names = [n for n in all_names if not n.startswith("NewX:")]
        missing = [n for n in all_names if n.encode("utf-8") not in dex]
        if missing:
            fail(f"patch names missing from classes.dex: {missing}", failures)
        else:
            ok(f"all {len(all_names)} listed patch names found in classes.dex")
    else:
        newx_occurrences = len(re.findall(rb"NewX: ", dex))
        if newx_occurrences >= 40:
            ok(f"dex contains {newx_occurrences} 'NewX: ' patch name strings")
            newx_names = [f"<{newx_occurrences} occurrences in dex>"]
        else:
            fail(f"only {newx_occurrences} 'NewX: ' strings in dex", failures)
        for sample in TWITCH_NAME_SAMPLES:
            if sample.encode("utf-8") in dex:
                ok(f"Twitch patch name in dex: {sample}")
                twitch_names.append(sample)
            else:
                fail(f"Twitch patch name missing from dex: {sample}", failures)

    summary["newx_patch_count"] = (
        len(newx_names) if args.patches_list else None
    )
    summary["twitch_patch_count"] = (
        len(twitch_names) if args.patches_list else None
    )
    summary["newx_patches"] = newx_names
    summary["twitch_patches"] = twitch_names

    summary_path = (
        Path(args.summary)
        if args.summary
        else bundle_path.parent / "bundle-summary.json"
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"summary written: {summary_path}")
    print(
        f"patches: NewX (X) = {summary['newx_patch_count']}, "
        f"Twitch = {summary['twitch_patch_count']}"
    )

    if failures:
        print(f"\n{len(failures)} check(s) FAILED")
        return 1
    print("\nAll bundle checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
