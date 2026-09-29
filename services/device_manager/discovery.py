"""
Smart Spectator - mDNS Service Advertiser
Advertises the Smart Spectator Desktop Hub on the local network using Zeroconf.
Follows docs/04_NETWORK_ARCHITECTURE.md
"""

import socket
import uuid
from typing import Optional

try:
    from zeroconf import Zeroconf, ServiceInfo
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False

from ..hub_backend.config import settings


def get_local_ip() -> str:
    """Detects active outbound LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually transmit packets, just probes default routing interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


class HubDiscoveryAdvertiser:
    """Manages mDNS advertisement of the Smart Spectator Hub."""

    def __init__(self):
        self.zeroconf: Optional[Any] = None
        self.service_info: Optional[Any] = None
        self.hub_id = str(uuid.uuid4())[:8]
        self.is_advertising = False

    def start(self) -> bool:
        if not HAS_ZEROCONF:
            print("[mDNS] Zeroconf package not installed yet. Skipping broadcast.")
            return False

        try:
            local_ip = get_local_ip()
            hostname = socket.gethostname().split(".")[0]
            instance_name = f"{settings.MDNS_SERVICE_NAME}-{hostname}"
            
            # Service type must end with .local.
            service_type = settings.MDNS_SERVICE_TYPE
            
            properties = {
                "api_port": str(settings.PORT),
                "stream_port": str(settings.STREAM_PORT),
                "version": "1.0.0",
                "hub_id": self.hub_id,
                "device": "hub"
            }

            self.service_info = ServiceInfo(
                type_=service_type,
                name=f"{instance_name}.{service_type}",
                addresses=[socket.inet_aton(local_ip)],
                port=settings.PORT,
                properties=properties,
            )

            self.zeroconf = Zeroconf()
            self.zeroconf.register_service(self.service_info, allow_name_change=True)
            self.is_advertising = True
            print(f"[mDNS] Advertising '{instance_name}' on {local_ip}:{settings.PORT} ({service_type})")
            return True
        except Exception as e:
            import traceback
            print(f"[mDNS] Error broadcasting service: {type(e).__name__}: {e}")
            traceback.print_exc()
            return False

    def stop(self) -> None:
        if self.zeroconf and self.service_info:
            try:
                self.zeroconf.unregister_service(self.service_info)
                self.zeroconf.close()
                self.is_advertising = False
                print("[mDNS] Service advertisement stopped.")
            except Exception as e:
                print(f"[mDNS] Error unregistering service: {e}")


hub_advertiser = HubDiscoveryAdvertiser()
