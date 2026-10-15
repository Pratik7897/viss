# Visual Impairment Support System (VISS)

> **Current Status**: **Production-Ready Prototype (109 / 109 Automated Tests Passing — 100% PASS)**  
> **Target Platforms**: **macOS (MacBook Air M2)** for local camera + AI + speech verification $\rightarrow$ **Raspberry Pi 5 (8 GB)** for physical hardware deployment.  
> **Key Documents**:
> - [**`yourside.md`**](./yourside.md): **User handoff & action guide** (what's done, Mac verification steps, permissions, Pi 5 deployment).
> - [**`TEST_REPORT.md`**](./TEST_REPORT.md): **Complete test report** (benchmarks, inference latencies, detections, audio tests).
> - [**`MODEL_SELECTION.md`**](./MODEL_SELECTION.md): **Model selection & evaluation** (architecture, taxonomy, preprocessing, checksums).
> - [**`HARDWARE_DEPLOYMENT_GUIDE.md`**](./HARDWARE_DEPLOYMENT_GUIDE.md): **Raspberry Pi hardware guide** (wiring, GPIO safety, 12 milestones).

---

## 1. Project Overview

The **Visual Impairment Support System (VISS)** is an assistive wearable device designed to help visually impaired individuals navigate safely. It combines:
- **Ultrasonic Distance Ranging**: Detects obstacles in the forward walking path (HC-SR04).
- **Computer Vision**: Identifies people, animals, and vehicles in real time (MobileNet-SSD).
- **Spoken Voice Announcements**: Speaks detected objects through wired or Bluetooth earphones (offline TTS via `pyttsx3` + `espeak-ng`).
- **Acoustic Proximity Alerts**: Warns the user of obstacles through acoustic beeps (active buzzer).
- **Emergency Distress Messaging**: Sends an automated distress SMS with location details when a physical push button is pressed (SIM800L GSM).

---

## 2. Completed Implementation Phases

### Phase 1: Architecture, Configuration & Hardware Abstraction
1. **Central Configuration (`config/settings.py`)**: Centralizes GPIO pin assignments, distance bands, vision parameters, alert timings, and runtime flags.
2. **Core Domain Models (`core/models.py`)**: Clean Python dataclasses for sensor readings, object detections, and emergency events.
3. **Hardware Abstraction Layer (`hardware/base.py`)**: Standard abstract interfaces (`ABC`) for distance sensing, camera capture, buzzer, GSM modem, and push button.
4. **Mock Driver Implementations (`hardware/mock/`)**: Software simulators for all hardware components running on macOS with zero physical wires.

### Phase 2: Core Decision Engine & SMS Alert Coordinator
1. **Distance Decision Engine (`core/engine.py`)**:
   - Maps ultrasonic distances to acoustic patterns:
     - `< 0.40 m`: `CONTINUOUS` tone.
     - `0.40 m` to `< 0.80 m`: `FAST_BEEP` (80 ms on / 80 ms off).
     - `0.80 m` to `< 1.50 m`: `SLOW_BEEP` (150 ms on / 250 ms off).
     - `>= 1.50 m`: `OFF`.
   - **Boundary Precision**: Explicitly tested at exact thresholds (0.40m, 0.80m, 1.50m).
   - **Invalid Reading Safety**: Sensor timeouts or invalid readings are **never** treated as confirmed clear space. Under the default `MAINTAIN_LAST` policy, active obstacle warnings are maintained during transient dropouts.
2. **Camera-Arming Modes**:
   - **Default Safety Mode (`require_vision_for_buzzer=False`)**: Proximity alerts trigger for *any* obstacle in the user's path, regardless of whether the camera detects a person, car, or animal.
   - **Black Book Compatibility Mode (`require_vision_for_buzzer=True`)**: Preserves the original project's arming gate (`armed = (now - last_seen_ts) <= 1.0s`).
3. **Emergency SMS Coordinator (`core/sms_coordinator.py`)**:
   - Implements the exact Black Book SMS payload with location URL and fallback.
   - **Duplicate Suppression**: Configurable cooldown period (default: 10.0s) prevents repeated SMS messages on rapid button presses.

### Phase 3: Vision Detection Pipeline
1. **MobileNet-SSD Object Detector (`vision/detector.py`)**:
   - Implements the Black Book's Caffe deep learning model approach (`cv2.dnn`).
   - Evaluates the 20-class Pascal VOC taxonomy with target entity filtering (`person`, `dog`, `cat`, `car`).
   - Configurable confidence threshold (`0.50` default).
2. **Inference Engine Abstraction**:
   - `StubInferenceEngine`: Lightweight in-memory stub for testing without binary weights or OpenCV.
   - `OpenCVInferenceEngine`: Real Caffe DNN inference engine supporting configurable `swap_rb` for RGB-to-BGR alignment.
3. **Vision Pipeline & Camera Integration (`vision/pipeline.py`)**:
   - Decoupled `VisionPipeline` adapter connecting `BaseCamera` capture with `ObjectDetector`.
   - Optional macOS webcam driver (`hardware/camera/opencv_camera.py`) with canonical RGB array output.

### Phase 4: End-to-End Application Integration
1. **Application Controller (`core/controller.py`)**:
   - Decoupled threading model running independent `_distance_worker`, `_vision_worker`, and `_button_worker` loops.
   - Independent threads guarantee that slow neural network inference or vision stalls **cannot** block ultrasonic proximity warnings.
2. **Platform-Aware Audio Player (`core/sound_player.py`)**:
   - Native macOS support via `afplay`; Linux/Raspberry Pi support via `aplay`.
   - Synthetic, deterministic alert tones (`sounds/a.wav`, `sounds/h.wav`).
3. **Application Entry Point (`main.py`)**:
   - Supports `--mode mock` (default simulation) and `--mode hardware` (Raspberry Pi physical devices).

### Phase 5B: Production Hardware Drivers (Software Only)
1. **Ultrasonic Distance Sensor (`hardware/distance/gpio_distance.py`)**:
   - Real `GPIODistanceSensor` utilizing `gpiozero.DistanceSensor`.
   - Configurable BCM pins (`TRIG=24`, `ECHO=23`), deferred initialization, and error-resilient exception handling.
2. **CSI Camera Driver (`hardware/camera/picam2_camera.py`)**:
   - Real `PiCamera2Driver` utilizing `picamera2.Picamera2`.
   - Captures standard RGB video frames at configured resolution ($640 \times 480$).
3. **Proximity Buzzer Driver (`hardware/alert/gpio_buzzer.py`)**:
   - Real `GPIOBuzzer` utilizing `gpiozero.Buzzer`.
   - Direct hardware mapping for `CONTINUOUS`, `FAST_BEEP`, `SLOW_BEEP`, and `OFF` states.
4. **Emergency Push Button Driver (`hardware/button/gpio_button.py`)**:
   - Real `GPIOButton` utilizing `gpiozero.Button`.
   - Internal pull-up (`pull_up=True`) and hardware debouncing (`bounce_time=0.05s`).
5. **Serial GSM Modem Driver (`hardware/gsm/serial_gsm.py`)**:
   - Real `SerialGSM` communicating over UART (`/dev/ttyS0` at 9600 baud) via `pyserial`.
   - Implements complete AT command sequence (`AT`, `ATE0`, `AT+CMGF=1`, `AT+CMGS`, payload submission, `+CMGS: OK` confirmation).
6. **Hardware Factory (`hardware/factory.py`)**:
   - `HardwareBundle` container and selection factory (`create_mock_hardware`, `create_production_hardware`, `create_hardware_bundle`).
   - Clean partial initialization rollback and explicit errors when platform dependencies are missing.

---

## 3. Beginner's Guide: Running on macOS

You can run both simulated mode (zero hardware required) and real computer-vision mode (real Mac webcam + real MobileNet-SSD + real spoken voice alerts) directly on macOS.

### Quick Start with `./run.sh` (Recommended)
The repository includes an automated test runner script `run.sh` that detects your virtual environment automatically:

```bash
# Make executable (if not already)
chmod +x run.sh

# 1. Run full automated verification (tests + diagnostics + 5s demo)
./run.sh

# 2. Test object detection on a sample image with voice announcement
./run.sh image

# 3. Test object detection on pedestrians/people
./run.sh image vision/test_assets/sample_person.png

# 4. Run real-time webcam detection with voice alerts (15 seconds)
./run.sh pipeline 15

# 5. Run the full VISS controller in macOS real mode
./run.sh mac 20

# 6. Run full unit and integration test suite (109 tests)
./run.sh test
```

### Manual Virtual Environment Setup (Python 3.12 Recommended)
```bash
# Create venv using Python 3.12 (avoids Homebrew Python 3.14 wheel limitations)
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements-mac.txt
```

---

## 4. Running the Full Test Suite

You can run the full suite of **109 automated unit and integration tests** using either pytest or Python's built-in `unittest` runner:
 
```bash
# Using pytest
./venv/bin/pytest tests/

# Using standard library unittest
./run.sh test
```
 
All 109 tests run offline and in-memory using deterministic stubs and mocks without requiring hardware, camera devices, audio output devices, or network connectivity.

---

## 5. Execution Modes: Mock, Mac, and Hardware

The application supports three distinct execution modes via the `--mode` command-line flag:

| Mode | Command | Target Machine | Behavior |
| :--- | :--- | :--- | :--- |
| **Mock Simulation** (Default) | `python3 main.py --mode mock` | macOS (MacBook Air M2) / CI | Uses software simulators (`MockDistanceSensor`, `MockCamera`, `MockBuzzer`, `MockButton`, `MockGSM`). Requires **zero** physical hardware or external drivers. |
| **macOS Real Mode** | `python3 main.py --mode mac [--camera-index 0]` | macOS (MacBook Air M2) | Uses **real Mac FaceTime webcam** (`OpenCVCamera`), **real MobileNet-SSD Caffe DNN** (`OpenCVInferenceEngine`), and **real native spoken voice alerts** (`/usr/bin/say`). GPIO sensors/actuators are safely mocked. |
| **Production Hardware** | `python3 main.py --mode hardware` | Raspberry Pi 5 / 4 (8 GB) | Selects physical GPIO, CSI camera, and serial modem drivers (`GPIODistanceSensor`, `PiCamera2Driver`, `GPIOBuzzer`, `GPIOButton`, `SerialGSM`). Requires `gpiozero`, `picamera2`, `pyserial`, and configured wiring. If dependencies are absent, halts immediately with a clear error without silently substituting mocks. |

---

## 6. Sound Alert Architecture & Assets

The system includes a platform-aware audio notification layer (`core/sound_player.py`):
- **macOS**: Uses native `/usr/bin/afplay`.
- **Raspberry Pi / Linux**: Uses ALSA `/usr/bin/aplay`.
- **Test / Mock**: Uses `MockSoundPlayer` (zero subprocesses spawned).

### Alert Sound Files (`sounds/`):
| File | Alert Category | Target Classes | Description |
| :--- | :--- | :--- | :--- |
| `sounds/a.wav` | `animal` | `dog`, `cat` | 880 Hz (A5), 0.25 s tone (higher alert pitch) |
| `sounds/h.wav` | `human` | `person`, `car` | 440 Hz (A4), 0.25 s tone (mid alert pitch) |

These files are synthetically generated using Python's standard library (`wave`, `struct`, `math`) without copyrighted third-party assets:
```bash
python3 scripts/generate_alert_tones.py
```

### Audio Safety:
- Audio alerts run in background daemon threads with a strict 5.0-second timeout, ensuring that audio playback **never blocks** high-frequency ultrasonic proximity ranging.
- If sound files or playback binaries are missing, `SystemSoundPlayer` logs a warning and returns `False` safely without crashing.

---

## 7. Hardware Electrical Safety & Deployment Blockers

> [!CAUTION]
> **READ BEFORE CONNECTING PHYSICAL HARDWARE TO RASPBERRY PI**
> The following electrical and power safety requirements must be satisfied before connecting physical components to prevent permanent damage to the Raspberry Pi SoC or modules.

### 1. HC-SR04 Ultrasonic Sensor Voltage Protection
- **The Risk**: The standard HC-SR04 ultrasonic sensor operates at 5V VCC and outputs a **5V logic HIGH** signal on its `ECHO` pin. Raspberry Pi GPIO pins are rated for a **maximum of 3.3V**. Connecting a 5V ECHO signal directly to GPIO 23 will **permanently destroy the GPIO pin or the Pi 4 SoC**.
- **Required Protection**: You **must** use a voltage divider or a 3.3V bidirectional logic level shifter between the HC-SR04 ECHO pin and Raspberry Pi GPIO 23:
  - **Voltage Divider**: Connect HC-SR04 ECHO $\rightarrow$ $1\text{ k}\Omega$ resistor $\rightarrow$ Pi GPIO 23 $\rightarrow$ $2\text{ k}\Omega$ resistor $\rightarrow$ GND. This steps 5V down to $5\text{V} \times \frac{2000}{1000 + 2000} \approx 3.33\text{V}$.
  - **Alternative Sensor**: Use an **HC-SR04P** or **RCWL-1601**, which natively supports 3.3V operation.

### 2. SIM800L GSM Module Power Supply
- **The Risk**: The SIM800L module operates strictly between **3.4V and 4.4V** (recommended **3.7V to 4.2V**) and draws **peak transmission burst currents up to 2.0A**.
- **Do NOT Power from Raspberry Pi**:
  - Connecting SIM800L to the Pi's **5V rail** exceeds the module's 4.4V absolute maximum rating and will **permanently destroy** the SIM800L.
  - Connecting SIM800L to the Pi's **3.3V rail** will result in brownouts, boot-loops, and cellular registration failures because the Pi 3.3V regulator cannot deliver 2A bursts.
- **Required Power Supply**: Use a dedicated 3.7V Li-ion battery (such as an 18650 cell with battery protection circuit) or a high-current step-down buck converter (e.g., LM2596 tuned to 4.0V). **The battery/supply ground must be tied to Raspberry Pi GND** to maintain a common ground reference.

### 3. Production Hardware Verification Status
- Although production driver software has been written and verified against unit tests with mocks, **actual physical testing has NOT been performed**.
- Real-world acoustic sound pressure levels, sensor noise, beam reflections, camera optics, UART timing, and cellular transmission remain unverified on hardware.

---

## 8. Model Files & Weights Setup (Optional for Local Video Testing)

Per project policy, binary neural network weights (~23 MB) are **not** bundled or committed into Git. All unit tests use `StubInferenceEngine` to run offline with zero downloads.

If you wish to test with live video on your Mac or when deploying to the Raspberry Pi:
```bash
# 1. Download network prototxt architecture definition
curl -L -o vision/weights/MobileNetSSD_deploy.prototxt \
  https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/voc/MobileNetSSD_deploy.prototxt

# 2. Download pre-trained Caffe weights (~23 MB)
curl -L -o vision/weights/MobileNetSSD_deploy.caffemodel \
  https://github.com/chuanqi305/MobileNet-SSD/raw/master/MobileNetSSD_deploy.caffemodel
```

---

## 9. Project Directory Structure

```
viss_project/
├── .gitignore                      # Excludes bytecode, venvs, model weights, logs, and secrets
├── HARDWARE_DEPLOYMENT_GUIDE.md    # Master Raspberry Pi 4/5 hardware wiring, testing & deployment guide
├── MODEL_SELECTION.md              # Model architecture, taxonomy, checksums, and latency evaluation
├── PROJECT_REFERENCE_REVIEW.md     # Reference document extraction & conflict review
├── README.md                       # Setup, architectural decisions, and testing guide
├── TEST_REPORT.md                  # Comprehensive macOS test report, benchmarks & verification results
├── yourside.md                     # Beginner-friendly handoff guide & step-by-step actions for user
├── run.sh                          # Laptop simulation, testing, and real vision runner script
├── requirements.txt                # Core dependencies (OpenCV <5.0.0, NumPy, pyttsx3)
├── requirements-mac.txt            # macOS pinned development & testing dependencies
├── requirements-pi.txt             # Raspberry Pi deployment dependencies (APT & pip)
├── main.py                         # Application bootstrap entry point (--mode mock|mac|hardware)
├── config/
│   ├── __init__.py
│   └── settings.py                 # Central configuration (pins, thresholds, vision, emergency, runtime)
├── core/
│   ├── __init__.py                 # Clean lazy module exports (PEP 562)
│   ├── controller.py               # ApplicationController & thread coordination (create_mac_real)
│   ├── engine.py                   # DecisionEngine & InvalidReadingPolicy
│   ├── logger.py                   # Structured console logging
│   ├── models.py                   # Dataclasses & enums (Detection, BoundingBox, etc.)
│   ├── sms_coordinator.py          # SMSCoordinator & message formatting
│   ├── sound_player.py             # Platform-aware SoundPlayer (afplay/aplay/mock)
│   └── voice_alert.py              # Offline spoken voice announcements (/usr/bin/say, pyttsx3)
├── hardware/
│   ├── __init__.py
│   ├── base.py                     # Abstract Base Classes (BaseDistanceSensor, BaseCamera, etc.)
│   ├── alert/
│   │   ├── __init__.py
│   │   └── gpio_buzzer.py          # Real GPIO active buzzer driver (gpiozero)
│   ├── button/
│   │   ├── __init__.py
│   │   └── gpio_button.py          # Real GPIO push button driver (gpiozero)
│   ├── camera/
│   │   ├── __init__.py
│   │   ├── opencv_camera.py        # Mac webcam driver using OpenCV (RGB contract)
│   │   └── picam2_camera.py        # Real Pi Camera V2/V3 driver (Picamera2)
│   ├── distance/
│   │   ├── __init__.py
│   │   └── gpio_distance.py        # Real HC-SR04 ultrasonic distance driver (gpiozero)
│   ├── factory.py                  # Hardware bundle factory (mock vs production)
│   ├── gsm/
│   │   ├── __init__.py
│   │   └── serial_gsm.py           # Real SIM800L cellular UART driver (pyserial)
│   └── mock/
│       ├── __init__.py
│       ├── mock_button.py          # Emergency push button simulator
│       ├── mock_buzzer.py          # Proximity buzzer simulator
│       ├── mock_camera.py          # Video capture simulator
│       ├── mock_distance.py        # HC-SR04 distance simulator
│       ├── mock_gsm.py             # SIM800L cellular modem simulator
│       └── mock_location.py        # Geolocation simulator
├── scripts/
│   ├── generate_alert_tones.py     # Deterministic WAV alert tone generator (standard library)
│   ├── test_audio_voice.py         # Earphone audio & spoken TTS test script
│   ├── test_button.py              # Emergency push button test script
│   ├── test_camera.py              # CSI camera capture & resolution test script
│   ├── test_distance_sensor.py     # HC-SR04 ultrasonic distance test script
│   ├── test_gsm_uart.py            # SIM800L serial UART communication test script
│   ├── test_image_inference.py     # Still image MobileNet-SSD detection & TTS announcement
│   ├── test_live_inference.py       # Live camera inference + spoken alert test script
│   ├── test_mac_webcam.py          # Mac webcam OpenCV capture diagnostic
│   ├── test_model_smoke.py         # MobileNet-SSD model loading smoke test
│   ├── test_real_pipeline_mac.py   # Live Mac webcam -> neural network -> spoken alert pipeline
│   └── verify_hardware_readiness.py# Hardware readiness diagnostic checklist tool
├── sounds/
│   ├── README.md                   # Alert sound documentation & licensing
│   ├── a.wav                       # Animal alert tone (880 Hz, 0.25s)
│   └── h.wav                       # Human/car alert tone (440 Hz, 0.25s)
├── vision/
│   ├── __init__.py
│   ├── detector.py                 # MobileNet-SSD ObjectDetector & inference engines
│   ├── pipeline.py                 # VisionPipeline adapter
│   ├── test_assets/
│   │   ├── sample_cat.jpg          # Test image for animal detection
│   │   └── sample_person.png       # Test image for pedestrian detection
│   └── weights/
│       ├── MobileNetSSD_deploy.caffemodel  # Pretrained weights (23.3 MB)
│       ├── MobileNetSSD_deploy.prototxt    # Deploy prototxt (29.4 KB)
│       └── README.md                       # Model file instructions and preprocessing specs
└── tests/
    ├── __init__.py
    ├── test_application_controller.py# Lifecycle, thread independence, and integration tests
    ├── test_config.py              # Configuration & environment override tests
    ├── test_decision_engine.py     # Boundary, arming, and error policy tests
    ├── test_emergency_coordinator.py# SMS format, fallback, and cooldown tests
    ├── test_mock_hardware.py       # Mock hardware contract tests
    ├── test_models.py              # Dataclass & validation tests
    ├── test_production_hardware.py # Production hardware drivers & factory mock tests
    ├── test_real_vision_audio.py   # Real vision & voice alert integration tests (9 tests)
    ├── test_sound_player.py        # Sound player fallback, lifecycle, and format tests
    └── test_vision_detector.py     # Detection parsing, filtering, and color tests
```

---

## 10. Known Limitations & Technical Realities

1. **Vocabulary Limitation**: MobileNet-SSD was trained on the 20 Pascal VOC classes. It can classify `person`, `car`, `dog`, and `cat`, but **cannot** detect or classify static navigation hazards like walls, pillars, glass doors, curbs, or drop-offs. Proximity safety must rely primarily on ultrasonic ranging.
2. **Lighting Sensitivity**: In dim or nighttime environments, optical camera contrast degrades significantly (observed ~85% accuracy in reference report Table 6.1). Ultrasonic distance sensing remains unaffected by lighting conditions.
3. **No Embedded GPU**: On the Raspberry Pi 4 CPU, MobileNet-SSD inference runs at ~5 to 10 FPS. Frame resizing to $320 \times 240$ and blob input of $300 \times 300$ are necessary to maintain interactive latency.
4. **Safety Disclaimer**: This system is an educational engineering prototype. It is **not rated or certified** for real-world navigation or safety-critical use.

