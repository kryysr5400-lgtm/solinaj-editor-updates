from pathlib import Path

APP_NAME = "Solinaj Shorts"
APP_VERSION = "2.8.14"

def version_tuple(value):
    import re
    nums = re.findall(r"\d+", str(value))
    nums = (nums + ["0", "0", "0"])[:3]
    return tuple(int(x) for x in nums)

def is_newer(remote_version, current_version=APP_VERSION):
    return version_tuple(remote_version) > version_tuple(current_version)

def display_version():
    return f"V{APP_VERSION}"

def app_title():
    return f"{APP_NAME} V{APP_VERSION}"

def update_channel_name():
    return "Solinaj Editor Internet Update Channel"

def compatibility_note():
    return "Mevcut SolinajEditorV2 klasoru, FFmpeg ve kullanici ayarlari korunur."
