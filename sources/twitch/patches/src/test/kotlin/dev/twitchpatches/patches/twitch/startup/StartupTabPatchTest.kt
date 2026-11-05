package dev.twitchpatches.patches.twitch.startup

import app.morphe.patcher.extensions.InstructionExtensions.addInstructionsWithLabels
import app.morphe.patcher.patch.PatchException
import app.morphe.patcher.util.proxy.mutableTypes.MutableMethod.Companion.toMutable
import com.android.tools.smali.dexlib2.AccessFlags
import com.android.tools.smali.dexlib2.builder.MutableMethodImplementation
import com.android.tools.smali.dexlib2.immutable.ImmutableMethod
import com.android.tools.smali.dexlib2.immutable.ImmutableMethodParameter
import org.junit.Assert.assertEquals
import org.junit.Test

class StartupTabPatchTest {
    private fun inject(body: String) =
        ImmutableMethod("Lsynthetic/Hilt;", "inject", emptyList<ImmutableMethodParameter>(), "V",
            AccessFlags.PUBLIC.value or AccessFlags.FINAL.value, null, null,
            MutableMethodImplementation(4)).toMutable().apply {
            addInstructionsWithLabels(0, body)
        }

    private fun guarded(location: String, extraConstruction: String = "") = """
        const/4 v1, 0x0
        if-nez v1, :skip
        new-instance v1, Ltv/twitch/android/models/feed/DiscoveryFeedPage${'$'}FeedLocationPage;
        sget-object v2, Ltv/twitch/android/models/feed/FeedLocation${'$'}$location;->INSTANCE:Ltv/twitch/android/models/feed/FeedLocation${'$'}$location;
        invoke-direct {v1, v2}, Ltv/twitch/android/models/feed/DiscoveryFeedPage${'$'}FeedLocationPage;-><init>(Ltv/twitch/android/models/feed/FeedLocation;)V
        $extraConstruction
        :skip
        return-void
    """

    @Test fun findsTheLiveDefaultConstruction() {
        val (index, register) = findDefaultPageConstruction(inject(guarded("Live")))
        assertEquals(4, index)
        assertEquals(1, register)
    }

    @Test(expected = PatchException::class) fun rejectsANonLiveDefault() {
        findDefaultPageConstruction(inject(guarded("Clips")))
    }

    @Test(expected = PatchException::class) fun rejectsTwoDefaultConstructions() {
        val extra = """
            new-instance v1, Ltv/twitch/android/models/feed/DiscoveryFeedPage${'$'}FeedLocationPage;
        """
        findDefaultPageConstruction(inject(guarded("Live", extra)))
    }

    @Test(expected = PatchException::class) fun rejectsAMissingConstruction() {
        findDefaultPageConstruction(inject("""
            const/4 v1, 0x0
            return-void
        """))
    }
}
