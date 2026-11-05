package ai.flochat.companion

import android.app.AlertDialog
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.provider.Settings
import android.text.InputFilter
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.*
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class OverlayService : Service() {
    private val handler = Handler(Looper.getMainLooper())
    private val operations = Executors.newSingleThreadExecutor()
    private val heartbeat = Executors.newSingleThreadScheduledExecutor()
    private lateinit var bridge: Bridge
    private lateinit var windowManager: WindowManager
    private lateinit var panel: LinearLayout
    private lateinit var status: TextView
    private lateinit var editor: EditText
    private lateinit var drafts: Spinner
    private val draftIds = ArrayList<String>()
    private var review: AlertDialog? = null
    private var alive = false
    private var busy = false
    private var savedText = ""
    private var reviewObservedAt = 0.0
    @Volatile private var uiGeneration = 0L

    private fun action(command: String, args: JSONObject = JSONObject(), then: (Any) -> Unit = { status.text = it.toString() }) {
        if (busy && command !in listOf("stop", "cancel")) return
        val generation = ++uiGeneration
        val executor = if (command in listOf("stop", "cancel")) heartbeat else operations
        if (command !in listOf("stop", "cancel")) busy = true
        executor.execute {
            try {
                val result = bridge.call(command, args)
                handler.post { if (alive) { if (command !in listOf("stop", "cancel")) busy = false; if (generation == uiGeneration || command == "confirm") {
                    reviewObservedAt = maxOf(reviewObservedAt, (result as? JSONObject)?.optDouble("observed_at", 0.0) ?: 0.0)
                    then(result)
                } } }
            } catch (failure: Exception) {
                val safeReason = if (failure is CoreRejected) failure.message else null
                handler.post { if (alive) { if (command !in listOf("stop", "cancel")) busy = false
                    if (generation != uiGeneration && command != "confirm") return@post
                    review?.dismiss(); review = null
                    status.text = safeReason ?: "Core disconnected or action rejected. No automatic retry. A confirmation may have reached the core: inspect history/chat. Open Termux to recover/re-pair; fresh approval is mandatory." } }
            }
        }
    }
    private fun startControls() {
        if (!Settings.canDrawOverlays(this)) { stopSelf(); return }
        val notifications = getSystemService(NotificationManager::class.java)
        notifications.createNotificationChannel(NotificationChannel("controls", "FloChat availability", NotificationManager.IMPORTANCE_LOW))
        val setup = PendingIntent.getActivity(this, 0, Intent(this, SetupActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, 1, Intent(this, OverlayService::class.java).setAction("stop"), PendingIntent.FLAG_IMMUTABLE)
        startForeground(1, Notification.Builder(this, "controls").setContentTitle("FloChat controls available")
            .setContentText("Explicit approval only · Android can terminate availability")
            .setSmallIcon(android.R.drawable.ic_dialog_info).setContentIntent(setup)
            .addAction(Notification.Action.Builder(null, "Stop controls", stop).build()).build())
        alive = true; bridge = Bridge(this); windowManager = getSystemService(WindowManager::class.java)
        panel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(18, 14, 18, 14); setBackgroundColor(Color.rgb(246, 247, 249)) }
        val width = minOf(resources.displayMetrics.widthPixels - 24, (360 * resources.displayMetrics.density).toInt())
        val params = WindowManager.LayoutParams(width, WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or WindowManager.LayoutParams.FLAG_SECURE, PixelFormat.TRANSLUCENT)
        val header = TextView(this).apply { text = "FloChat · drag here"; textSize = 19f; setTextColor(Color.BLACK) }
        var originX = 0; var originY = 0; var touchX = 0f; var touchY = 0f
        header.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> { originX = params.x; originY = params.y; touchX = event.rawX; touchY = event.rawY; true }
                MotionEvent.ACTION_MOVE -> { params.x = originX + (event.rawX - touchX).toInt(); params.y = originY + (event.rawY - touchY).toInt(); windowManager.updateViewLayout(panel, params); true }
                else -> false
            }
        }
        panel.addView(header)
        val contents = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val scroll = ScrollView(this).apply { addView(contents) }
        panel.addView(scroll, LinearLayout.LayoutParams(-1, minOf((440 * resources.displayMetrics.density).toInt(), resources.displayMetrics.heightPixels / 2)))
        fun button(label: String, operation: () -> Unit) { contents.addView(Button(this).apply { text = label; setOnClickListener { operation() } }) }
        status = TextView(this).apply { text = "Connecting to local core…" }; contents.addView(status)
        editor = EditText(this).apply { hint = "Local comment editor"; minLines = 2; maxLines = 4; filters = arrayOf(InputFilter.LengthFilter(64000)) }; contents.addView(editor)
        button("Save editor") { if (!editor.isEnabled) status.text = "Oversized editor is read-only. Use Termux to edit the full text." else action("edit", JSONObject().put("text", editor.text.toString())) { savedText = (it as JSONObject).getString("text"); editor.isEnabled = !it.optBoolean("truncated"); editor.setText(savedText) } }
        drafts = Spinner(this); contents.addView(drafts)
        button("Refresh drafts") { action("drafts") { value ->
            val list = value as JSONArray; draftIds.clear(); val labels = ArrayList<String>()
            for (i in 0 until list.length()) { val item = list.getJSONObject(i); draftIds.add(item.getString("id")); labels.add(item.getString("title")) }
            drafts.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, labels)
        } }
        button("Open selected draft") { draftIds.getOrNull(drafts.selectedItemPosition)?.let { id -> action("draft", JSONObject().put("id", id)) { savedText = (it as JSONObject).getString("text"); editor.isEnabled = !it.optBoolean("truncated"); editor.setText(savedText) } } }
        button("Local preview") { action("preview") { status.text = it.toString() } }
        for (name in listOf("start", "pause", "resume", "stop", "recover")) button(name.replaceFirstChar { it.uppercase() }) { action(name) }
        button("Review ONE submission") { if (editor.text.toString() != savedText) status.text = "Save editor changes before requesting a core review." else action("prepare") { showReview(it as JSONObject) } }
        button("Cancel review") { review?.dismiss(); review = null; action("cancel") }
        panel.addView(Button(this).apply { text = "Collapse / expand"; setOnClickListener { scroll.visibility = if (scroll.visibility == View.VISIBLE) View.GONE else View.VISIBLE } })
        button("Open Termux") {
            val terminal = packageManager.getLaunchIntentForPackage("com.termux")
            if (terminal == null) status.text = "Open Termux manually; no visible launch intent is available."
            else try { startActivity(terminal.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
            catch (_: Exception) { status.text = "Android refused opening Termux. Open it manually." }
        }
        button("Close controls") { stopSelf() }
        windowManager.addView(panel, params)
        action("attach") { value -> savedText = (value as JSONObject).getJSONObject("editor").getString("text"); editor.isEnabled = !value.getJSONObject("editor").optBoolean("truncated"); editor.setText(savedText) }
        heartbeat.scheduleWithFixedDelay({
            val generation = uiGeneration
            try {
                val snapshot = bridge.call("status") as JSONObject
                handler.post { if (alive && generation == uiGeneration && snapshot.getDouble("observed_at") >= reviewObservedAt) {
                    status.text = "${snapshot.getString("availability")} · ${snapshot.getJSONObject("safety").getString("session")}\n${snapshot.optJSONObject("selection")}\n${snapshot.getJSONObject("connection")}\nCooldown: ${snapshot.getJSONObject("safety").opt("cooldown_remaining")}s"
                    val remoteEditor = snapshot.getJSONObject("editor")
                    val remoteText = remoteEditor.getString("text")
                    if (editor.text.toString() == savedText && !editor.hasFocus()) {
                        savedText = remoteText; editor.isEnabled = !remoteEditor.optBoolean("truncated"); editor.setText(savedText)
                    } else if (remoteText != savedText) {
                        status.append("\nEditor changed elsewhere. Saving replaces it; review uses the current core text.")
                    }
                    if (!snapshot.getBoolean("owns_review") || !snapshot.getJSONObject("safety").getBoolean("approval_pending")) { review?.dismiss(); review = null }
                } }
            } catch (_: Exception) { handler.post { if (alive && generation == uiGeneration) { review?.dismiss(); review = null; status.text = "Core disconnected. No active connection or recoverable approval. Reopen Termux; never retry an uncertain confirmation." } } }
        }, 3, 3, TimeUnit.SECONDS)
    }
    private fun showReview(view: JSONObject) {
        reviewObservedAt = maxOf(reviewObservedAt, view.getDouble("observed_at"))
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(20, 16, 20, 16) }
        val exact = TextView(this).apply { text = view.toString(2) + "\nExact text:\n" + view.getString("text"); setTextIsSelectable(true) }
        val scroll = ScrollView(this).apply { addView(exact) }; layout.addView(scroll, LinearLayout.LayoutParams(-1, 450))
        val phrase = EditText(this).apply { hint = "SEND " + view.getString("approval_id") }; layout.addView(phrase)
        var consumed = false
        val dialog = AlertDialog.Builder(this).setTitle("Approve ONE exact comment").setView(layout)
            .setPositiveButton("Confirm this one attempt", null).setNegativeButton("Cancel", null).create()
        dialog.window?.setType(WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY)
        dialog.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        dialog.setCanceledOnTouchOutside(false)
        dialog.setOnDismissListener { if (!consumed && alive) action("cancel") }
        review = dialog; dialog.show()
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
            if (phrase.text.toString() != "SEND " + view.getString("approval_id")) {
                phrase.error = "Type the displayed exact one-use phrase"; return@setOnClickListener
            }
            consumed = true; review = null; dialog.dismiss()
            action("confirm", JSONObject().put("approval_id", view.getString("approval_id")).put("phrase", phrase.text.toString()))
        }
        handler.postDelayed({ if (review === dialog) { dialog.dismiss(); review = null } }, maxOf(1L, (view.getDouble("expires_in_seconds") * 1000).toLong()))
    }
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "stop") stopSelf()
        else if (!alive) try { startControls() } catch (_: Exception) { stopSelf() }
        return START_NOT_STICKY
    }
    override fun onDestroy() {
        alive = false; review?.dismiss(); review = null
        heartbeat.shutdownNow(); operations.shutdownNow()
        if (::bridge.isInitialized) Thread {
            try { runCatching { bridge.call("detach") } } finally { bridge.close() }
        }.start()
        if (::panel.isInitialized) runCatching { windowManager.removeView(panel) }
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }
    override fun onBind(intent: Intent?): IBinder? = null
}
