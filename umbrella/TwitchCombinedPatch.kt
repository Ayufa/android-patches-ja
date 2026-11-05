package dev.twitchpatches.patches.twitch

import app.morphe.patcher.patch.bytecodePatch
import dev.twitchpatches.patches.twitch.shared.TwitchTarget
import dev.twitchpatches.patches.twitch.ads.blockClientAdsPatch
import dev.twitchpatches.patches.twitch.ads.blockStitchedAdsPatch
import dev.twitchpatches.patches.twitch.ads.hideDisplayAdsPatch
import dev.twitchpatches.patches.twitch.channelpoints.autoClaimChannelPointsPatch
import dev.twitchpatches.patches.twitch.chat.showDeletedMessagesPatch
import dev.twitchpatches.patches.twitch.diagnostics.inspectBaselinePatch
import dev.twitchpatches.patches.twitch.emotes.favoriteEmotesPatch
import dev.twitchpatches.patches.twitch.emotes.thirdPartyEmotesPatch
import dev.twitchpatches.patches.twitch.promotions.hideSubscriptionBannersPatch
import dev.twitchpatches.patches.twitch.promotions.hideTurboPromotionsPatch
import dev.twitchpatches.patches.twitch.reload.reloadStreamPatch
import dev.twitchpatches.patches.twitch.ui.uiSettingsPatch

/**
 * Android Patches JA: combined Twitch patch.
 *
 * Morphe lists only named patches, so this single named patch pulls in the
 * whole Twitch feature set as dependencies. build_combined.py strips the
 * `name`/`description` arguments from every feature patch declaration at
 * build time (making them dependency-only) and copies this file into the
 * build tree. Per-feature on/off lives in the Twitch "パッチ設定" screen.
 *
 * The dependsOn list is the manifest of included feature patches:
 * build_combined.py fails the build if the set of named upstream patches
 * differs from this list plus the documented exclusions, so a new upstream
 * patch can never be silently dropped. See docs/UPSTREAM.md.
 */
@Suppress("unused")
val twitchCombinedPatch =
    bytecodePatch(
        name = "Twitch 日本語化パッチ",
        description = "Twitch 用の全機能パッチをまとめて適用します。個別機能のオン・オフは、適用後の Twitch アプリ内「パッチ設定」画面で行えます。",
        default = true,
    ) {
        compatibleWith(TwitchTarget.compatibility)

        dependsOn(
            blockClientAdsPatch,
            hideDisplayAdsPatch,
            blockStitchedAdsPatch,
            autoClaimChannelPointsPatch,
            showDeletedMessagesPatch,
            inspectBaselinePatch,
            favoriteEmotesPatch,
            thirdPartyEmotesPatch,
            hideSubscriptionBannersPatch,
            hideTurboPromotionsPatch,
            reloadStreamPatch,
            uiSettingsPatch,
        )

        execute {
        }
    }
