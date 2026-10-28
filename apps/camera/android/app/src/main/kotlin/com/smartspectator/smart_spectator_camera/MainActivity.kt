package com.smartspectator.smart_spectator_camera

import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.view.WindowManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val main = Handler(Looper.getMainLooper())
    private val encoder = VideoEncoder()
    private val decoders = mutableMapOf<Long, VideoDecoder>()
    private var nsd: NsdHelper? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        val messenger = flutterEngine.dartExecutor.binaryMessenger
        nsd = NsdHelper(applicationContext)

        // ---- Camcorder Mode: hardware H.264 encoder
        MethodChannel(messenger, ENCODER_CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "initEncoder" -> {
                    val width = call.argument<Int>("width") ?: 1280
                    val height = call.argument<Int>("height") ?: 720
                    val bitrate = call.argument<Int>("bitrate") ?: 2_000_000
                    val fps = call.argument<Int>("fps") ?: 30
                    val gop = call.argument<Int>("keyframeInterval") ?: 1
                    encoder.post {
                        val ok = encoder.configure(width, height, bitrate, fps, gop)
                        main.post {
                            if (ok) result.success(true)
                            else result.error("ENCODER_INIT_FAILED", "Failed to initialize H.264 encoder for ${width}x$height", null)
                        }
                    }
                }
                "encodeFrame" -> {
                    val rawPlanes = call.argument<List<Map<String, Any>>>("planes")
                    val timestampUs = (call.argument<Number>("timestampUs") ?: System.nanoTime() / 1000).toLong()
                    if (rawPlanes == null || rawPlanes.size < 3) {
                        result.error("INVALID_ARGS", "Expected three YUV planes", null)
                        return@setMethodCallHandler
                    }
                    val planes = rawPlanes.map {
                        PlaneData(
                            it["bytes"] as ByteArray,
                            (it["rowStride"] as Number).toInt(),
                            (it["pixelStride"] as Number).toInt(),
                        )
                    }
                    encoder.post {
                        try {
                            val packets = encoder.encode(planes, timestampUs)
                            main.post { result.success(packets) }
                        } catch (e: Exception) {
                            main.post { result.error("ENCODE_ERROR", e.message, null) }
                        }
                    }
                }
                "requestKeyframe" -> {
                    encoder.requestKeyframe()
                    result.success(true)
                }
                "stopEncoder" -> encoder.post {
                    encoder.stopCodec()
                    main.post { result.success(true) }
                }
                else -> result.notImplemented()
            }
        }

        // ---- View Mode: hardware H.264 decoders rendering into Flutter textures
        val decoderChannel = MethodChannel(messenger, DECODER_CHANNEL)
        decoderChannel.setMethodCallHandler { call, result ->
            when (call.method) {
                "create" -> {
                    val producer = flutterEngine.renderer.createSurfaceProducer()
                    val id = producer.id()
                    decoders[id] = VideoDecoder(producer) { w, h ->
                        main.post {
                            decoderChannel.invokeMethod("onVideoSize", mapOf("textureId" to id, "width" to w, "height" to h))
                        }
                    }
                    result.success(id)
                }
                "feed" -> {
                    val id = (call.argument<Number>("textureId") ?: -1).toLong()
                    val data = call.argument<ByteArray>("data")
                    val pts = (call.argument<Number>("ptsUs") ?: 0).toLong()
                    val decoder = decoders[id]
                    if (decoder != null && data != null) decoder.feed(data, pts)
                    result.success(null)
                }
                "stats" -> {
                    val d = decoders[(call.argument<Number>("textureId") ?: -1).toLong()]
                    result.success(d?.let { mapOf("framesRendered" to it.framesRendered, "packetsDropped" to it.packetsDropped) })
                }
                "release" -> {
                    decoders.remove((call.argument<Number>("textureId") ?: -1).toLong())?.release()
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }

        // ---- System services: foreground hub service, screen wake, LAN discovery
        MethodChannel(messenger, SYSTEM_CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "startHubService" -> {
                    val intent = Intent(this, HubForegroundService::class.java)
                        .putExtra(HubForegroundService.EXTRA_TEXT, call.argument<String>("text"))
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(intent) else startService(intent)
                    result.success(true)
                }
                "stopHubService" -> {
                    stopService(Intent(this, HubForegroundService::class.java))
                    result.success(true)
                }
                "keepScreenOn" -> {
                    if (call.argument<Boolean>("enabled") == true) {
                        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    } else {
                        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    }
                    result.success(true)
                }
                "nsdRegister" -> {
                    nsd?.register(call.argument<Int>("port") ?: 8000, call.argument<String>("name") ?: "SmartSpectator")
                    result.success(true)
                }
                "nsdUnregister" -> {
                    nsd?.unregister()
                    result.success(true)
                }
                "nsdDiscover" -> {
                    val timeout = (call.argument<Number>("timeoutMs") ?: 3000).toLong()
                    val helper = nsd
                    if (helper == null) result.success(emptyList<Any>())
                    else helper.discover(timeout) { hubs -> result.success(hubs) }
                }
                else -> result.notImplemented()
            }
        }
    }

    override fun onDestroy() {
        decoders.values.forEach { it.release() }
        decoders.clear()
        nsd?.unregister()
        encoder.shutdown()
        super.onDestroy()
    }

    companion object {
        private const val ENCODER_CHANNEL = "com.smartspectator.camera/encoder"
        private const val DECODER_CHANNEL = "com.smartspectator/decoder"
        private const val SYSTEM_CHANNEL = "com.smartspectator/system"
    }
}
