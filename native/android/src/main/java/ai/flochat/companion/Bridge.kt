package ai.flochat.companion

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.net.InetSocketAddress
import java.net.Socket
import java.security.KeyStore
import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.Mac
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

class CoreRejected(message: String) : Exception(message)

// A local capability only. NEVER Google credentials; no arbitrary remote host or write API.
class Bridge(private val context: Context) {
    private val alias = "flochat-local-ipc"
    private val client = hex(random(16))
    private val sockets = mutableSetOf<Socket>()
    private var closed = false
    fun close() {
        synchronized(sockets) {
            closed = true
            sockets.forEach { runCatching { it.close() } }
            sockets.clear()
        }
    }
    private fun random(size: Int) = ByteArray(size).also { SecureRandom().nextBytes(it) }
    private fun hex(bytes: ByteArray) = bytes.joinToString("") { "%02x".format(it.toInt() and 255) }
    private fun unhex(value: String): ByteArray {
        require(value.matches(Regex("[0-9a-f]{64}")))
        return value.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
    }
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(alias, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    fun pair(code: String) {
        val parts = code.trim().split(":")
        require(parts.size == 4 && parts[0] == "fc1")
        require(parts[1].toInt() in 1024..65535)
        require(parts[2].matches(Regex("[0-9a-f-]{36}")))
        unhex(parts[3])
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        val encrypted = cipher.doFinal(code.trim().toByteArray(Charsets.UTF_8))
        context.getSharedPreferences("ipc", Context.MODE_PRIVATE).edit()
            .putString("iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .putString("ciphertext", Base64.encodeToString(encrypted, Base64.NO_WRAP)).apply()
    }
    private fun pairing(): List<String> {
        val preferences = context.getSharedPreferences("ipc", Context.MODE_PRIVATE)
        val iv = Base64.decode(preferences.getString("iv", null) ?: error("Pair first"), Base64.NO_WRAP)
        val ciphertext = Base64.decode(preferences.getString("ciphertext", null) ?: error("Pair first"), Base64.NO_WRAP)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
        }
        return cipher.doFinal(ciphertext).toString(Charsets.UTF_8).split(":")
    }
    private fun signature(key: ByteArray, message: String): String = hex(
        Mac.getInstance("HmacSHA256").apply { init(SecretKeySpec(key, "HmacSHA256")) }
            .doFinal(message.toByteArray(Charsets.UTF_8)))
    fun call(command: String, arguments: JSONObject = JSONObject()): Any {
        val code = pairing()
        val secret = unhex(code[3])
        val nonce = hex(random(16))
        val at = System.currentTimeMillis() / 1000
        val payload = JSONObject().put("instance", code[2]).put("client", client)
            .put("command", command).put("args", arguments)
        val body = Base64.encodeToString(payload.toString().toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
        val envelope = JSONObject().put("at", at).put("nonce", nonce).put("body", body)
            .put("mac", signature(secret, "$at:$nonce:$body")).toString() + "\n"
        require(envelope.length <= 524288)
        val socket = Socket()
        synchronized(sockets) {
            if (closed) { socket.close(); error("Panel connection is closed") }
            sockets.add(socket)
        }
        try {
            socket.use {
                socket.connect(InetSocketAddress("127.0.0.1", code[1].toInt()), 3000)
                socket.soTimeout = if (command in listOf("prepare", "confirm", "recover")) 180000 else 4000
                socket.getOutputStream().write(envelope.toByteArray(Charsets.UTF_8))
                val bytes = ArrayList<Byte>()
                val input = socket.getInputStream()
                while (true) {
                    val next = input.read()
                    require(next >= 0 && bytes.size < 524288)
                    if (next == 10) break
                    bytes.add(next.toByte())
                }
                val response = JSONObject(bytes.toByteArray().toString(Charsets.UTF_8))
                require(response.keys().asSequence().toSet() == setOf("at", "nonce", "body", "mac"))
                val responseTime = response.getLong("at")
                require(kotlin.math.abs(System.currentTimeMillis() / 1000 - responseTime) <= 30)
                val responseBody = response.getString("body")
                val responseNonce = response.getString("nonce")
                val expected = signature(secret, "$responseTime:$responseNonce:$responseBody")
                require(MessageDigest.isEqual(expected.toByteArray(), response.getString("mac").toByteArray()))
                val reply = JSONObject(Base64.decode(responseBody, Base64.NO_WRAP).toString(Charsets.UTF_8))
                require(reply.getString("request_nonce") == nonce)
                if (!reply.getBoolean("ok")) throw CoreRejected(reply.optString("error", "Core rejected action"))
                return reply.get("result")
            }
        } finally {
            synchronized(sockets) { sockets.remove(socket) }
        }
    }
}
