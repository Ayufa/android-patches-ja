#!/usr/bin/env python3
"""Build the combined Ayufa Patches JP bundle (one .mpp).

All three patch sets are kept in this repository as translated source
copies (the "clone upstream + translate only" model, v1.2.0+):

- sources/piko: a copy of upstream crimera/piko (branch ``x-lite``,
  stripped to the NewX patch set) with the Japanese strings applied
  in-tree: the Piko settings UI resources under
  addresources/values-ja-rJP/ and the NewX patch descriptions
  translated in the patch declarations (patch names stay upstream
  English: the patcher executes patches sorted by name, so names are
  never translated). The upstream base commit is recorded in
  sources/piko/UPSTREAM_BASE.md.
- sources/twitch: a translated source copy of ryykitty/twitch-patched.
- sources/line: a translated source copy of
  andrewliang25/morphe-patches. The copy keeps upstream's full tree,
  but only the LINE patch set is injected; the Facebook patch sources
  stay out of the bundle. The upstream base commit is recorded in
  sources/line/UPSTREAM_BASE.md.

The build itself adds no patch machinery of its own:

1. Copy sources/piko into a temporary directory (it is the build
   host: a full Piko tree with the Morphe Gradle plugin).
2. Report the Japanese translation coverage of the Piko settings UI
   (untranslated keys fall back to English at runtime).
3. Inject the Twitch patch set from sources/twitch: patch sources,
   patch resources (reactnative/, hermes/), the extensions/twitch
   module and the shared/ivs-api compile-only sources it needs.
4. Inject the LINE patch set from sources/line: the LINE and shared
   patch sources and the extensions/extension module.
5. Rewrite the bundle metadata (name/description/source/author) in
   the temporary tree and set the bundle version.
6. Run ``./gradlew clean buildAndroid`` and copy out
   patches-<version>.mpp. A patches list is generated afterwards on a
   best-effort basis for verification/release metadata; the release
   workflow fails if the list is missing (v1.1.0 shipped without one).

Upstream repositories are only ever read (fetched / merged into the
source copies by the daily sync), never written. All build-time
adaptations happen inside the throwaway build tree.
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

# X side: translated source copy of crimera/piko@x-lite kept in this
# repository (see docs/UPSTREAM.md). Its patches/src tree doubles as
# the build host for the combined bundle.
PIKO_SOURCES = REPO_ROOT / "sources" / "piko"
PIKO_BASE_FILE = PIKO_SOURCES / "UPSTREAM_BASE.md"
XLITE_CONSTANTS = (
    "patches/src/main/kotlin/app/crimera/patches/newx/utils/Constants.kt"
)
ADDRESOURCES_DIR = "patches/src/main/resources/addresources"

# Twitch side: translated source copy of ryykitty/twitch-patched kept
# in this repository (see docs/UPSTREAM.md). Injected into the build
# tree hosted by the Piko copy.
TWITCH_SOURCES = REPO_ROOT / "sources" / "twitch"

# LINE side: translated source copy of andrewliang25/morphe-patches
# kept in this repository (see docs/UPSTREAM.md). Only its LINE patch
# set is injected into the build tree; the Facebook patches are not.
LINE_SOURCES = REPO_ROOT / "sources" / "line"

# Combined bundle metadata written into the temporary tree's
# patches/build.gradle.kts about block (ends up in the .mpp MANIFEST).
BUNDLE_NAME = "Ayufa Patches JP"
BUNDLE_DESCRIPTION = (
    "X (NewX)・Twitch・LINE の Morphe パッチを1つにまとめた日本語化バンドル"
)
BUNDLE_SOURCE = "https://github.com/Ayufa/ayufa-patches-jp"
BUNDLE_AUTHOR = "Ayufa"
BUNDLE_CONTACT = ""
BUNDLE_WEBSITE = "https://github.com/Ayufa/ayufa-patches-jp"
BUNDLE_LICENSE = "GNU General Public License v3.0"


def piko_base_commit() -> str:
    """Upstream piko commit the sources/piko copy is based on."""
    match = re.search(
        r"^- commit:\s*([0-9a-f]{40})\s*$",
        PIKO_BASE_FILE.read_text(encoding="utf-8"),
        re.M,
    )
    if not match:
        raise ValueError(f"No base commit recorded in {PIKO_BASE_FILE}")
    return match.group(1)


def _string_keys(xml_text: str) -> set[str]:
    return set(re.findall(r'<string\s+name="([^"]+)"', xml_text))


def report_translation_coverage(piko_directory: Path) -> None:
    """Report untranslated Piko settings strings in the source copy.

    Missing keys are not an error: Android falls back to the default
    (English) resources, so new upstream strings stay visible in
    English until they are translated. They are reported here so a
    release log shows the translation coverage.
    """
    english_file = (
        piko_directory / ADDRESOURCES_DIR / "values" / "newx" / "strings.xml"
    )
    japanese_file = (
        piko_directory / ADDRESOURCES_DIR / "values-ja-rJP" / "newx" / "strings.xml"
    )
    if not japanese_file.is_file():
        print("No Japanese settings resources in sources/piko; building untranslated")
        return
    english_keys = _string_keys(english_file.read_text(encoding="utf-8"))
    japanese_keys = _string_keys(japanese_file.read_text(encoding="utf-8"))
    missing = sorted(english_keys - japanese_keys)
    if missing:
        print(
            f"  {len(missing)} untranslated string(s) fall back to English: "
            + ", ".join(missing)
        )
    else:
        print(f"  translation coverage: {len(japanese_keys)}/{len(english_keys)}")


def get_supported_versions(constants: str) -> frozenset[str]:
    """Return the X-Lite app versions supported by the Piko source copy."""
    versions = frozenset(
        re.findall(r'AppTarget\(version\s*=\s*"([^"]+)"\)', constants)
    )
    if not versions:
        raise ValueError("Could not find X-Lite compatible app versions in Piko")
    return versions


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"Source tree is missing: {source}")
    shutil.copytree(source, destination, dirs_exist_ok=True)
    print(f"Copied tree: {source} -> {destination}")


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
    print(f"Adapted {build_file}: removed extension {{}} block")


# Packages of the injected extensions whose classes are referenced
# from patches by class-name strings and therefore need an explicit
# keep in the extension R8 step.
_PROGUARD_KEEPS = (
    "dev.twitchpatches",
    "app.andrewliang",
)


def _append_proguard_keep(piko_directory: Path) -> None:
    """Keep the injected extension classes in the extension R8 step.

    The Piko tree's extensions/proguard-rules.pro only keeps
    app.morphe.**, app.revanced.** and com.google.**. The Twitch
    extension lives in dev.twitchpatches.** and the LINE extension in
    app.andrewliang.**, so both need an explicit keep. Idempotent:
    each keep is appended only when its package is not mentioned yet.
    """
    rules = piko_directory / "extensions" / "proguard-rules.pro"
    text = rules.read_text(encoding="utf-8")
    for package in _PROGUARD_KEEPS:
        if package not in text:
            keep = f"-keep class {package}.** {{\n  *;\n}}\n"
            text = text.rstrip("\n") + "\n\n" + keep
    rules.write_text(text, encoding="utf-8")
    print(
        "Adapted extensions/proguard-rules.pro: keep "
        + " and ".join(f"{package}.**" for package in _PROGUARD_KEEPS)
    )


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
    print("Rewrote bundle about metadata for Ayufa Patches JP")


def prepare_build_tree(piko_directory: Path) -> None:
    """Copy the sources/piko tree into the throwaway build directory."""
    _copy_tree(PIKO_SOURCES, piko_directory)
    # The copy carries upstream's own stale patches-list.json; remove
    # it so only a list generated by this build can be picked up.
    stale_list = piko_directory / "patches-list.json"
    if stale_list.exists():
        stale_list.unlink()
        print("Removed stale patches-list.json from the build tree")


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


def inject_line_sources(piko_directory: Path) -> None:
    """Copy the LINE patch set from sources/line into the build tree.

    Only the LINE patches enter the bundle. The source copy keeps
    upstream's full tree, but the Facebook patch sources and
    upstream's release tooling (patches/src/main/kotlin/util/, its
    own generatePatchesList) are not injected. The shared subtree
    carries the LINE compatibility definition and the resource-id
    resolver the LINE patches depend on; the LINE settings UI lives
    in the extensions/extension module.
    """
    patches_kotlin = LINE_SOURCES / "patches" / "src" / "main" / "kotlin"
    build_kotlin = piko_directory / "patches" / "src" / "main" / "kotlin"
    for subtree in ("line", "shared"):
        _copy_tree(
            patches_kotlin / "app" / "andrewliang" / "patches" / subtree,
            build_kotlin / "app" / "andrewliang" / "patches" / subtree,
        )
    _copy_tree(
        LINE_SOURCES / "extensions" / "extension",
        piko_directory / "extensions" / "extension",
    )
    _strip_extension_dsl(
        piko_directory / "extensions" / "extension" / "build.gradle.kts"
    )
    _append_proguard_keep(piko_directory)


def set_project_version(piko_directory: Path, version: str) -> None:
    """Set the version only in the temporary Piko tree used for a build."""
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


def line_base_version() -> str:
    """Version of the upstream morphe-patches release the copy is based on."""
    changelog = LINE_SOURCES / "CHANGELOG.md"
    if changelog.is_file():
        match = re.search(
            r"\[(\d+\.\d+\.\d+)\]", changelog.read_text(encoding="utf-8")
        )
        if match:
            return match.group(1)
    return "unknown"


# The order of upstream crimera/piko-newx's published patches-list.json
# (v3.73.0). The Morphe Gradle plugin emits the generated list sorted
# by patch name instead; the generated X entries are reordered to
# match upstream's published list so the released asset reads the
# same. This is cosmetic only: the patcher sorts by name at runtime
# regardless of the list order. Keep in sync with EXPECTED_X_ORDER in
# scripts/verify_bundle.py.
UPSTREAM_X_LIST_ORDER = [
    "NewX: Remove ads",
    "NewX: Disable blur effects",
    "NewX: Restore Twitter branding",
    "NewX: Browse tweet object",
    "NewX: Open canonical URLs",
    "NewX: Clone",
    "NewX: Crash logs",
    "NewX: Custom font",
    "NewX: Custom sharing domain",
    "NewX: Permanent share links",
    "NewX: Remove share tracking parameters",
    "NewX: Customize drawer items",
    "NewX: Theme",
    "NewX: Feature switch overrides",
    "NewX: Enable quality-of-life feature flags",
    "NewX: Customize inline actions",
    "NewX: Inline download button",
    "NewX: Redirect downloads to chosen folder",
    "NewX: Log HLS audio renditions",
    "NewX: Customize media menu items",
    "NewX: Set default media tab",
    "NewX: Gallery profile Photos tab",
    "NewX: Customize navigation bar",
    "NewX: Hide post author actions",
    "NewX: Hide post reply bar",
    "NewX: Customize post menu items",
    "NewX: Set default profile post sorting",
    "NewX: Customize profile tabs",
    "NewX: Set default reply sorting",
    "NewX: Server error logging",
    "NewX: Disable video player scrolling",
    "NewX: Hide premium upsell",
    "NewX: Unlock color customization",
    "NewX: Unlock downloads",
    "NewX: Customize timeline tabs",
    "NewX: Disable automatic timeline refresh",
    "NewX: Filter For You by topic",
    "NewX: Hide AI-generated posts",
    "NewX: Hide Discover more",
    "NewX: Hide compose button",
    "NewX: Hide new posts pill",
    "NewX: Hide post dividers",
    "NewX: Hide Spaces bar",
    "NewX: Hide timeline tabs bar",
    "NewX: Hide who to follow",
    "NewX: Restore pinned home tab",
    "NewX: Restore timeline position",
    "NewX: Show poll results",
    "NewX: Show sensitive media",
    "NewX: Hide posts by verified account type",
    "NewX: Filter posts by keyword",
    "NewX: Translator",
]


def reorder_patches_list(patches_list: Path) -> None:
    """Reorder the X entries of a generated patches-list.json in place.

    Only the relative order among the X (com.twitter.android) entries
    changes; every other entry keeps its generated position.
    """

    def is_x_entry(entry: object) -> bool:
        if not isinstance(entry, dict):
            return False
        compat = entry.get("compatiblePackages") or []
        if isinstance(compat, dict):
            packages = list(compat.keys())
        else:
            packages = [
                item.get("packageName") for item in compat if isinstance(item, dict)
            ]
        return "com.twitter.android" in packages

    data = json.loads(patches_list.read_text(encoding="utf-8"))
    entries = data["patches"] if isinstance(data, dict) else data
    rank = {name: index for index, name in enumerate(UPSTREAM_X_LIST_ORDER)}
    x_sorted = sorted(
        (entry for entry in entries if is_x_entry(entry)),
        key=lambda entry: rank.get(entry["name"], len(rank)),
    )
    x_iter = iter(x_sorted)
    reordered = [next(x_iter) if is_x_entry(entry) else entry for entry in entries]
    if reordered == entries:
        return
    if isinstance(data, dict):
        data["patches"] = reordered
    else:
        data = reordered
    patches_list.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("Reordered X patches in the patches list to upstream's published order")


@dataclass
class CombinedBuild:
    piko_commit: str
    supported_versions: frozenset[str]
    twitch_base: str
    line_base: str
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

    base_commit = piko_base_commit()
    supported_versions = get_supported_versions(
        (PIKO_SOURCES / XLITE_CONSTANTS).read_text(encoding="utf-8")
    )

    with tempfile.TemporaryDirectory(prefix="ayufa-patches-jp-") as temporary_directory:
        piko_directory = Path(temporary_directory) / "piko"

        prepare_build_tree(piko_directory)
        report_translation_coverage(piko_directory)
        inject_twitch_sources(piko_directory)
        inject_line_sources(piko_directory)
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
        # release metadata. The release workflow fails the release if
        # the list is missing, so a failure here cannot ship silently.
        patches_list: Path | None = None
        try:
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
                reorder_patches_list(patches_list)
                print(f"Generated patches list: {patches_list}")
            else:
                print("generatePatchesList produced no fresh patches-list.json")
        except subprocess.CalledProcessError as error:
            print(f"WARNING: generatePatchesList failed ({error}); continuing")

    return CombinedBuild(
        piko_commit=base_commit,
        supported_versions=supported_versions,
        twitch_base=twitch_base_version(),
        line_base=line_base_version(),
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
        "piko_branch": "x-lite",
        "piko_source": "sources/piko (translated source copy)",
        "x_supported_versions": sorted(result.supported_versions),
        "twitch_base_version": result.twitch_base,
        "line_base_version": result.line_base,
        "patches_list_generated": result.patches_list is not None,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
