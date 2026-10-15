# Visual Impairment Support System (VISS) — User Handoff Guide

> **Author**: Engineering & Integration Team  
> **Host Development Machine**: MacBook Air M2 (macOS Sequoia)  
> **Deployment Target**: Raspberry Pi 5 (8 GB RAM, Raspberry Pi OS 64-bit Bookworm)  
> **Current Status**: Real computer-vision pipeline & spoken alerts verified working locally on macOS. 109/109 tests passing.

---

## 1. WHAT HAS BEEN DONE (FULLY AUTOMATED)

All of the following engineering, refactoring, and verification tasks have been completed directly inside this repository:

1. **Python 3.12 Virtual Environment Created & Configured**:
   - Resolved the macOS Homebrew Python 3.14 wheel incompatibility by creating an isolated virtual environment at `./venv` using Python 3.12.14 (`/opt/homebrew/bin/python3.12`).
   - Pinned and installed verified dependencies in `requirements-mac.txt`:
     - `opencv-python==4.14.0.94` (pinned `<5.0.0` to retain Caffe DNN support).
     - `numpy==2.5.4`
     - `pyttsx3==2.99`
     - `pytest==9.1.1`

2. **Pretrained Neural Network Acquired & Validated**:
   - Downloaded and verified the authoritative MobileNet-SSD Caffe weights and deployment prototxt in `vision/weights/`:
     - `MobileNetSSD_deploy.caffemodel` (23.3 MB, SHA256: `52eed8be80522c152a17fb56740de705b79881bde1a167e0e747310523685fc7`)
     - `MobileNetSSD_deploy.prototxt` (29.4 KB, SHA256: `2d180f723b3109e21f8287f6b3c691390d07b60eed998327cd3259ffa0e50608`)
   - Documented the model selection criteria, tensor dimensions, normalization, and trade-offs in `MODEL_SELECTION.md`.

3. **Earphone Audio & Spoken Alerts Subsystem Implemented**:
   - Implemented `VoiceAlertPlayer` in `core/voice_alert.py` with native macOS `/usr/bin/say` integration, falling back to `pyttsx3`/`espeak-ng`.
   - Built an asynchronous, non-blocking announcement queue with smart deduplication (3.0s cooldown per class label) so speech synthesis never slows down camera frame capture or distance processing.

4. **Architecture Cleaned & Decoupled**:
   - Fixed circular import between `core/__init__.py` and `vision.detector` using PEP 562 lazy module attributes.
   - Added `ApplicationController.create_mac_real(config, camera_device)` in `core/controller.py` to allow live camera capture, real MobileNet-SSD detection, and real earphone voice alerts on macOS while keeping GPIO hardware safely mocked.
   - Enhanced `main.py` CLI with `--mode mac` and `--camera-index`.

5. **Validation Test Assets & Scripts Created**:
   - Sample images placed in `vision/test_assets/` (`sample_cat.jpg` and `sample_person.png`).
   - Test scripts in `scripts/`:
     - `test_model_smoke.py` (model loading smoke test)
     - `test_image_inference.py` (static image detection + voice alert)
     - `test_mac_webcam.py` (webcam capture diagnostic)
     - `test_audio_voice.py` (tone audio and spoken TTS verification)
     - `test_real_pipeline_mac.py` (end-to-end live webcam -> model -> speech pipeline)
   - Created `tests/test_real_vision_audio.py` adding 9 real-pipeline unit tests. Full test suite expanded to **109 tests (100% passing)**.

6. **Unified Test & Execution Script (`run.sh`)**:
   - Configured `./run.sh` to automatically detect `./venv` and run tests, diagnostics, and simulations with clear terminal output.

---

## 2. ACTIONS YOU MUST PERFORM ON YOUR MAC

To run the live camera and hear real voice alerts directly from your MacBook Air M2, perform the following in your macOS Terminal:

### Step 1: Open Terminal in the Project Directory
```bash
cd /Users/pratikshinde/viss_project
```

### Step 2: Test Object Detection on a Sample Image with Spoken Audio
Plug in earphones or turn on your Mac speakers, then run:
```bash
./run.sh image
```
*Expected Behavior*: You will see the detected `CAT` bounding box and hear your Mac speak *"cat detected"*.

To test on people/pedestrians:
```bash
./run.sh image vision/test_assets/sample_person.png
```
*Expected Behavior*: You will see 4 `PERSON` detections (up to 99.3% confidence) and hear spoken alerts for detected persons.

To test on domestic animals & indoor obstacles (dog + chair):
```bash
./run.sh image vision/test_assets/sample_dog.jpg
```
*Expected Behavior*: You will see `DOG` (99.8%) and `CHAIR` (67.8%) detected, and hear *"Dog detected"*, *"Chair detected"*.

To test on office obstacles (chair + potted plant + bottle):
```bash
./run.sh image vision/test_assets/sample_office.jpg
```
*Expected Behavior*: You will see `CHAIR` (100%), `POTTEDPLANT` (90.2%), and `BOTTLE` (51%) detected, and hear natural voice announcements.

### Step 3: Run the Live Webcam Pipeline
Run the real-time webcam pipeline for 15 seconds:
```bash
./run.sh pipeline 15
```
*Expected Behavior*: If macOS displays a camera permission prompt, click **"Allow"** (see Section 3). Stand in front of your Mac camera. When the system detects you, you will hear *"person detected"* through your earphones/speakers every 3 seconds while you remain in view.

### Step 4: Run the Complete VISS Application in Real macOS Mode
Run the full VISS controller (real webcam + real MobileNet-SSD + real voice alerts + mock GPIO):
```bash
./run.sh mac 20
```
This runs the full decision engine and application loop for 20 seconds.

---

## 3. ACTIONS REQUIRING PERMISSION OR EXTERNAL PROMPTS

### macOS Camera Permission (TCC)
macOS requires user authorization before any app or terminal can access the FaceTime camera.

1. When you run `./run.sh pipeline` or `./run.sh camera` from your Terminal for the first time, macOS will show a dialog:
   > *"Terminal would like to access the camera."*
2. Click **"OK" / "Allow"**.
3. If camera permission was previously denied or does not prompt:
   - Open **System Settings** on your Mac.
   - Navigate to **Privacy & Security** $\rightarrow$ **Camera**.
   - Ensure the toggle next to **Terminal** (or **iTerm2** / your IDE) is switched **ON**.

---

## 4. API KEYS AND EXTERNAL SERVICES

> **CONFIRMATION**: **ZERO external or paid API keys are required.**

- **Computer Vision**: Powered by local MobileNet-SSD running on the local CPU via OpenCV DNN.
- **Audio & Speech**: Powered by local macOS `/usr/bin/say` (or local `pyttsx3` / `espeak-ng`).
- **Network Dependency**: **None.** The entire system operates completely offline without internet connectivity.

---

## 5. RASPBERRY PI 5 DEPLOYMENT (STEP-BY-STEP)

When you are ready to deploy to your physical Raspberry Pi 5 (8 GB RAM):

### Step 1: Prepare the Pi 5 Operating System
1. Install **Raspberry Pi OS (64-bit Bookworm)** on a high-speed microSD card (or NVMe SSD) using Raspberry Pi Imager.
2. Boot the Pi 5, complete initial setup, and connect to your local Wi-Fi or Ethernet.

### Step 2: Transfer the VISS Project to the Pi
From your Mac:
```bash
# Copy the project archive to the Pi
scp viss_project.zip pi@<pi-ip-address>:~/
```
On the Pi:
```bash
unzip viss_project.zip -d ~/viss_project
cd ~/viss_project
```

### Step 3: Install System Packages on the Pi
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv python3-opencv \
    python3-picamera2 libcamera-dev espeak-ng alsa-utils
```

### Step 4: Create Virtual Environment on the Pi
```bash
# Create venv with system site packages so it can use apt's picamera2 and cv2
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 5: Test Hardware Subsystems Individually
Run the hardware diagnostic scripts on the Pi:
```bash
# 1. Verify model weights load on Pi 5 CPU
python3 scripts/test_model_smoke.py

# 2. Test earphone audio via 3.5mm jack or USB/Bluetooth earphones
python3 scripts/test_audio_voice.py

# 3. Test Raspberry Pi Camera (CSI ribbon or USB)
python3 scripts/test_camera.py

# 4. Test HC-SR04 ultrasonic distance sensor
python3 scripts/test_distance_sensor.py

# 5. Test push buttons
python3 scripts/test_button.py

# 6. Test SIM800L GSM module
python3 scripts/test_gsm_uart.py
```

### Step 6: Launch Full Production VISS on the Pi
```bash
# Launch in physical hardware mode
python3 main.py --mode hardware
```

---

## 6. PHYSICAL HARDWARE REQUIRED FOR NEXT STAGE

The table below lists the physical hardware components required for the wearable assistive prototype:

| Component | Purpose | Pi 5 Interface / Wiring | Notes |
|---|---|---|---|
| **Raspberry Pi 5 (8 GB)** | Primary compute unit | 5V / 5A USB-C Power Supply | Active cooling fan recommended. |
| **RPi Camera Module v2 / v3** | Real-time visual obstacle capture | Pi 5 CSI/DSI 22-pin ribbon cable port | Use the 22-to-15 pin adapter ribbon cable designed for Pi 5. |
| **Wired Earphones or Bluetooth Headset** | Spoken obstacle alerts & acoustic beeps | USB Audio adapter, 3.5mm DAC, or Bluetooth | Since Pi 5 lacks an onboard 3.5mm jack, use a cheap USB-C-to-3.5mm DAC or Bluetooth earbuds. |
| **HC-SR04 Distance Sensor** | Close-range obstacle detection ($< 200\text{ cm}$) | GPIO 23 (Trigger), GPIO 24 (Echo via 1k/2k voltage divider) | Voltage divider protects Pi GPIO from 5V echo pulse. |
| **Active Buzzer** | Acoustic proximity alert | GPIO 18 (PWM / Digital Out) | Provides proximity beeps proportional to distance. |
| **Push Buttons (x2)** | Power toggle & Emergency SOS trigger | GPIO 17 (Emergency SOS), GPIO 27 (Power/Cancel) | Connect between GPIO pin and GND; internal pull-up enabled in software. |
| **SIM800L GSM Module** | Emergency SMS dispatch with GPS | Hardware UART (`/dev/ttyAMA0` or `/dev/serial0`) | Requires dedicated 3.7V–4.2V 2A power supply with common GND. |

---

## 7. EXPECTED OUTPUT AND TROUBLESHOOTING

### Expected Output Example (`./run.sh image`)
```text
Loaded image: 'vision/test_assets/sample_cat.jpg' (Resolution: 1600x1598, Channels: 3)
[INFO] Loading Caffe network from 'vision/weights/MobileNetSSD_deploy.caffemodel'...
[INFO] OpenCV Caffe DNN successfully initialized.
Running detection (confidence threshold: 0.40)...
[PASS] Inference completed in 44.8 ms (22.3 FPS equivalent).
----------------------------------------------------------------------
Detected 1 target objects:
  #1: CAT      | Confidence: 1.00 (100.0%) | BBox: [5, 9, 1264, 1590]

Announcing detected objects via voice alert player...
[INFO] Voice alert backend initialized using macOS native '/usr/bin/say' (rate=160 wpm).
[INFO] VoiceAlertPlayer closed. Announcements: 1 made, 0 deduplicated, 0 dropped.
```

### Common Issues & Solutions

| Symptom | Probable Cause | Immediate Remedy |
|---|---|---|
| `OpenCVCamera: could not open camera device 0` | macOS camera permission denied or webcam in use by another app | Grant Camera permission to Terminal in **System Settings $\rightarrow$ Privacy & Security $\rightarrow$ Camera**, and close FaceTime/Photo Booth. |
| `OpenCV: cv2.dnn.readNetFromCaffe failed` | Using OpenCV 5.0+ or corrupted weights | Ensure `opencv-python<5.0.0` is installed via `pip install "opencv-python<5.0.0"`. Check SHA256 checksums in `vision/weights/README.md`. |
| `No sound from earphones on macOS` | Mac default audio output not routed to earphones | Click Sound in the macOS Control Center and select your headphones/Bluetooth earphones as the active output device. |
| `picamera2 not found` on macOS | `picamera2` is a Linux/Raspberry Pi specific package | Expected on macOS. On Mac, use `--mode mac` or `--mode mock`, which uses `OpenCVCamera` or `MockCamera`. `picamera2` is only used in `--mode hardware` on the Pi. |
| `Serial port /dev/ttyAMA0 not found` | RPi UART port does not exist on macOS | Expected on macOS. The application automatically mocks serial communication on macOS. |
