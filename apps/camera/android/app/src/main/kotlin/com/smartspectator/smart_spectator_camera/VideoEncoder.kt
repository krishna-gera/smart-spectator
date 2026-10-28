package com.smartspectator.smart_spectator_camera

import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread

/** One YUV420 plane as delivered by the Flutter camera plugin. */
class PlaneData(val bytes: ByteArray, val rowStride: Int, val pixelStride: Int)

/**
 * Hardware H.264 encoder running on its own thread.
 *
 * - Copies camera planes into the codec's own input Image using both sides'
 *   row/pixel strides, so padded rows and interleaved chroma are handled.
 * - Prepends SPS/PPS to every keyframe so a viewer can start decoding at any
 *   keyframe, not only at the very first packet of the stream.
 */
class VideoEncoder {
    private val thread = HandlerThread("ss-video-encoder").apply { start() }
    private val handler = Handler(thread.looper)

    private var codec: MediaCodec? = null
    private var codecConfig: ByteArray? = null
    var width = 0
        private set
    var height = 0
        private set

    fun post(block: () -> Unit) {
        handler.post(block)
    }

    /** Must be called on the encoder thread (via [post]). */
    fun configure(width: Int, height: Int, bitrate: Int, fps: Int, gopSeconds: Int): Boolean {
        stopCodec()
        return try {
            val format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, width, height).apply {
                setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible)
                setInteger(MediaFormat.KEY_BIT_RATE, bitrate)
                setInteger(MediaFormat.KEY_FRAME_RATE, fps)
                setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, gopSeconds)
                setInteger(MediaFormat.KEY_BITRATE_MODE, MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_CBR)
            }
            codec = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC).apply {
                configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
                start()
            }
            this.width = width
            this.height = height
            true
        } catch (e: Exception) {
            stopCodec()
            false
        }
    }

    /** Must be called on the encoder thread. Returns encoded packets (possibly empty). */
    fun encode(planes: List<PlaneData>, timestampUs: Long): List<Map<String, Any>> {
        val c = codec ?: return emptyList()
        val inputIndex = c.dequeueInputBuffer(10_000L)
        if (inputIndex >= 0) {
            val image = c.getInputImage(inputIndex)
            if (image != null && planes.size >= 3) {
                for (p in 0 until 3) {
                    val src = planes[p]
                    val dst = image.planes[p]
                    val planeWidth = if (p == 0) width else width / 2
                    val planeHeight = if (p == 0) height else height / 2
                    val buf = dst.buffer
                    for (row in 0 until planeHeight) {
                        val srcOffset = row * src.rowStride
                        val dstOffset = row * dst.rowStride
                        if (src.pixelStride == 1 && dst.pixelStride == 1) {
                            buf.position(dstOffset)
                            buf.put(src.bytes, srcOffset, planeWidth)
                        } else {
                            for (col in 0 until planeWidth) {
                                buf.put(dstOffset + col * dst.pixelStride, src.bytes[srcOffset + col * src.pixelStride])
                            }
                        }
                    }
                }
            }
            c.queueInputBuffer(inputIndex, 0, width * height * 3 / 2, timestampUs, 0)
        }
        return drain(c)
    }

    private fun drain(c: MediaCodec): List<Map<String, Any>> {
        val results = mutableListOf<Map<String, Any>>()
        val info = MediaCodec.BufferInfo()
        while (true) {
            val index = c.dequeueOutputBuffer(info, 0L)
            if (index < 0) break // TRY_AGAIN, FORMAT_CHANGED or BUFFERS_CHANGED
            val out = c.getOutputBuffer(index)
            if (out != null && info.size > 0) {
                out.position(info.offset)
                out.limit(info.offset + info.size)
                val data = ByteArray(info.size)
                out.get(data)

                if (info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG != 0) {
                    // SPS/PPS: keep and attach to keyframes instead of sending alone.
                    codecConfig = data
                } else {
                    val isKey = info.flags and MediaCodec.BUFFER_FLAG_KEY_FRAME != 0
                    val config = codecConfig
                    val payload = if (isKey && config != null && !H264.containsSps(data)) config + data else data
                    results.add(
                        mapOf(
                            "isKeyframe" to isKey,
                            "data" to payload,
                            "ptsUs" to info.presentationTimeUs,
                        ),
                    )
                }
            }
            c.releaseOutputBuffer(index, false)
        }
        return results
    }

    fun requestKeyframe() {
        handler.post {
            try {
                codec?.setParameters(Bundle().apply { putInt(MediaCodec.PARAMETER_KEY_REQUEST_SYNC_FRAME, 0) })
            } catch (_: Exception) {
            }
        }
    }

    /** Must be called on the encoder thread. */
    fun stopCodec() {
        try {
            codec?.stop()
        } catch (_: Exception) {
        }
        try {
            codec?.release()
        } catch (_: Exception) {
        }
        codec = null
        codecConfig = null
        width = 0
        height = 0
    }

    fun shutdown() {
        handler.post { stopCodec() }
        thread.quitSafely()
    }
}

/** Minimal H.264 Annex-B helpers shared by the encoder and decoder. */
object H264 {
    /** NAL unit types found after each start code. */
    fun nalTypes(data: ByteArray): List<Int> = nalStarts(data).map { data[it].toInt() and 0x1F }

    fun containsSps(data: ByteArray): Boolean = nalTypes(data).contains(7)

    /** Byte offset of the start code before the first slice NAL (types 1 or 5), or -1. */
    fun firstSliceStartCode(data: ByteArray): Int {
        for (start in nalStarts(data)) {
            val type = data[start].toInt() and 0x1F
            if (type == 1 || type == 5) {
                return if (start >= 4 && data[start - 4].toInt() == 0) start - 4 else start - 3
            }
        }
        return -1
    }

    /** Offsets of the first byte after each 00 00 01 start code. */
    private fun nalStarts(data: ByteArray): List<Int> {
        val starts = mutableListOf<Int>()
        var i = 0
        while (i + 3 < data.size) {
            if (data[i].toInt() == 0 && data[i + 1].toInt() == 0 && data[i + 2].toInt() == 1) {
                starts.add(i + 3)
                i += 3
            } else {
                i++
            }
        }
        return starts
    }
}
