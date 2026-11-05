#!/usr/bin/env python3
"""Build the combined Android Patches JA bundle (one .mpp).

The bundle is built inside a fresh, read-only clone of upstream
crimera/piko (branch ``x-lite``), exactly like the piko-newx-ja builder:

1. Clone crimera/piko@x-lite (depth 1) into a temporary directory.
2. Strip the clone down to the NewX patch set (pre_build_cleanup).
3. Apply the Japanese resource overlay for the Piko settings UI
   (localization/values-ja-rJP -> addresources/values-ja-rJP).
4. Inject the Twitch patch set from sources/twitch (a translated source
   copy kept in this repository): patch sources, patch resources
   (reactnative/, hermes/), the extensions/twitch module and the
   shared/ivs-api compile-only sources it needs.
5. Rewrite the bundle metadata (name/description/source/author) in the
   temporary tree and set the bundle version.
6. Run ``./gradlew clean buildAndroid`` and copy out
   patches-<version>.mpp. A patches list is generated afterwards on a
   best-effort basis for verification/release metadata.

Upstream repositories are only ever read (cloned / fetched), never
written. All adaptations happen inside the throwaway build tree.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

PIKO_REPO = "crimera/piko"
PIKO_REPOSITORY = f"https://github.com/{PIKO_REPO}.git"
PIKO_BRANCH = "x-lite"
XLITE_CONSTANTS = (
    "patches/src/main/kotlin/app/crimera/patches/newx/utils/Constants.kt"
)

# Japanese localization overlay: translated Android resources shipped in
# this repository under localization/values-ja-rJP/. They are copied into
# the freshly cloned upstream Piko tree at build time, so the X side of
# the bundle always builds from the latest upstream x-lite sources with
# the Japanese strings applied on top.
LOCALIZATION_DIR = REPO_ROOT / "localization" / "values-ja-rJP"
ADDRESOURCES_DIR = "patches/src/main/resources/addresources"

# Twitch side: translated source copy of ryykitty/twitch-patched kept in
# this repository (see docs/UPSTREAM.md). Injected into the build tree.
TWITCH_SOURCES = REPO_ROOT / "sources" / "twitch"

# Combined bundle metadata written into the temporary tree's
# patches/build.gradle.kts about block (ends up in the .mpp MANIFEST).
BUNDLE_NAME = "Android Patches JA"
BUNDLE_DESCRIPTION = (
    "X (NewX) と Twitch の Morphe パッチを1つにまとめた日本語化バンドル"
)
BUNDLE_SOURCE = "https://github.com/Ayufa/android-patches-ja"
BUNDLE_AUTHOR = "Ayufa"
BUNDLE_CONTACT = ""
BUNDLE_WEBSITE = "https://github.com/Ayufa/android-patches-ja"
BUNDLE_LICENSE = "GNU General Public License v3.0"


def _string_keys(xml_text: str) -> set[str]:
    return set(re.findall(r'<string\s+name="([^"]+)"', xml_text))


def apply_japanese_localization(piko_directory: Path) -> None:
    """Copy the Japanese resources into the cloned Piko tree.

    Missing keys are not an error: Android falls back to the default
    (English) resources, so new upstream strings stay visible in English
    until they are translated. They are reported here so a release log
    shows the translation coverage.
    """
    if not LOCALIZATION_DIR.is_dir():
        print("No localization directory found; building without Japanese overlay")
        return

    target_root = piko_directory / ADDRESOURCES_DIR / "values-ja-rJP"
    for source_file in sorted(LOCALIZATION_DIR.rglob("*.xml")):
        relative = source_file.relative_to(LOCALIZATION_DIR)
        destination = target_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination)
        print(f"Applied Japanese localization: values-ja-rJP/{relative.as_posix()}")

        english_file = (
            piko_directory / ADDRESOURCES_DIR / "values" / relative
        )
        if english_file.is_file():
            english_keys = _string_keys(english_file.read_text(encoding="utf-8"))
            japanese_keys = _string_keys(source_file.read_text(encoding="utf-8"))
            missing = sorted(english_keys - japanese_keys)
            if missing:
                print(
                    f"  {len(missing)} untranslated string(s) fall back to English: "
                    + ", ".join(missing)
                )
            else:
                print(f"  translation coverage: {len(japanese_keys)}/{len(english_keys)}")


def get_supported_versions(constants: str) -> frozenset[str]:
    """Return the X-Lite app versions supported by the checked-out Piko source."""
    versions = frozenset(
        re.findall(r'AppTarget\(version\s*=\s*"([^"]+)"\)', constants)
    )
    if not versions:
        raise ValueError("Could not find X-Lite compatible app versions in Piko")
    return versions


def pre_build_cleanup(piko_directory: Path) -> None:
    """Remove Instagram, Twitter, and legacy patches/extensions before building."""
    # Remove non-NewX patch source packages
    for path in [
        piko_directory / "patches/src/main/kotlin/app/crimera/patches/instagram",
        piko_directory / "patches/src/main/kotlin/app/crimera/patches/twitter",
        piko_directory / "patches/src/main/kotlin/app/revanced",
    ]:
        if path.exists():
            shutil.rmtree(path)

    # Remove non-NewX extension modules
    for path in [
        piko_directory / "extensions/instagram",
        piko_directory / "extensions/twitter",
    ]:
        if path.exists():
            shutil.rmtree(path)

    # Keep twitter/bringbacktwitter assets for Bring back twitter patch
    twitter_res = piko_directory / "patches/src/main/resources/twitter"
    if twitter_res.exists():
        for item in twitter_res.iterdir():
            if item.name != "bringbacktwitter":
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

    addresources_dir = piko_directory / "patches/src/main/resources/addresources"
    if addresources_dir.exists():
        for res_name in ("instagram", "twitter"):
            for matched in addresources_dir.glob(f"*/{res_name}"):
                if matched.is_dir():
                    shutil.rmtree(matched)


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"Twitch source tree is missing: {source}")
    shutil.copytree(source, destination, dirs_exist_ok=True)
    print(f"Injected Twitch sources: {destination}")


def _strip_extension_dsl(build_file: Path) -> None:
    """Remove the Morphe plugin 2.0.0 ``extension { ... }`` block.

    The Twitch extension build file was written for app.morphe.patches
    plugin 2.0.0, where the .mpe output name is declared explicitly.
    The Piko build tree uses plugin 1.3.4, which derives the name from
    the module path instead (extensions/twitch -> extensions/twitch.mpe,
    the same value), and does not know the block. The block is flat
    (no nested braces), so a line-based removal is exact.
    """
    lines = build_file.read_text(encoding="utf-8").splitlines(keepends=True)
    kept: list[str] = []
    removed = 0
    index = 0
    while index < len(lines):
        if lines[index].strip() == "extension {":
            end = index + 1
            while end < len(lines) and lines[end].strip() != "}":
                end += 1
            if end >= len(lines):
                raise ValueError(f"Unterminated extension block in {build_file}")
            removed += 1
            index = end + 1
            # Swallow one following blank line to keep the file tidy.
            if index < len(lines) and lines[index].strip() == "":
                index += 1
            continue
        kept.append(lines[index])
        index += 1
    if removed != 1:
        raise ValueError(
            f"Expected exactly one extension block in {build_file}, removed {removed}"
        )
    build_file.write_text("".join(kept), encoding="utf-8")
    print("Adapted extensions/twitch/build.gradle.kts: removed extension {} block")


def _append_proguard_keep(piko_directory: Path) -> None:
    """Keep the Twitch extension classes in the extension R8 step.

    The Piko tree's extensions/proguard-rules.pro only keeps
    app.morphe.**, app.revanced.** and com.google.**. The Twitch
    extension lives in dev.twitchpatches.** and is referenced from
    patches by class-name strings, so it needs an explicit keep.
    """
    rules = piko_directory / "extensions" / "proguard-rules.pro"
    text = rules.read_text(encoding="utf-8")
    keep = "-keep class dev.twitchpatches.** {\n  *;\n}\n"
    if "dev.twitchpatches" not in text:
        rules.write_text(text.rstrip("\n") + "\n\n" + keep, encoding="utf-8")
    print("Adapted extensions/proguard-rules.pro: keep dev.twitchpatches.**")


def _rewrite_about_block(piko_directory: Path) -> None:
    """Point the bundle metadata (MANIFEST) at the combined project.

    Replacements are scoped to the ``about { ... }`` block: the same
    file has other ``description =`` assignments in task registrations
    that must not be touched.
    """
    build_file = piko_directory / "patches" / "build.gradle.kts"
    lines = build_file.read_text(encoding="utf-8").splitlines(keepends=True)

    start = next(
        (i for i, line in enumerate(lines) if line.strip() == "about {"),
        None,
    )
    if start is None:
        raise ValueError("No about block in patches/build.gradle.kts")
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].rstrip() == "    }"
        ),
        None,
    )
    if end is None:
        raise ValueError("Unterminated about block in patches/build.gradle.kts")

    values = {
        "name": BUNDLE_NAME,
        "description": BUNDLE_DESCRIPTION,
        "source": BUNDLE_SOURCE,
        "author": BUNDLE_AUTHOR,
        "contact": BUNDLE_CONTACT,
        "website": BUNDLE_WEBSITE,
        "license": BUNDLE_LICENSE,
    }
    for key, value in values.items():
        pattern = re.compile(rf'^(\s*{key}\s*=\s*)"[^"]*"')
        replaced = 0
        for i in range(start + 1, end):
            lines[i], count = pattern.subn(
                rf'\g<1>"{value}"', lines[i], count=1
            )
            replaced += count
        if replaced != 1:
            raise ValueError(
                f"Expected exactly one about.{key} in patches/build.gradle.kts, "
                f"replaced {replaced}"
            )
    build_file.write_text("".join(lines), encoding="utf-8")
    print("Rewrote bundle about metadata for Android Patches JA")


def inject_twitch_sources(piko_directory: Path) -> None:
    """Copy the Twitch patch set from sources/twitch into the build tree."""
    patches_main = TWITCH_SOURCES / "patches" / "src" / "main"
    _copy_tree(
        patches_main / "kotlin" / "dev",
        piko_directory / "patches" / "src" / "main" / "kotlin" / "dev",
    )
    for resource_dir in ("reactnative", "hermes"):
        _copy_tree(
            patches_main / "resources" / resource_dir,
            piko_directory / "patches" / "src" / "main" / "resources" / resource_dir,
        )
    _copy_tree(
        TWITCH_SOURCES / "extensions" / "twitch",
        piko_directory / "extensions" / "twitch",
    )
    _strip_extension_dsl(
        piko_directory / "extensions" / "twitch" / "build.gradle.kts"
    )
    _copy_tree(TWITCH_SOURCES / "shared", piko_directory / "shared")
    _append_proguard_keep(piko_directory)
    _rewrite_about_block(piko_directory)


def set_project_version(piko_directory: Path, version: str) -> None:
    """Set the version only in the temporary Piko checkout used for a build."""
    properties_path = piko_directory / "gradle.properties"
    lines = properties_path.read_text(encoding="utf-8").splitlines(keepends=True)
    version_indexes = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^\s*version\s*=", line)
    ]
    if len(version_indexes) != 1:
        raise ValueError("Piko gradle.properties must contain exactly one version")

    lines[version_indexes[0]] = f"version = {version}\n"
    properties_path.write_text("".join(lines), encoding="utf-8")


def twitch_base_version() -> str:
    """Version of the upstream twitch-patched release the copy is based on."""
    changelog = TWITCH_SOURCES / "CHANGELOG.md"
    if changelog.is_file():
        match = re.search(
            r"\[(\d+\.\d+\.\d+)\]", changelog.read_text(encoding="utf-8")
        )
        if match:
            return match.group(1)
    return "unknown"


@dataclass
class CombinedBuild:
    piko_commit: str
    supported_versions: frozenset[str]
    twitch_base: str
    patches_list: Path | None = field(default=None)


def build_combined(
    bundle_version: str, output: str | None = None
) -> CombinedBuild:
    if bundle_version.startswith("v"):
        raise ValueError("bundle_version must not include the leading v")
    if output is None:
        output = f"bins/patches-{bundle_version}.mpp"
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="android-patches-ja-") as temporary_directory:
        piko_directory = Path(temporary_directory) / "piko"

        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                PIKO_BRANCH,
                PIKO_REPOSITORY,
                str(piko_directory),
            ],
            check=True,
        )

        supported_versions = get_supported_versions(
            (piko_directory / XLITE_CONSTANTS).read_text()
        )

        pre_build_cleanup(piko_directory)
        apply_japanese_localization(piko_directory)
        inject_twitch_sources(piko_directory)
        set_project_version(piko_directory, bundle_version)

        subprocess.run(
            ["./gradlew", "clean", "buildAndroid"],
            cwd=piko_directory,
            env=os.environ.copy(),
            check=True,
        )

        artifacts_directory = piko_directory / "patches" / "build" / "libs"
        artifact = artifacts_directory / f"patches-{bundle_version}.mpp"
        if not artifact.is_file():
            raise FileNotFoundError(
                f"Build did not produce the expected artifact {artifact.name}"
            )
        shutil.copy2(artifact, output_path)
        print(f"Built combined bundle: {output_path}")

        # Best effort: generate the patches list for verification and
        # release metadata. Failure here must not fail the build itself.
        patches_list: Path | None = None
        try:
            # The clone ships an upstream patches-list.json; only a file
            # written after this point counts as generated by this build.
            list_search_after = time.time()
            subprocess.run(
                ["./gradlew", ":patches:generatePatchesList"],
                cwd=piko_directory,
                env=os.environ.copy(),
                check=True,
            )
            candidates = [
                candidate
                for candidate in piko_directory.rglob("patches-list.json")
                if ".git" not in candidate.parts
                and candidate.stat().st_mtime >= list_search_after
            ]
            if candidates:
                generated = max(candidates, key=lambda c: c.stat().st_mtime)
                patches_list = output_path.parent / "patches-list.json"
                shutil.copy2(generated, patches_list)
                print(f"Generated patches list: {patches_list}")
            else:
                print("generatePatchesList produced no fresh patches-list.json")
        except subprocess.CalledProcessError as error:
            print(f"WARNING: generatePatchesList failed ({error}); continuing")

        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=piko_directory,
            check=True,
            capture_output=True,
            text=True,
        )

    return CombinedBuild(
        piko_commit=commit.stdout.strip(),
        supported_versions=supported_versions,
        twitch_base=twitch_base_version(),
        patches_list=patches_list,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        required=True,
        help="Combined bundle version (semver, without the leading v)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output .mpp path (default: bins/patches-<version>.mpp)",
    )
    parser.add_argument(
        "--metadata",
        default=None,
        help="Where to write build metadata JSON (default: next to the output)",
    )
    args = parser.parse_args()

    result = build_combined(args.version, args.output)

    output_path = Path(args.output or f"bins/patches-{args.version}.mpp")
    metadata_path = (
        Path(args.metadata)
        if args.metadata
        else output_path.parent / "build-metadata.json"
    )
    metadata = {
        "version": args.version,
        "piko_commit": result.piko_commit,
        "piko_branch": PIKO_BRANCH,
        "x_supported_versions": sorted(result.supported_versions),
        "twitch_base_version": result.twitch_base,
        "patches_list_generated": result.patches_list is not None,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
