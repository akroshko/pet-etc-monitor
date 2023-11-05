#!/usr/bin/env python3
""" Contains hardware specific data.
"""

# see https://github.com/espressif/esp32-camera/blob/master/driver/include/sensor.h
# typedef enum {
#     FRAMESIZE_96X96,    // 96x96
#     FRAMESIZE_QQVGA,    // 160x120
#     FRAMESIZE_QCIF,     // 176x144
#     FRAMESIZE_HQVGA,    // 240x176
#     FRAMESIZE_240X240,  // 240x240
#     FRAMESIZE_QVGA,     // 320x240
#     FRAMESIZE_CIF,      // 400x296
#     FRAMESIZE_HVGA,     // 480x320
#     FRAMESIZE_VGA,      // 640x480
#     FRAMESIZE_SVGA,     // 800x600
#     FRAMESIZE_XGA,      // 1024x768
#     FRAMESIZE_HD,       // 1280x720
#     FRAMESIZE_SXGA,     // 1280x1024
#     FRAMESIZE_UXGA,     // 1600x1200
#     // 3MP Sensors
#     FRAMESIZE_FHD,      // 1920x1080
#     FRAMESIZE_P_HD,     //  720x1280
#     FRAMESIZE_P_3MP,    //  864x1536
#     FRAMESIZE_QXGA,     // 2048x1536
#     // 5MP Sensors
#     FRAMESIZE_QHD,      // 2560x1440
#     FRAMESIZE_WQXGA,    // 2560x1600
#     FRAMESIZE_P_FHD,    // 1080x1920
#     FRAMESIZE_QSXGA,    // 2560x1920
#     FRAMESIZE_INVALID
# } framesize_t;

def _get_formats():
    """Enumerate the formats for the camera.

    The camera only ever returns numeric values to designate a format
    so this function allows indexing those to obtain a human-readable
    string

    """
    i=0
    def _get_format_index():
        nonlocal i
        old_i=i
        i=i+1
        return old_i
    formats=["96X96",
             "QQVGA(160x120)",
             "QCIF(176x144)",
             "HQVGA(240x176)",
             "240X240",
             "QVGA(320x240)",
             "CIF(400x296)",
             "HVGA(480x320)",
             "VGA(640x480)",
             "SVGA(800x600)",
             "XGA(1024x768)",
             "HD(1280x720)",
             "SXGA(1280x1024)",
             "UXGA(1600x1200)"
             # below not valid on my camera
             # # 3MP sensors
             # "FHD(1920x1080)"
             # "P HD(720x1280)",
             # "P 3MP(864x1536)",
             # "QXGA(2048x1536)",
             # # 5MP sensors
             # "QHD(2560x1440)",
             # "WQXGA(2560x1600)",
             # "P FHD(1080x1920)",
             # "QSXGA(2560x1920)",
             # "INVALID"
             ]
    format_dict={_get_format_index():f for f in formats}
    return format_dict
ESP32_FRAMESIZE=_get_formats()
