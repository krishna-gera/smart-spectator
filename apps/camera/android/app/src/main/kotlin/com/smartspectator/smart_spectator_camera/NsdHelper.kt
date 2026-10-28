package com.smartspectator.smart_spectator_camera

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Handler
import android.os.Looper

/**
 * Local-network discovery (mDNS/DNS-SD) via Android NsdManager.
 * The main phone advertises "_smartspectator._tcp"; camera phones browse for it.
 */
class NsdHelper(context: Context) {
    private val nsd = context.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val main = Handler(Looper.getMainLooper())
    private var registration: NsdManager.RegistrationListener? = null

    fun register(port: Int, name: String) {
        unregister()
        val info = NsdServiceInfo().apply {
            serviceName = name
            serviceType = SERVICE_TYPE
            setPort(port)
        }
        val listener = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(info: NsdServiceInfo) {}
            override fun onRegistrationFailed(info: NsdServiceInfo, errorCode: Int) {}
            override fun onServiceUnregistered(info: NsdServiceInfo) {}
            override fun onUnregistrationFailed(info: NsdServiceInfo, errorCode: Int) {}
        }
        registration = listener
        nsd.registerService(info, NsdManager.PROTOCOL_DNS_SD, listener)
    }

    fun unregister() {
        registration?.let {
            try {
                nsd.unregisterService(it)
            } catch (_: Exception) {
            }
        }
        registration = null
    }

    /** Browses for [timeoutMs] and returns every resolved hub as {host, port, name}. */
    fun discover(timeoutMs: Long, onResult: (List<Map<String, Any>>) -> Unit) {
        val found = mutableListOf<Map<String, Any>>()
        val toResolve = ArrayDeque<NsdServiceInfo>()
        var resolving = false
        var finished = false

        fun resolveNext() {
            if (resolving || finished) return
            val next = toResolve.removeFirstOrNull() ?: return
            resolving = true
            @Suppress("DEPRECATION")
            nsd.resolveService(next, object : NsdManager.ResolveListener {
                override fun onServiceResolved(info: NsdServiceInfo) {
                    main.post {
                        @Suppress("DEPRECATION")
                        val host = info.host?.hostAddress
                        if (host != null && found.none { it["host"] == host && it["port"] == info.port }) {
                            found.add(mapOf("host" to host, "port" to info.port, "name" to info.serviceName))
                        }
                        resolving = false
                        resolveNext()
                    }
                }

                override fun onResolveFailed(info: NsdServiceInfo, errorCode: Int) {
                    main.post {
                        resolving = false
                        resolveNext()
                    }
                }
            })
        }

        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) {}
            override fun onDiscoveryStopped(serviceType: String) {}
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {}
            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {}
            override fun onServiceLost(info: NsdServiceInfo) {}
            override fun onServiceFound(info: NsdServiceInfo) {
                main.post {
                    toResolve.addLast(info)
                    resolveNext()
                }
            }
        }

        try {
            nsd.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener)
        } catch (e: Exception) {
            onResult(emptyList())
            return
        }
        main.postDelayed({
            finished = true
            try {
                nsd.stopServiceDiscovery(listener)
            } catch (_: Exception) {
            }
            onResult(found.toList())
        }, timeoutMs)
    }

    companion object {
        const val SERVICE_TYPE = "_smartspectator._tcp"
    }
}
