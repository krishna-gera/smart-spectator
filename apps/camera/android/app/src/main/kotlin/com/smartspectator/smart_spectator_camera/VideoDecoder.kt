package com.smartspectator.smart_spectator_camera

import android.media.MediaCodec
import android.media.MediaFormat
import android.os.Handler
import android.os.HandlerThread
import io.flutter.view.TextureRegistry
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Hardware H.264 decoder for one camera, rendering into a Flutter texture.
 *
 * The decoder starts at the first packet containing SPS/PPS and keeps that
 * configuration, so if Flutter destroys and recreates the texture surface
 * (e.g. app backgrounded), decoding resumes at the next keyframe.
 */
class VideoDecoder(
    private val producer: TextureRegistry.SurfaceProducer,
    private val onVideoSize: (width: Int, height: Int) -> Unit,
) {
    private val thread = HandlerThread("ss-video-decoder-${producer.id()}").apply { start() }
    private val handler = Handler(thread.looper)

    private var codec: MediaCodec? = null
    private var codecConfig: ByteArray? = null
    private var surfaceReady = true
    private var waitingForKeyframe = true
    var framesRendered = 0L
        private set
    var packetsDropped = 0L
        private set

    val textureId: Long get() = producer.id()

    init {
        producer.setSize(1280, 720)
        producer.setCallback(object : TextureRegistry.SurfaceProducer.Callback {
            override fun onSurfaceAvailable() {
                handler.post {
                    surfaceReady = true
                    waitingForKeyframe = true
                }
            }

            override fun onSurfaceCleanup() {
                // The surface is about to become invalid: stop rendering into it first.
                val done = CountDownLatch(1)
                handler.post {
                    surfaceReady = false
                    releaseCodec()
                    done.countDown()
                }
                done.await(500, TimeUnit.MILLISECONDS)
            }
        })
    }

    fun feed(data: ByteArray, ptsUs: Long) {
        handler.post { feedOnThread(data, ptsUs) }
    }

    private fun feedOnThread(data: ByteArray, ptsUs: Long) {
        if (!surfaceReady) return
        val hasSps = H264.containsSps(data)

        if (codec == null) {
            if (hasSps) {
                val sliceAt = H264.firstSliceStartCode(data)
                codecConfig = if (sliceAt > 0) data.copyOfRange(0, sliceAt) else data
            }
            val config = codecConfig
            if (config == null || !(hasSps || H264.nalTypes(data).contains(5))) {
                packetsDropped++
                return
            }
            if (!startCodec(config)) {
                packetsDropped++
                return
            }
        }
        if (waitingForKeyframe) {
            if (!H264.nalTypes(data).contains(5)) {
                packetsDropped++
                return
            }
            waitingForKeyframe = false
        }

        val c = codec ?: return
        try {
            val inputIndex = c.dequeueInputBuffer(10_000L)
            if (inputIndex < 0) {
                packetsDropped++
            } else {
                val input = c.getInputBuffer(inputIndex)
                if (input == null || input.capacity() < data.size) {
                    c.queueInputBuffer(inputIndex, 0, 0, ptsUs, 0)
                    packetsDropped++
                } else {
                    input.clear()
                    input.put(data)
                    c.queueInputBuffer(inputIndex, 0, data.size, ptsUs, 0)
                }
            }
            drain(c)
        } catch (e: Exception) {
            // Decoder error (corrupt stream, codec reclaimed): restart at the next keyframe.
            releaseCodec()
            packetsDropped++
        }
    }

    private fun startCodec(config: ByteArray): Boolean {
        return try {
            val format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, 1280, 720)
            val c = MediaCodec.createDecoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
            c.configure(format, producer.surface, null, 0)
            c.start()
            val index = c.dequeueInputBuffer(10_000L)
            if (index >= 0) {
                val input = c.getInputBuffer(index)!!
                input.clear()
                input.put(config)
                c.queueInputBuffer(index, 0, config.size, 0, MediaCodec.BUFFER_FLAG_CODEC_CONFIG)
            }
            codec = c
            waitingForKeyframe = true
            true
        } catch (e: Exception) {
            releaseCodec()
            false
        }
    }

    private fun drain(c: MediaCodec) {
        val info = MediaCodec.BufferInfo()
        while (true) {
            val index = c.dequeueOutputBuffer(info, 0L)
            when {
                index >= 0 -> {
                    c.releaseOutputBuffer(index, true)
                    framesRendered++
                }
                index == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> reportSize(c.outputFormat)
                else -> return
            }
        }
    }

    private fun reportSize(format: MediaFormat) {
        var w = format.getInteger(MediaFormat.KEY_WIDTH)
        var h = format.getInteger(MediaFormat.KEY_HEIGHT)
        if (format.containsKey("crop-right") && format.containsKey("crop-left")) {
            w = format.getInteger("crop-right") - format.getInteger("crop-left") + 1
        }
        if (format.containsKey("crop-bottom") && format.containsKey("crop-top")) {
            h = format.getInteger("crop-bottom") - format.getInteger("crop-top") + 1
        }
        producer.setSize(w, h)
        onVideoSize(w, h)
    }

    private fun releaseCodec() {
        try {
            codec?.stop()
        } catch (_: Exception) {
        }
        try {
            codec?.release()
        } catch (_: Exception) {
        }
        codec = null
        waitingForKeyframe = true
    }

    fun release() {
        handler.post {
            releaseCodec()
            producer.release()
        }
        thread.quitSafely()
    }
}
