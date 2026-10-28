package com.smartspectator.smart_spectator_camera

import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.nio.ByteBuffer

class MainActivity : FlutterActivity() {
    private val ENCODER_CHANNEL = "com.smartspectator.camera/encoder"
    private var mediaCodec: MediaCodec? = null
    private var isEncoderInitialized = false
    private var frameWidth = 1280
    private var frameHeight = 720

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, ENCODER_CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "initEncoder" -> {
                    val width = call.argument<Int>("width") ?: 1280
                    val height = call.argument<Int>("height") ?: 720
                    val bitrate = call.argument<Int>("bitrate") ?: 2000000
                    val fps = call.argument<Int>("fps") ?: 30
                    val gopSeconds = call.argument<Int>("keyframeInterval") ?: 1

                    val success = initializeMediaCodec(width, height, bitrate, fps, gopSeconds)
                    if (success) {
                        result.success(true)
                    } else {
                        result.error("ENCODER_INIT_FAILED", "Failed to initialize Android MediaCodec H.264 encoder", null)
                    }
                }
                "encodeFrame" -> {
                    val yuvData = call.argument<ByteArray>("yuvData")
                    val width = call.argument<Int>("width") ?: frameWidth
                    val height = call.argument<Int>("height") ?: frameHeight
                    val timestampUs = call.argument<Long>("timestampUs") ?: (System.nanoTime() / 1000)

                    if (yuvData == null || !isEncoderInitialized) {
                        result.error("INVALID_STATE", "Encoder not initialized or null YUV buffer", null)
                        return@setMethodCallHandler
                    }

                    try {
                        val encodedPackets = encodeYuvToH264(yuvData, width, height, timestampUs)
                        result.success(encodedPackets)
                    } catch (e: Exception) {
                        result.error("ENCODE_ERROR", e.message, null)
                    }
                }
                "stopEncoder" -> {
                    stopMediaCodec()
                    result.success(true)
                }
                else -> result.notImplemented()
            }
        }
    }

    private fun initializeMediaCodec(width: Int, height: Int, bitrate: Int, fps: Int, gopSeconds: Int): Boolean {
        stopMediaCodec()
        return try {
            frameWidth = width
            frameHeight = height

            val format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, width, height).apply {
                setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible)
                setInteger(MediaFormat.KEY_BIT_RATE, bitrate)
                setInteger(MediaFormat.KEY_FRAME_RATE, fps)
                setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, gopSeconds)
                setInteger(MediaFormat.KEY_BITRATE_MODE, MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_CBR)
            }

            mediaCodec = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC).apply {
                configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
                start()
            }
            isEncoderInitialized = true
            true
        } catch (e: Exception) {
            mediaCodec = null
            isEncoderInitialized = false
            false
        }
    }

    private fun encodeYuvToH264(yuvData: ByteArray, width: Int, height: Int, timestampUs: Long): List<Map<String, Any>> {
        val codec = mediaCodec ?: return emptyList()
        val results = mutableListOf<Map<String, Any>>()

        // 1. Submit input frame
        val inputBufferIndex = codec.dequeueInputBuffer(10000L) // 10ms timeout
        if (inputBufferIndex >= 0) {
            val inputBuffer: ByteBuffer = codec.getInputBuffer(inputBufferIndex) ?: return emptyList()
            inputBuffer.clear()
            val bytesToCopy = Math.min(yuvData.size, inputBuffer.remaining())
            inputBuffer.put(yuvData, 0, bytesToCopy)
            codec.queueInputBuffer(inputBufferIndex, 0, bytesToCopy, timestampUs, 0)
        }

        // 2. Drain output buffers
        val bufferInfo = MediaCodec.BufferInfo()
        var outputBufferIndex = codec.dequeueOutputBuffer(bufferInfo, 10000L)

        while (outputBufferIndex >= 0) {
            val outputBuffer: ByteBuffer = codec.getOutputBuffer(outputBufferIndex) ?: continue
            outputBuffer.position(bufferInfo.offset)
            outputBuffer.limit(bufferInfo.offset + bufferInfo.size)

            val outData = ByteArray(bufferInfo.size)
            outputBuffer.get(outData)

            val isKeyframe = (bufferInfo.flags and MediaCodec.BUFFER_FLAG_KEY_FRAME) != 0 ||
                             (bufferInfo.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG) != 0

            results.add(mapOf(
                "isKeyframe" to isKeyframe,
                "data" to outData,
                "ptsUs" to bufferInfo.presentationTimeUs,
                "flags" to bufferInfo.flags
            ))

            codec.releaseOutputBuffer(outputBufferIndex, false)
            outputBufferIndex = codec.dequeueOutputBuffer(bufferInfo, 0L)
        }

        return results
    }

    private fun stopMediaCodec() {
        try {
            if (isEncoderInitialized && mediaCodec != null) {
                mediaCodec?.stop()
                mediaCodec?.release()
            }
        } catch (e: Exception) {
            // Ignore teardown errors
        } finally {
            mediaCodec = null
            isEncoderInitialized = false
        }
    }

    override fun onDestroy() {
        stopMediaCodec()
        super.onDestroy()
    }
}
