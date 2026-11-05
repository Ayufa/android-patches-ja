#!/usr/bin/env python3
"""Verify a combined Android Patches JA bundle (.mpp).

Checks that the single bundle really contains both patch sets:

- bundle structure: patch classes dex plus all three extension
  payloads (newx, shared, twitch) and both resource sets
  (addresources with the Japanese overlay, reactnative/, hermes/).
- MANIFEST metadata points at this project and carries a
  Patcher-Version.
- the Japanese overlay holds the full Piko settings translation.
- patch inventory: the bundle lists exactly ONE patch per app
  (v1.1.0+ umbrella structure). When a patches-list.json from the
  build is given, it must contain exactly 2 patches -- one targeting
  com.twitter.android, one targeting tv.twitch.android.app -- and
  both names must be present in classes.dex. The feature patch code
  of both sets (which is no longer listed individually) is checked
  via code markers in classes.dex and the extension payloads.

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
# The two umbrella patches are the only listed patches since v1.1.0.
UMBRELLA_PATCHES = {
    "com.twitter.android": "X（NewX）日本語化パッチ",
    "tv.twitch.android.app": "Twitch 日本語化パッチ",
}
# Code markers proving both feature patch sets survived in classes.dex
# even though the feature patches are no longer listed by name: class
# descriptor prefixes of both sets, plus the settings key of a
# settings-gated opt-in NewX patch (Hide post dividers).
DEX_CODE_MARKERS = [
    b"app/crimera/patches/newx",
    b"dev/twitchpatches/patches",
    b"newx.timeline.hide_post_dividers",
]
# The Twitch settings screen title must be inside the Twitch extension
# payload (the feature toggles live there at runtime).
TWITCH_EXTENSION_MARKER = "パッチ設定"


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)
    print(f"FAIL: {message}")


def ok(message: str) -> None:
    print(f"ok: {message}")


def load_patches(patches_list_path: Path) -> list[dict]:
    """Return [{name, packages}] from a generated patches-list.json."""
    data = json.loads(patches_list_path.read_text(encoding="utf-8"))
    entries = data["patches"] if isinstance(data, dict) else data
    patches = []
    for entry in entries:
        if isinstance(entry, str):
            patches.append({"name": entry, "packages": []})
        else:
            compat = entry.get("compatiblePackages") or []
            if isinstance(compat, dict):
                packages = sorted(compat.keys())
            else:
                packages = sorted(
                    item["packageName"] for item in compat if item.get("packageName")
                )
            patches.append({"name": str(entry["name"]), "packages": packages})
    return patches


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

        twitch_ext = (
            archive.read("extensions/twitch.mpe")
            if "extensions/twitch.mpe" in names
            else b""
        )

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

    # Both feature patch sets must be present as code even though only
    # the two umbrella patches are listed by name.
    for marker in DEX_CODE_MARKERS:
        if marker in dex:
            ok(f"dex code marker present: {marker.decode()}")
        else:
            fail(f"dex code marker missing: {marker.decode()}", failures)
    if TWITCH_EXTENSION_MARKER.encode("utf-8") in twitch_ext:
        ok("Twitch extension contains the パッチ設定 screen strings")
    else:
        fail("Twitch extension lacks パッチ設定 strings", failures)

    listed: list[dict] = []
    if args.patches_list:
        listed = load_patches(Path(args.patches_list))
        if len(listed) == len(UMBRELLA_PATCHES):
            ok(f"patches list contains exactly {len(listed)} patches")
        else:
            fail(
                f"patches list contains {len(listed)} patches, "
                f"expected exactly {len(UMBRELLA_PATCHES)} (one per app)",
                failures,
            )
        seen_packages: set[str] = set()
        for patch in listed:
            for package in patch["packages"]:
                seen_packages.add(package)
                expected_name = UMBRELLA_PATCHES.get(package)
                if expected_name is None:
                    fail(f"listed patch targets unexpected app: {package}", failures)
                elif patch["name"] != expected_name:
                    fail(
                        f"listed patch for {package} is {patch['name']!r}, "
                        f"expected {expected_name!r}",
                        failures,
                    )
            if patch["name"].encode("utf-8") not in dex:
                fail(f"listed patch name missing from classes.dex: {patch['name']}", failures)
        missing_apps = set(UMBRELLA_PATCHES) - seen_packages
        if missing_apps:
            fail(f"no listed patch for app(s): {sorted(missing_apps)}", failures)
    else:
        for package, name in UMBRELLA_PATCHES.items():
            if name.encode("utf-8") in dex:
                ok(f"umbrella patch for {package} found in dex: {name}")
                listed.append({"name": name, "packages": [package]})
            else:
                fail(f"umbrella patch name missing from dex: {name}", failures)

    summary["listed_patches"] = listed
    summary["listed_patch_count"] = len(listed)
    summary["newx_patch_count"] = sum(
        1 for p in listed if "com.twitter.android" in p["packages"]
    )
    summary["twitch_patch_count"] = sum(
        1 for p in listed if "tv.twitch.android.app" in p["packages"]
    )

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
