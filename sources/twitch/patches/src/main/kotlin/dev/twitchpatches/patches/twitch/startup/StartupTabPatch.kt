package dev.twitchpatches.patches.twitch.startup

import app.morphe.patcher.extensions.InstructionExtensions.addInstructionsWithLabels
import app.morphe.patcher.patch.BytecodePatchContext
import app.morphe.patcher.patch.PatchException
import app.morphe.patcher.patch.bytecodePatch
import app.morphe.patcher.util.proxy.mutableTypes.MutableMethod.Companion.toMutable
import com.android.tools.smali.dexlib2.AccessFlags
import com.android.tools.smali.dexlib2.Opcode
import com.android.tools.smali.dexlib2.builder.MutableMethodImplementation
import com.android.tools.smali.dexlib2.iface.Method
import com.android.tools.smali.dexlib2.iface.instruction.FiveRegisterInstruction
import com.android.tools.smali.dexlib2.iface.instruction.ReferenceInstruction
import com.android.tools.smali.dexlib2.iface.instruction.RegisterRangeInstruction
import com.android.tools.smali.dexlib2.immutable.ImmutableMethod
import com.android.tools.smali.dexlib2.immutable.ImmutableMethodParameter
import dev.twitchpatches.patches.twitch.settings.settingsPatch
import dev.twitchpatches.patches.twitch.shared.TwitchTarget
import dev.twitchpatches.patches.twitch.shared.code
import dev.twitchpatches.patches.twitch.shared.insertAtReturn
import dev.twitchpatches.patches.twitch.shared.isInstance
import dev.twitchpatches.patches.twitch.shared.reference
import dev.twitchpatches.patches.twitch.shared.uniqueHook

private const val SETTINGS = "Ldev/twitchpatches/extension/startup/StartupTabSettings;"
private const val HOST = "Ltv/twitch/android/feature/discovery/feed/tab/Hilt_DiscoveryFeedHomeFragment;"
private const val PAGE = "Ltv/twitch/android/models/feed/DiscoveryFeedPage;"
private const val LOCATION = "Ltv/twitch/android/models/feed/FeedLocation;"
private const val LOCATION_PAGE = $$"Ltv/twitch/android/models/feed/DiscoveryFeedPage$FeedLocationPage;"
private const val FOLLOWING_PAGE = $$"Ltv/twitch/android/models/feed/DiscoveryFeedPage$FollowingPage;"
private const val LIVE_LOCATION = $$"Ltv/twitch/android/models/feed/FeedLocation$Live;"
private const val CLIPS_LOCATION = $$"Ltv/twitch/android/models/feed/FeedLocation$Clips;"
private const val BRIDGE_NAME = "twitchPatchesStartupPage"

/**
 * Finds the one place where the home fragment injection builds Twitch's
 * default page, a FeedLocationPage around the Live location, used only when
 * no explicit page was supplied. Returns the constructor call's instruction
 * index and the register holding the constructed page.
 */
internal fun findDefaultPageConstruction(method: Method): Pair<Int, Int> {
    if (method.name != "inject" || !method.isInstance(emptyList(), "V"))
        throw PatchException("Startup tab: home injection must be a no-arg void instance method")
    val code = method.code()
    val constructions = code.withIndex().filter { (_, instruction) ->
        instruction.opcode == Opcode.NEW_INSTANCE &&
            (instruction as? ReferenceInstruction)?.reference?.toString() == LOCATION_PAGE
    }
    if (constructions.size != 1)
        throw PatchException("Startup tab: expected one default page construction, found ${constructions.size}")
    val start = constructions.single().index
    val window = code.subList(start + 1, minOf(code.size, start + 5))
    val liveOffset = window.indexOfFirst { instruction ->
        instruction.opcode == Opcode.SGET_OBJECT &&
            (instruction as? ReferenceInstruction)?.reference?.toString() == "$LIVE_LOCATION->INSTANCE:$LIVE_LOCATION"
    }
    if (liveOffset < 0) throw PatchException("Startup tab: default page no longer uses the Live location")
    val initOffset = window.withIndex().firstOrNull { (offset, instruction) ->
        offset > liveOffset && instruction.opcode == Opcode.INVOKE_DIRECT &&
            (instruction as? ReferenceInstruction)?.reference?.toString() == "$LOCATION_PAGE-><init>($LOCATION)V"
    } ?: throw PatchException("Startup tab: default page constructor call missing")
    val initIndex = start + 1 + initOffset.index
    val register = when (val invoke = code[initIndex]) {
        is FiveRegisterInstruction -> invoke.registerC
        is RegisterRangeInstruction -> invoke.startRegister
        else -> throw PatchException("Startup tab: default page constructor uses an unsupported invocation")
    }
    if (register !in 0..255) throw PatchException("Startup tab: default page register out of range")
    return initIndex to register
}

@Suppress("unused")
val startupTabPatch = bytecodePatch(
    name = "Ayufa: Startup tab",
    description = "Ayufaのカスタムパッチ。アプリ起動時に最初に開くタブ（フォロー／ライブ／クリップ）を、パッチ設定で選べるようにします。",
    default = false,
) {
    compatibleWith(TwitchTarget.compatibility)
    dependsOn(settingsPatch)
    execute {
        val inject = classDefBy(HOST).methods.filter { it.name == "inject" && it.isInstance(emptyList(), "V") }
            .uniqueHook("startup tab home injection")
        val (initIndex, register) = findDefaultPageConstruction(inject)
        val bridge = startupBridge()
        // The construction sits inside the null guard for the supplied page:
        // inserting here runs the bridge only for Twitch's own default, and
        // the guard branch keeps landing on the following instruction.
        val method = mutableClassDefBy(HOST).methods.single { it.reference == inject.reference }
        method.addInstructionsWithLabels(initIndex + 1, """
            invoke-static {v$register}, $bridge
            move-result-object v$register
        """)
        val application = classDefBy("Ltv/twitch/android/app/consumer/TwitchApplication;").methods.filter {
            it.name == "onCreate" && it.isInstance(emptyList(), "V")
        }.uniqueHook("startup tab settings initialization")
        val app = mutableClassDefBy(application.definingClass).methods.single { it.reference == application.reference }
        app.code().withIndex().filter { it.value.opcode == Opcode.RETURN_VOID }.map { it.index }.asReversed().forEach {
            app.insertAtReturn(it, "invoke-static/range {p0 .. p0}, $SETTINGS->initialize(Landroid/app/Application;)V")
        }
    }
}

private fun BytecodePatchContext.startupBridge(): String {
    val type = mutableClassDefBy(HOST)
    if (type.methods.any { it.name == BRIDGE_NAME }) throw PatchException("Startup tab bridge already exists")
    val method = ImmutableMethod(HOST, BRIDGE_NAME, listOf(ImmutableMethodParameter(PAGE, null, null)), PAGE,
        AccessFlags.PUBLIC.value or AccessFlags.STATIC.value or AccessFlags.SYNTHETIC.value, null, null,
        MutableMethodImplementation(3)).toMutable()
    method.addInstructionsWithLabels(0, """
        invoke-static {}, $SETTINGS->selectedTab()I
        move-result v0
        const/4 v1, 0x0
        if-ne v0, v1, :not_following
        sget-object v0, $FOLLOWING_PAGE->INSTANCE:$FOLLOWING_PAGE
        return-object v0
        :not_following
        const/4 v1, 0x2
        if-ne v0, v1, :original
        new-instance v0, $LOCATION_PAGE
        sget-object v1, $CLIPS_LOCATION->INSTANCE:$CLIPS_LOCATION
        invoke-direct {v0, v1}, $LOCATION_PAGE-><init>($LOCATION)V
        return-object v0
        :original
        return-object p0
    """)
    type.methods.add(method)
    return method.reference
}
