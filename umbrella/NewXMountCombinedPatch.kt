package app.crimera.patches.newx

import app.crimera.patches.newx.premium.newXDownloadPatch
import app.crimera.patches.newx.premium.newXUnlockColorCustomizationPatch
import app.crimera.patches.newx.utils.Constants.COMPATIBILITY_NEW_X
import app.morphe.patcher.patch.bytecodePatch

/**
 * Android Patches JA: combined NewX patch for MOUNT installs.
 *
 * Mount installs retain the stock manifest, so patches that need the
 * NewX settings screen, added components or a package change cannot be
 * used there. Upstream marks those patches unavailable on mount
 * (unsupportedOnMount), and its own validation test
 * (SettingsAggregateValidationTest) requires the selectable patch set
 * to keep at least one mount-compatible patch -- which is why X ships
 * this second umbrella next to the standard one. It contains exactly
 * the NewX feature patches that upstream itself keeps available on
 * mount installs (no settings contribution, no standard-install-only
 * dependency). On a standard install, use newXCombinedPatch instead;
 * selecting both is harmless because shared patches run only once.
 *
 * build_combined.py verifies this dependsOn list against the rule
 * above and fails the build if they diverge. See docs/UPSTREAM.md.
 */
@Suppress("unused")
val newXMountCombinedPatch =
    bytecodePatch(
        name = "X（NewX）日本語化パッチ（マウント用）",
        description = "マウントインストール専用です。設定画面など標準インストールが必要な機能を除いた NewX パッチ（ダウンロード解放・色カスタマイズ解放）を適用します。通常のインストールでは「X（NewX）日本語化パッチ」を選んでください。",
        default = true,
    ) {
        compatibleWith(COMPATIBILITY_NEW_X)

        dependsOn(
            newXDownloadPatch,
            newXUnlockColorCustomizationPatch,
        )

        execute {
        }
    }
