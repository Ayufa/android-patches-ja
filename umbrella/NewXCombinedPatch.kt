package app.crimera.patches.newx

import app.crimera.patches.newx.utils.Constants.COMPATIBILITY_NEW_X
import app.crimera.patches.newx.utils.unsupportedOnMount
import app.morphe.patcher.patch.bytecodePatch
import app.crimera.patches.newx.ads.newXHideAdsPatch
import app.crimera.patches.newx.misc.blur.newXDisableBlurPatch
import app.crimera.patches.newx.misc.browseobject.newXBrowseObjectPatch
import app.crimera.patches.newx.misc.canonicalurls.newXCanonicalUrlsPatch
import app.crimera.patches.newx.misc.crashlogs.newXCrashLogsPatch
import app.crimera.patches.newx.misc.customfont.customFontPatch
import app.crimera.patches.newx.misc.customsharingdomain.newXCustomSharingDomainPatch
import app.crimera.patches.newx.misc.customsharingdomain.newXPermanentShareLinksPatch
import app.crimera.patches.newx.misc.customsharingdomain.newXRemoveShareTrackingQueryPatch
import app.crimera.patches.newx.misc.drawer.customizeNewXDrawerPatch
import app.crimera.patches.newx.misc.dynamiccolor.dynamicColorPatch
import app.crimera.patches.newx.misc.featureflags.featureFlagPatch
import app.crimera.patches.newx.misc.featureflags.newXQualityOfLifeFeatureFlagsPatch
import app.crimera.patches.newx.misc.inlineactions.customizeNewXInlineActionsPatch
import app.crimera.patches.newx.misc.inlineactions.newXInlineDownloadButtonPatch
import app.crimera.patches.newx.misc.inlineactions.newXNativeDownloadRedirectPatch
import app.crimera.patches.newx.misc.mediasheet.customizeNewXMediaSheetPatch
import app.crimera.patches.newx.misc.mediatab.newXDefaultMediaTabPatch
import app.crimera.patches.newx.misc.mediatab.newXProfilePhotosGalleryPatch
import app.crimera.patches.newx.misc.navbar.customizeNewXNavBarPatch
import app.crimera.patches.newx.misc.postdetails.newXHidePostDetailAuthorActionsPatch
import app.crimera.patches.newx.misc.postdetails.newXHidePostReplyBarPatch
import app.crimera.patches.newx.misc.postoptions.customizeNewXPostOptionsPatch
import app.crimera.patches.newx.misc.profilesorting.newXDefaultProfilePostSortingPatch
import app.crimera.patches.newx.misc.profiletabs.customizeNewXProfileTabsPatch
import app.crimera.patches.newx.misc.replysorting.newXDefaultReplySortingPatch
import app.crimera.patches.newx.misc.serverlogging.newXServerLoggingPatch
import app.crimera.patches.newx.misc.videoscrolling.newXDisableVideoScrollingPatch
import app.crimera.patches.newx.premium.hidePremiumUpsellPatch
import app.crimera.patches.newx.premium.newXDownloadPatch
import app.crimera.patches.newx.premium.newXUnlockColorCustomizationPatch
import app.crimera.patches.newx.timeline.customizeNewXTimelineTabsPatch
import app.crimera.patches.newx.timeline.disableTimelineRefreshPatch
import app.crimera.patches.newx.timeline.hideNewPostButtonPatch
import app.crimera.patches.newx.timeline.hideNewPostPillPatch
import app.crimera.patches.newx.timeline.newXForYouTopicFilterPatch
import app.crimera.patches.newx.timeline.newXHideAiGeneratedPostsPatch
import app.crimera.patches.newx.timeline.newXHideDiscoverMorePatch
import app.crimera.patches.newx.timeline.newXHidePostDividersPatch
import app.crimera.patches.newx.timeline.newXHideSpacesBarPatch
import app.crimera.patches.newx.timeline.newXHideTimelineTabsBarPatch
import app.crimera.patches.newx.timeline.newXHideWhoToFollowPatch
import app.crimera.patches.newx.timeline.newXShowPollResultsPatch
import app.crimera.patches.newx.timeline.newXShowSensitiveMediaPatch
import app.crimera.patches.newx.timeline.restorePinnedHomeTabPatch
import app.crimera.patches.newx.timeline.restoreTimelinePositionPatch
import app.crimera.patches.newx.timeline.postfilter.newXHideVerifiedPostsPatch
import app.crimera.patches.newx.timeline.postfilter.postFilterPatch
import app.crimera.patches.newx.translation.newXTranslatorPatch

/**
 * Android Patches JA: combined NewX patch.
 *
 * Morphe lists only named patches, so this single named patch pulls in the
 * whole NewX feature set as dependencies. build_combined.py strips the
 * `name`/`description` arguments from every feature patch declaration at
 * build time (making them dependency-only) and copies this file into the
 * build tree. Per-feature on/off lives in the NewX settings screen, which
 * the included patches register their toggles into.
 *
 * The dependsOn list is the manifest of included feature patches:
 * build_combined.py fails the build if the set of named upstream patches
 * differs from this list plus the documented exclusions, so a new upstream
 * patch can never be silently dropped. See docs/UPSTREAM.md.
 *
 * X ships a second umbrella, NewXMountCombinedPatch, with the small
 * mount-compatible subset: upstream's validation requires the selectable
 * set to keep a mount-compatible patch, and this umbrella's feature set
 * (settings screen included) requires a standard install.
 */
@Suppress("unused")
val newXCombinedPatch =
    bytecodePatch(
        name = "X（NewX）日本語化パッチ",
        description = "NewX の全機能パッチをまとめて適用します。個別機能のオン・オフは、適用後の X アプリ内「NewX 設定」画面で行えます。",
        default = true,
    ) {
        // The feature set needs the settings screen and other
        // standard-install-only pieces, so -- exactly like the upstream
        // feature patches themselves -- this umbrella is unavailable
        // on mount installs. Mount installs use newXMountCombinedPatch.
        unsupportedOnMount(default = true)
        compatibleWith(COMPATIBILITY_NEW_X)

        dependsOn(
            newXHideAdsPatch,
            newXDisableBlurPatch,
            newXBrowseObjectPatch,
            newXCanonicalUrlsPatch,
            newXCrashLogsPatch,
            customFontPatch,
            newXCustomSharingDomainPatch,
            newXPermanentShareLinksPatch,
            newXRemoveShareTrackingQueryPatch,
            customizeNewXDrawerPatch,
            dynamicColorPatch,
            featureFlagPatch,
            newXQualityOfLifeFeatureFlagsPatch,
            customizeNewXInlineActionsPatch,
            newXInlineDownloadButtonPatch,
            newXNativeDownloadRedirectPatch,
            customizeNewXMediaSheetPatch,
            newXDefaultMediaTabPatch,
            newXProfilePhotosGalleryPatch,
            customizeNewXNavBarPatch,
            newXHidePostDetailAuthorActionsPatch,
            newXHidePostReplyBarPatch,
            customizeNewXPostOptionsPatch,
            newXDefaultProfilePostSortingPatch,
            customizeNewXProfileTabsPatch,
            newXDefaultReplySortingPatch,
            newXServerLoggingPatch,
            newXDisableVideoScrollingPatch,
            hidePremiumUpsellPatch,
            newXUnlockColorCustomizationPatch,
            newXDownloadPatch,
            customizeNewXTimelineTabsPatch,
            disableTimelineRefreshPatch,
            newXForYouTopicFilterPatch,
            newXHideAiGeneratedPostsPatch,
            newXHideDiscoverMorePatch,
            hideNewPostButtonPatch,
            hideNewPostPillPatch,
            newXHidePostDividersPatch,
            newXHideSpacesBarPatch,
            newXHideTimelineTabsBarPatch,
            newXHideWhoToFollowPatch,
            restorePinnedHomeTabPatch,
            restoreTimelinePositionPatch,
            newXShowPollResultsPatch,
            newXShowSensitiveMediaPatch,
            newXHideVerifiedPostsPatch,
            postFilterPatch,
            newXTranslatorPatch,
        )

        execute {
        }
    }
