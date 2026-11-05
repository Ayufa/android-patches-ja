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
5. Restructure to one listed patch per app: strip the name/description
   arguments from every feature patch declaration (making them
   dependency-only) and inject the two umbrella patches from umbrella/,
   whose dependsOn(...) pulls in each app's whole feature set.
6. Rewrite the bundle metadata (name/description/source/author) in the
   temporary tree and set the bundle version.
7. Run ``./gradlew clean buildAndroid`` and copy out
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

# One patch per app (v1.1.0+): the umbrella patch sources kept in this
# repository. build_combined.py strips every feature patch's name at
# build time (see apply_one_patch_per_app) and copies these into the
# build tree, so Morphe's patch list shows exactly one patch per app.
UMBRELLA_DIR = REPO_ROOT / "umbrella"

# Feature patches deliberately NOT pulled in by the umbrellas. Each was
# opt-in upstream (default = false) and cannot be disabled at runtime,
# so applying it unconditionally would change the app for every user:
#
# - clonePatch (NewX: Clone): renames the app package name / app name
#   from its patch options; unconditional application would turn every
#   install into the clone, and an unlisted patch's options cannot be
#   presented or changed in Morphe Manager.
# - bringBackTwitterPatch (NewX: Restore Twitter branding): replaces
#   the app label, icons and splash resources at patch time; resources
#   cannot be toggled at runtime.
# - newXAudioRenditionDiagnosticsPatch (NewX: Log HLS audio renditions):
#   diagnostic logging hooks with no runtime off switch.
# - inspectPlaybackPatch (Twitch: 再生の診断): wraps the playback HTTP
#   client and installs tracing hooks; no runtime off switch.
#
# The patches' code still ships inside the bundle; it simply never
# executes. Every other opt-in patch IS included, because its behaviour
# is gated by an in-app settings toggle (NewX: Browse tweet object,
# Hide post dividers, Server error logging) or performs no modification
# at all (Twitch: Twitch APKを検査 only validates/logs at patch time).
COMBINED_EXCLUDED_PATCHES = {
    "clonePatch": "renames the app package/name; options not settable when unlisted",
    "bringBackTwitterPatch": "replaces app branding at patch time; not runtime-toggleable",
    "newXAudioRenditionDiagnosticsPatch": "always-on diagnostic logging; no runtime off switch",
    "inspectPlaybackPatch": "always-on playback tracing hooks; no runtime off switch",
}

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


# ---------------------------------------------------------------------------
# One patch per app
#
# Morphe's PatchLoader only lists patches whose name is non-null (the
# Patch KDoc in morphe-patcher states an unnamed patch "will not be
# loaded by PatchLoader"), while unnamed patches still execute when a
# listed patch depends on them. So the bundle ships one named umbrella
# patch per app (umbrella/*.kt, kept in this repository) whose
# dependsOn(...) lists the app's feature patches, and every feature
# patch declaration has its `name`/`description` arguments stripped
# here, in the throwaway build tree only. Kept sources stay pristine.
#
# The umbrella dependsOn lists double as the manifest of included
# patches: the build fails if the set of named patches found upstream
# differs from manifest + COMBINED_EXCLUDED_PATCHES, so a patch added,
# removed or renamed upstream can never silently vanish from (or sneak
# into) the combined bundle -- the daily sync must consciously add it to
# an umbrella or to the exclusion list. See docs/UPSTREAM.md.

_PATCH_BUILDER_CALL = re.compile(
    r"\b(?:bytecodePatch|resourcePatch|rawResourcePatch)\s*\("
)
_PATCH_VAL_PREFIX = re.compile(
    r"(?:(private|internal)\s+)?val\s+([A-Za-z_]\w*)\s*=\s*$"
)
_TOP_LEVEL_ARG_NAME = re.compile(r"\s*([A-Za-z_]\w*)\s*=")


def _scan_parens(text: str, open_index: int) -> tuple[int, list[int]]:
    """Scan the argument list whose '(' is at open_index.

    Returns (close_index, top_level_comma_indexes). String literals
    (plain, triple-quoted, with ${ } templates), char literals and
    comments are honoured so brackets inside them do not count.
    """
    stack: list = ["code"]
    template_brace_marks: list[int] = []
    depth = 1
    brace = 0
    bracket = 0
    commas: list[int] = []
    i = open_index + 1
    n = len(text)
    while i < n:
        mode = stack[-1]
        char = text[i]
        if mode == "code":
            if text.startswith("//", i):
                stack.append("line")
                i += 2
                continue
            if text.startswith("/*", i):
                stack.append("block")
                i += 2
                continue
            if text.startswith('"""', i):
                stack.append(("str", True))
                i += 3
                continue
            if char == '"':
                stack.append(("str", False))
                i += 1
                continue
            if char == "'":
                stack.append("char")
                i += 1
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return i, commas
            elif char == "{":
                brace += 1
            elif char == "}":
                if (
                    len(stack) > 1
                    and template_brace_marks
                    and brace == template_brace_marks[-1]
                ):
                    stack.pop()
                    template_brace_marks.pop()
                    i += 1
                    continue
                brace -= 1
            elif char == "[":
                bracket += 1
            elif char == "]":
                bracket -= 1
            elif (
                char == ","
                and depth == 1
                and brace == 0
                and bracket == 0
                and len(stack) == 1
            ):
                commas.append(i)
            i += 1
            continue
        if mode == "line":
            if char == "\n":
                stack.pop()
            i += 1
            continue
        if mode == "block":
            if text.startswith("*/", i):
                stack.pop()
                i += 2
                continue
            i += 1
            continue
        if mode == "char":
            if char == "\\":
                i += 2
                continue
            if char == "'":
                stack.pop()
            i += 1
            continue
        # String literal modes: mode == ("str", triple)
        triple = mode[1]
        if triple and text.startswith('"""', i):
            stack.pop()
            i += 3
            continue
        if not triple and char == "\\":
            i += 2
            continue
        if not triple and char == '"':
            stack.pop()
            i += 1
            continue
        if text.startswith("${", i):
            stack.append("code")
            template_brace_marks.append(brace)
            i += 2
            continue
        i += 1
    raise ValueError("Unbalanced parentheses while scanning patch declaration")


@dataclass
class _PatchDeclaration:
    val: str | None
    private: bool
    has_name: bool
    removable_args: list[tuple[int, int]]  # (start, end) of name/description args


def _find_patch_declarations(text: str) -> list[_PatchDeclaration]:
    """Find every patch builder call and classify its declaration."""
    declarations: list[_PatchDeclaration] = []
    for match in _PATCH_BUILDER_CALL.finditer(text):
        open_index = match.end() - 1
        close_index, commas = _scan_parens(text, open_index)
        bounds = [open_index, *commas, close_index]
        has_name = False
        removable: list[tuple[int, int]] = []
        for seg_start, seg_end in zip(bounds, bounds[1:]):
            segment = text[seg_start + 1 : seg_end]
            name_match = _TOP_LEVEL_ARG_NAME.match(segment)
            if not name_match:
                continue
            arg_name = name_match.group(1)
            if arg_name not in ("name", "description"):
                continue
            core_start = seg_start + 1 + (
                len(segment) - len(segment.lstrip())
            )
            core_end = seg_start + 1 + len(segment.rstrip())
            if arg_name == "name":
                has_name = True
            removable.append((core_start, core_end))
        prefix = text[max(0, match.start() - 300) : match.start()]
        val_match = _PATCH_VAL_PREFIX.search(prefix)
        val = val_match.group(2) if val_match else None
        private = bool(val_match and val_match.group(1) == "private")
        if has_name and val is None:
            raise ValueError(
                "Named patch declaration without a val prefix near: "
                + text[max(0, match.start() - 80) : match.start() + 40]
            )
        declarations.append(
            _PatchDeclaration(
                val=val, private=private, has_name=has_name,
                removable_args=removable,
            )
        )
    return declarations


def _excision_interval(text: str, start: int, end: int) -> tuple[int, int]:
    """Widen an argument span to include its comma and line layout."""
    ahead = end
    while ahead < len(text) and text[ahead] in " \t":
        ahead += 1
    if ahead < len(text) and text[ahead] == ",":
        stop = ahead + 1
        probe = stop
        while probe < len(text) and text[probe] in " \t":
            probe += 1
        if probe < len(text) and text[probe] == "\n":
            stop = probe + 1
            while stop < len(text) and text[stop] in " \t":
                stop += 1
        return (start, stop)
    behind = start
    while behind > 0 and text[behind - 1] in " \t":
        behind -= 1
    if behind > 0 and text[behind - 1] == ",":
        return (behind - 1, end)
    return (start, end)


def _strip_names_in_file(path: Path) -> list[str]:
    """Remove name/description from public patch declarations in a file.

    Returns the vals whose names were stripped. Private declarations
    (already dependency-only upstream) are left untouched.
    """
    text = path.read_text(encoding="utf-8")
    declarations = _find_patch_declarations(text)
    intervals: list[tuple[int, int]] = []
    stripped: list[str] = []
    for declaration in declarations:
        if not declaration.has_name or declaration.private:
            continue
        assert declaration.val is not None
        stripped.append(declaration.val)
        for arg_start, arg_end in declaration.removable_args:
            intervals.append(_excision_interval(text, arg_start, arg_end))
    if not intervals:
        return stripped
    new_text = text
    for start, end in sorted(intervals, reverse=True):
        new_text = new_text[:start] + new_text[end:]
    remaining = _find_patch_declarations(new_text)
    if len(remaining) != len(declarations):
        raise ValueError(f"Patch declaration count changed in {path}")
    for declaration in remaining:
        if declaration.has_name and not declaration.private:
            raise ValueError(
                f"Public named patch {declaration.val} survived stripping in {path}"
            )
    path.write_text(new_text, encoding="utf-8")
    return stripped


def _strip_names_under(roots: list[Path]) -> set[str]:
    stripped: set[str] = set()
    for root in roots:
        if not root.is_dir():
            raise FileNotFoundError(f"Patch source root missing: {root}")
        for kotlin_file in sorted(root.rglob("*.kt")):
            stripped.update(_strip_names_in_file(kotlin_file))
    return stripped


def _umbrella_dependencies(umbrella_file: Path) -> list[str]:
    text = umbrella_file.read_text(encoding="utf-8")
    match = re.search(r"dependsOn\((.*?)\)", text, re.S)
    if not match:
        raise ValueError(f"No dependsOn block in umbrella patch {umbrella_file}")
    return re.findall(r"[A-Za-z_]\w*", match.group(1))


# Patches that require a standard (non-mount) install when reached
# through a dependency closure -- mirrors upstream piko's
# SettingsAggregateValidationTest standardOnly set.
_STANDARD_ONLY_PATCHES = {
    "newXSettingsPatch",
    "newXSettingsResourcePatch",
    "downloaderManifestPatch",
    "clonePatch",
    "bringBackTwitterPatch",
}

# Tokens marking a patch builder as tied to the settings aggregate
# (and therefore to a standard install): the settings contribution DSL
# adds a dependency on the settings base patch at build time.
_SETTINGS_DSL_TOKENS = (
    "newXSettings(",
    "newXToggle(",
    "newXSingleChoice(",
    "newXMultiChoice(",
    "newXTextInput(",
    "contributeSettings(",
    "settingsToggle(",
    "newXPostOption(",
)

_TOP_LEVEL_DECL = re.compile(
    r"(?m)^(?:private\s+|internal\s+|public\s+)?(?:val|fun|object|class)\s+(\w+)"
)


def _val_regions(roots: list[Path]) -> dict[str, str]:
    """Map every top-level val name under roots to its source region.

    A region runs from the val's declaration to the next top-level
    declaration in the same file. Approximate, but sufficient for the
    mount-compatibility guard below (upstream's own JVM test in CI is
    the ground truth and runs before the patches list is generated).
    """
    regions: dict[str, str] = {}
    for root in roots:
        for kotlin_file in sorted(root.rglob("*.kt")):
            text = kotlin_file.read_text(encoding="utf-8")
            starts = list(_TOP_LEVEL_DECL.finditer(text))
            for index, match in enumerate(starts):
                end = (
                    starts[index + 1].start()
                    if index + 1 < len(starts)
                    else len(text)
                )
                regions.setdefault(match.group(1), text[match.start() : end])
    return regions


def _mount_compatible_subset(roots: list[Path], included: set[str]) -> set[str]:
    """Compute which included NewX patches are mount-compatible.

    Mirrors upstream's own classification: a patch is mount-compatible
    when it does not declare itself unavailable on mount, does not use
    the settings contribution DSL (which depends on the settings base
    patch), and its dependsOn closure reaches neither a
    standard-install-only patch nor a patch failing these checks.
    """
    regions = _val_regions(roots)
    graph: dict[str, list[str]] = {}
    region_dirty: dict[str, bool] = {}
    for val, region in regions.items():
        deps: list[str] = []
        for dep_match in re.finditer(r"dependsOn\s*\(", region):
            close_index, _ = _scan_parens(region, dep_match.end() - 1)
            deps += re.findall(r"[A-Za-z_]\w*", region[dep_match.end() : close_index])
        graph[val] = deps
        region_dirty[val] = (
            "unsupportedOnMount(" in region
            or any(token in region for token in _SETTINGS_DSL_TOKENS)
        )

    def closure_dirty(val: str, visited: set[str]) -> bool:
        if val in visited:
            return False
        visited.add(val)
        if val in _STANDARD_ONLY_PATCHES or region_dirty.get(val, False):
            return True
        return any(closure_dirty(dep, visited) for dep in graph.get(val, []))

    return {val for val in included if not closure_dirty(val, set())}


def apply_one_patch_per_app(piko_directory: Path) -> dict:
    """Strip feature patch names and inject the umbrella patches."""
    kotlin_root = piko_directory / "patches" / "src" / "main" / "kotlin"
    newx_root = kotlin_root / "app" / "crimera" / "patches" / "newx"
    plans = [
        (
            "x",
            [
                (
                    UMBRELLA_DIR / "NewXCombinedPatch.kt",
                    newx_root / "NewXCombinedPatch.kt",
                ),
                (
                    UMBRELLA_DIR / "NewXMountCombinedPatch.kt",
                    newx_root / "NewXMountCombinedPatch.kt",
                ),
            ],
            [kotlin_root / "app" / "crimera" / "patches"],
            {
                "clonePatch",
                "bringBackTwitterPatch",
                "newXAudioRenditionDiagnosticsPatch",
            },
        ),
        (
            "twitch",
            [
                (
                    UMBRELLA_DIR / "TwitchCombinedPatch.kt",
                    kotlin_root
                    / "dev" / "twitchpatches" / "patches" / "twitch"
                    / "TwitchCombinedPatch.kt",
                ),
            ],
            [kotlin_root / "dev"],
            {"inspectPlaybackPatch"},
        ),
    ]
    summary: dict = {}
    for side, umbrellas, roots, excluded in plans:
        if not excluded <= set(COMBINED_EXCLUDED_PATCHES):
            raise ValueError(
                f"Exclusions for {side} lack a documented reason: "
                f"{sorted(excluded - set(COMBINED_EXCLUDED_PATCHES))}"
            )
        manifests = {
            umbrella_file.stem: set(_umbrella_dependencies(umbrella_file))
            for umbrella_file, _ in umbrellas
        }
        manifest = set().union(*manifests.values())
        stripped = _strip_names_under(roots)
        expected = manifest | excluded
        if stripped != expected:
            missing = sorted(expected - stripped)
            unexpected = sorted(stripped - expected)
            raise ValueError(
                f"One-patch restructure mismatch for {side}: "
                f"declared upstream but not in umbrella/exclusions: {unexpected}; "
                f"in umbrella/exclusions but not declared upstream: {missing}. "
                "Update umbrella/*.kt or COMBINED_EXCLUDED_PATCHES consciously "
                "(see docs/UPSTREAM.md)."
            )
        entry: dict = {"stripped": len(stripped)}
        if side == "x":
            standard = manifests["NewXCombinedPatch"]
            mount = manifests["NewXMountCombinedPatch"]
            if not mount <= standard:
                raise ValueError(
                    "Mount umbrella must be a subset of the standard umbrella: "
                    f"{sorted(mount - standard)}"
                )
            computed_mount = _mount_compatible_subset(roots, standard)
            if computed_mount != mount:
                raise ValueError(
                    "Mount umbrella membership diverges from the computed "
                    f"mount-compatible subset: umbrella has {sorted(mount)}, "
                    f"computed {sorted(computed_mount)}. Review the new "
                    "patches and update umbrella/NewXMountCombinedPatch.kt "
                    "consciously (see docs/UPSTREAM.md)."
                )
            entry["umbrella"] = "NewXCombinedPatch"
            entry["included"] = len(standard)
            entry["mount_umbrella"] = "NewXMountCombinedPatch"
            entry["mount_included"] = len(mount)
        else:
            entry["umbrella"] = umbrellas[0][0].stem
            entry["included"] = len(manifest)
        for umbrella_file, destination in umbrellas:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(umbrella_file, destination)
        summary[side] = entry
        print(
            f"One patch per app ({side}): stripped names from "
            f"{len(stripped)} feature patches, umbrellas depend on "
            f"{len(manifest)} of them"
        )
    summary["excluded"] = sorted(COMBINED_EXCLUDED_PATCHES)
    return summary


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
    one_patch_per_app: dict = field(default_factory=dict)


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
        one_patch_per_app = apply_one_patch_per_app(piko_directory)
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
        one_patch_per_app=one_patch_per_app,
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
        "one_patch_per_app": result.one_patch_per_app,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
