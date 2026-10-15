"""Hardware readiness and diagnostic tool for VISS on Raspberry Pi 4.

Checks operating system environment, Python dependencies, system libraries,
audio output, camera detection, serial ports, and neural network weights.
Can be run on both Raspberry Pi OS (hardware diagnostics) and macOS (mock/dev mode).

Usage:
  python3 scripts/verify_hardware_readiness.py
"""

import os
import platform
import subprocess
import sys


def check_mark(status: bool) -> str:
    return "[\033[92mPASS\033[0m]" if status else "[\033[91mFAIL\033[0m]"


def warn_mark() -> str:
    return "[\033[93mWARN\033[0m]"


def main() -> int:
    print("=" * 70)
    print("VISS Hardware & System Readiness Verification")
    print("=" * 70)

    # 1. Platform & OS
    system = platform.system()
    machine = platform.machine()
    py_version = platform.python_version()
    print(f"Platform:       {system} ({machine})")
    print(f"Python:         {py_version}")
    is_rpi = False
    try:
        with open("/proc/device-tree/model", "r") as f:
            model = f.read().strip().replace("\x00", "")
            print(f"Hardware Model: {model}")
            is_rpi = "Raspberry Pi" in model
    except FileNotFoundError:
        print("Hardware Model: Non-Linux / Not Raspberry Pi (e.g. macOS / VM)")

    print("-" * 70)
    print("1. Python Package Availability:")

    # Core packages
    packages = [
        ("numpy", "NumPy array computation"),
        ("cv2", "OpenCV computer vision library"),
        ("pyttsx3", "Offline text-to-speech engine"),
        ("serial", "pySerial communication (SIM800L)"),
        ("gpiozero", "GPIO pin abstraction (HC-SR04, buzzer, button)"),
        ("picamera2", "Raspberry Pi Camera V2/V3 native interface"),
    ]

    all_critical_ok = True
    for mod_name, desc in packages:
        try:
            __import__(mod_name)
            print(f"  {check_mark(True)} {mod_name:12s} - {desc}")
        except ImportError:
            if is_rpi or mod_name in ("numpy", "pyttsx3"):
                print(f"  {check_mark(False)} {mod_name:12s} - {desc} (NOT INSTALLED)")
                if mod_name in ("numpy", "pyttsx3"):
                    all_critical_ok = False
            else:
                print(f"  {warn_mark()} {mod_name:12s} - {desc} (Optional on macOS development host)")

    print("-" * 70)
    print("2. MobileNet-SSD Weights & Prototxt:")
    prototxt = "vision/weights/MobileNetSSD_deploy.prototxt"
    weights = "vision/weights/MobileNetSSD_deploy.caffemodel"
    has_prototxt = os.path.isfile(prototxt)
    has_weights = os.path.isfile(weights)

    print(f"  {check_mark(has_prototxt)} Prototxt ({prototxt}): {'Found' if has_prototxt else 'MISSING'}")
    if has_weights:
        sz_mb = os.path.getsize(weights) / (1024 * 1024)
        print(f"  {check_mark(True)} Weights  ({weights}): Found ({sz_mb:.1f} MB)")
    else:
        print(f"  {check_mark(False)} Weights  ({weights}): MISSING (~23 MB required for real inference)")

    print("-" * 70)
    print("3. Audio & Speech Utilities:")
    # Check aplay or afplay
    has_aplay = subprocess.run(["which", "aplay"], capture_output=True).returncode == 0
    has_afplay = subprocess.run(["which", "afplay"], capture_output=True).returncode == 0
    has_espeak = subprocess.run(["which", "espeak-ng"], capture_output=True).returncode == 0 or \
                 subprocess.run(["which", "espeak"], capture_output=True).returncode == 0

    if system == "Darwin":
        print(f"  {check_mark(has_afplay)} macOS afplay audio player available")
        print(f"  {check_mark(True)} macOS NSSpeechSynthesizer built-in for pyttsx3")
    else:
        print(f"  {check_mark(has_aplay)} Linux aplay ALSA audio player: {'Found' if has_aplay else 'MISSING (install alsa-utils)'}")
        print(f"  {check_mark(has_espeak)} espeak-ng synthesizer: {'Found' if has_espeak else 'MISSING (sudo apt install espeak-ng)'}")

    print("-" * 70)
    print("4. Serial / UART Interfaces:")
    uart_ports = ["/dev/ttyS0", "/dev/ttyAMA0", "/dev/serial0"]
    found_uarts = [p for p in uart_ports if os.path.exists(p)]
    if found_uarts:
        for p in found_uarts:
            print(f"  {check_mark(True)} Detected serial port: {p}")
    else:
        if is_rpi:
            print(f"  {check_mark(False)} No standard UART ports found in /dev/. Check raspi-config serial settings.")
        else:
            print(f"  {warn_mark()} No standard RPi UART ports found (expected on non-Pi hosts)")

    print("-" * 70)
    print("5. Camera Device Check (libcamera / rpicam):")
    if is_rpi:
        rpicam_cmd = subprocess.run(["rpicam-hello", "--list-cameras"], capture_output=True, text=True)
        if rpicam_cmd.returncode == 0 and "No cameras available" not in rpicam_cmd.stderr:
            print(f"  {check_mark(True)} Camera hardware recognized by libcamera/rpicam")
            if rpicam_cmd.stdout.strip():
                print("   " + rpicam_cmd.stdout.strip().replace("\n", "\n   "))
        else:
            libcam_cmd = subprocess.run(["libcamera-hello", "--list-cameras"], capture_output=True, text=True)
            if libcam_cmd.returncode == 0 and "No cameras available" not in libcam_cmd.stderr:
                print(f"  {check_mark(True)} Camera hardware recognized by libcamera")
            else:
                print(f"  {check_mark(False)} No camera detected. Check ribbon cable seated orientation.")
    else:
        print(f"  {warn_mark()} Camera hardware verification requires physical Raspberry Pi.")

    print("=" * 70)
    print("Verification complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
