package ai.flochat.companion

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.WindowManager
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView

class SetupActivity : Activity() {
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        val layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(28, 32, 28, 32) }
        val status = TextView(this).apply {
            text = "FloChat · Termux companion\nStart the core in Termux with flochat panel start --core-only --mode persistent, then panel pair. Enter that local capability below. This is not Google login.\n\nOverlay permission lets this panel appear over apps; Android may hide or terminate it. A visible foreground notification is required. No accessibility permission or automatic posting.\n\nTermux OAuth/secure vault support remains blocked; local editing can still work."
        }
        val code = EditText(this).apply { hint = "fc1:port:instance:local capability"; inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD }
        fun button(text: String, action: () -> Unit) { layout.addView(Button(this).apply { this.text = text; setOnClickListener { action() } }) }
        layout.addView(status); layout.addView(code)
        button("Store pairing in Android Keystore") {
            try { Bridge(this).pair(code.text.toString()); code.text.clear(); status.text = "Paired locally. Grant overlay/notifications, then explicitly start. Re-pair after a core restart." }
            catch (_: Exception) { status.text = "Pairing/storage failed. No plaintext fallback. Check the current pairing code." }
        }
        button("Explain / grant overlay permission") {
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
        }
        button("Grant notification permission") {
            if (Build.VERSION.SDK_INT >= 33) requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
        button("Start floating controls") {
            if (!Settings.canDrawOverlays(this)) status.text = "Overlay permission is not granted. Nothing started."
            else if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
                status.text = "Notification permission is required for FloChat's visible background indicator."
            else try { startForegroundService(Intent(this, OverlayService::class.java)) }
            catch (_: Exception) { status.text = "Android refused foreground start. Keep this activity visible and inspect OS restrictions." }
        }
        button("Stop floating controls") { stopService(Intent(this, OverlayService::class.java)) }
        setContentView(layout)
    }
}
