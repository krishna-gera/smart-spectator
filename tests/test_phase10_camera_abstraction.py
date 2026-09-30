"""
Phase 10 Tests — Camera Source Abstraction
Conforms to Sections 17 & 37 of Phase 10 Specification.
Validates:
1. Polymorphic CameraSource base class contract.
2. AndroidCameraSource operational encapsulation.
3. Future source stubs (RTSP, ONVIF, USB) cleanly isolate future implementations.
"""

import pytest

from services.stream_engine.sources import (
    CameraSource,
    AndroidCameraSource,
    RTSPCameraSource,
    ONVIFCameraSource,
    USBCameraSource,
)


def test_android_camera_source_contract():
    src = AndroidCameraSource(camera_id="cam_phone_01")
    assert isinstance(src, CameraSource)
    assert src.source_type == "android_tcp"
    assert src.camera_id == "cam_phone_01"
    assert src.is_connected is False

    stats = src.get_stats()
    assert "source_type" in stats
    assert "connected" in stats
    assert stats["source_type"] == "android_tcp"


def test_future_camera_source_stubs_raise_clean_not_implemented():
    # RTSP
    rtsp = RTSPCameraSource(camera_id="cam_rtsp_01", rtsp_url="rtsp://192.168.1.100:554/live")
    assert rtsp.source_type == "rtsp"
    with pytest.raises(NotImplementedError, match="planned for a future release"):
        rtsp.connect()

    # ONVIF
    onvif = ONVIFCameraSource(camera_id="cam_onvif_01", host="192.168.1.101")
    assert onvif.source_type == "onvif"
    with pytest.raises(NotImplementedError, match="planned for a future release"):
        onvif.connect()

    # USB
    usb = USBCameraSource(camera_id="cam_usb_01", device_index=0)
    assert usb.source_type == "usb"
    with pytest.raises(NotImplementedError, match="planned for a future release"):
        usb.connect()
