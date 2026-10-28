package com.smartspectator.smart_spectator_camera

import android.Manifest
import android.app.Activity
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import android.os.Build
import java.io.ByteArrayOutputStream

/** JPEG snapshot of a camera frame given as YUV420 planes with strides. */
object SnapshotJpeg {
    fun encode(planes: List<PlaneData>, width: Int, height: Int, quality: Int, maxSize: Int = 0): ByteArray? {
        if (planes.size < 3 || width <= 0 || height <= 0) return null
        // NV21 = full Y plane followed by interleaved V/U at half resolution.
        val nv21 = ByteArray(width * height * 3 / 2)
        val y = planes[0]
        for (row in 0 until height) {
            val src = row * y.rowStride
            for (col in 0 until width) {
                val i = src + col * y.pixelStride
                if (i < y.bytes.size) nv21[row * width + col] = y.bytes[i]
            }
        }
        val u = planes[1]
        val v = planes[2]
        var out = width * height
        for (row in 0 until height / 2) {
            for (col in 0 until width / 2) {
                val vi = row * v.rowStride + col * v.pixelStride
                val ui = row * u.rowStride + col * u.pixelStride
                nv21[out++] = if (vi < v.bytes.size) v.bytes[vi] else 0
                nv21[out++] = if (ui < u.bytes.size) u.bytes[ui] else 0
            }
        }
        val stream = ByteArrayOutputStream()
        val ok = YuvImage(nv21, ImageFormat.NV21, width, height, null)
            .compressToJpeg(Rect(0, 0, width, height), quality.coerceIn(30, 95), stream)
        if (!ok) return null
        val full = stream.toByteArray()
        val longSide = maxOf(width, height)
        if (maxSize <= 0 || longSide <= maxSize) return full
        // Smaller pictures cost fewer AI tokens.
        val bitmap = android.graphics.BitmapFactory.decodeByteArray(full, 0, full.size) ?: return full
        val scale = maxSize.toFloat() / longSide
        val scaled = android.graphics.Bitmap.createScaledBitmap(
            bitmap, (width * scale).toInt().coerceAtLeast(1), (height * scale).toInt().coerceAtLeast(1), true)
        val small = ByteArrayOutputStream()
        scaled.compress(android.graphics.Bitmap.CompressFormat.JPEG, quality.coerceIn(30, 95), small)
        bitmap.recycle()
        scaled.recycle()
        return small.toByteArray()
    }
}

/** Local notifications for motion events on the main phone. */
class EventNotifier(private val context: Context) {
    private val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

    fun requestPermission(activity: Activity) {
        if (Build.VERSION.SDK_INT >= 33 &&
            activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            activity.requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQUEST_CODE)
        }
    }

    fun show(id: Int, title: String, body: String) {
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Camera alerts", NotificationManager.IMPORTANCE_HIGH).apply {
                    description = "Motion and other events from your cameras"
                },
            )
            Notification.Builder(context, CHANNEL_ID)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(context).setPriority(Notification.PRIORITY_HIGH)
        }
        val openApp = PendingIntent.getActivity(
            context,
            0,
            context.packageManager.getLaunchIntentForPackage(context.packageName),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notification = builder
            .setContentTitle(title)
            .setContentText(body)
            .setSmallIcon(R.drawable.ic_stat_vyro)
            .setColor(0xFFFACC2E.toInt())
            .setContentIntent(openApp)
            .setAutoCancel(true)
            .build()
        try {
            manager.notify(id, notification)
        } catch (_: SecurityException) {
            // Notifications not allowed by the user; the event is still in the app.
        }
    }

    companion object {
        private const val CHANNEL_ID = "ss_events"
        private const val REQUEST_CODE = 4102
    }
}
