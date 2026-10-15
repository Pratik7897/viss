# VISS — Raspberry Pi 4 Model B Hardware Integration and Deployment Guide

> **Authoritative Deployment Reference**  
> **Target Platform**: Raspberry Pi 4 Model B (8 GB RAM) running Raspberry Pi OS (Bookworm 64-bit)  
> **Development Host**: MacBook Air M2 (macOS)  
> **Primary Objective**: Real-time camera-based object detection with offline spoken announcements through earphones.

---

## Table of Contents

1. [Executive Summary & Primary Objective](#1-executive-summary--primary-objective)
2. [Hardware Inventory & Readiness Checklist](#2-hardware-inventory--readiness-checklist)
3. [Raspberry Pi 4 Master GPIO Wiring Table](#3-raspberry-pi-4-master-gpio-wiring-table)
4. [Primary Objective Integration: Camera + Earphone Voice Alerts](#4-primary-objective-integration-camera--earphone-voice-alerts)
   - [4.1 Safe CSI Camera Ribbon Cable Installation](#41-safe-csi-camera-ribbon-cable-installation)
   - [4.2 Earphone Setup (Wired 3.5mm & Bluetooth)](#42-earphone-setup-wired-35mm--bluetooth)
   - [4.3 Offline Text-to-Speech (TTS) Engine Installation](#43-offline-text-to-speech-tts-engine-installation)
   - [4.4 MobileNet-SSD Neural Network Model Installation](#44-mobilenet-ssd-neural-network-model-installation)
   - [4.5 Verification: Live Camera Detection + Spoken Voice Announcements](#45-verification-live-camera-detection--spoken-voice-announcements)
5. [Secondary Sensor & Peripheral Integration](#5-secondary-sensor--peripheral-integration)
   - [5.1 HC-SR04 Ultrasonic Distance Sensor & 3.3V Echo Protection](#51-hc-sr04-ultrasonic-distance-sensor--33v-echo-protection)
   - [5.2 Emergency Push Button (Tactile Switch)](#52-emergency-push-button-tactile-switch)
   - [5.3 Acoustic Buzzer Driver & Transistor Circuit](#53-acoustic-buzzer-driver--transistor-circuit)
   - [5.4 SIM800L GSM Modem & UART Integration](#54-sim800l-gsm-modem--uart-integration)
6. [Ordered 12-Milestone Deployment Plan](#6-ordered-12-milestone-deployment-plan)
7. [Raspberry Pi OS Installation & Environment Setup](#7-raspberry-pi-os-installation--environment-setup)
8. [Application Startup & Operational Commands](#8-application-startup--operational-commands)
9. [Troubleshooting Guide (Based on Project Code)](#9-troubleshooting-guide-based-on-project-code)
10. [Safety Blockers & Unresolved Hardware Questions](#10-safety-blockers--unresolved-hardware-questions)

---

## 1. Executive Summary & Primary Objective

The **Visual Impairment Support System (VISS)** is an assistive navigation device designed to assist visually impaired individuals in detecting environmental hazards.

### The Primary Objective
The highest priority is:
1. **Capturing live video frames** from the physical Raspberry Pi camera.
2. **Running neural network inference** in real time using MobileNet-SSD to detect target obstacles (`person`, `car`, `dog`, `cat`).
3. **Announcing detected objects through earphones** using an offline Text-to-Speech (TTS) synthesizer without blocking video streaming.

```
+--------------------+      +--------------------+      +----------------------+      +----------------------+
|  RPi Camera Module | ---> | OpenCV DNN         | ---> | VoiceAlertPlayer     | ---> | Earphones            |
|  (CSI / Picamera2) | RGB  | (MobileNet-SSD)    |      | (pyttsx3 + espeak-ng)|      | (3.5mm / Bluetooth)  |
+--------------------+      +--------------------+      +----------------------+      +----------------------+
                                                                                           "Person detected"
```

To eliminate risk to your Raspberry Pi 4 hardware, **hardware deployment follows a strict staged sequence**:
- **Stage 1 (Milestones 1–8)**: Boot the Pi, install camera, earphones, speech engine, and model files. Verify the full Computer Vision + Spoken Voice pipeline **before connecting any external GPIO breadboards or sensors**.
- **Stage 2 (Milestones 9–12)**: Add the ultrasonic distance sensor (with required voltage divider), emergency push button, buzzer, and SIM800L GSM modem.

---

## 2. Hardware Inventory & Readiness Checklist

Every item in this inventory is classified as either **Confirmed by Source Code** or **Requires Physical Inspection / Safety Verification**.

| Component | Code Status | Physical Verification Needed | Safety / Readiness Action |
|---|---|---|---|
| **Raspberry Pi 4 Model B (8 GB)** | Confirmed (`config/settings.py`, `requirements-pi.txt`) | Check USB-C Power Supply rating (requires 5.0V / 3.0A minimum). | Use official 15W USB-C PSU. Insufficient current causes brownouts and camera crashes. |
| **MicroSD Card (32 GB - 128 GB)** | Required for OS | Class 10 / U3 / A2 high-speed card. | Flash Raspberry Pi OS Bookworm 64-bit (Lite or with Desktop). |
| **RPi Camera Module V2 (or V1/V3)** | Confirmed (`hardware/camera/picam2_camera.py`) | Inspect 15-pin ribbon cable for tears; verify connector orientation. | **DO NOT plug or unplug while Pi is powered.** Connect to CSI port (between HDMI and 3.5mm audio). |
| **Earphones (Wired 3.5mm or Bluetooth)** | Confirmed (`core/voice_alert.py`, `core/sound_player.py`) | Check jack type (standard 3.5mm stereo/TRRS) or Bluetooth connectivity. | 3.5mm plugs into the Pi 4 audio jack; Bluetooth pairs via `bluetoothctl`. |
| **HC-SR04 Ultrasonic Distance Sensor** | Confirmed (`hardware/distance/gpio_distance.py`) | Confirm sensor operating voltage ($5.0\text{V}$). | **CRITICAL SAFETY BLOCKER:** ECHO pin outputs $5.0\text{V}$. Raspberry Pi GPIO is rated for $3.3\text{V}$ max. **A voltage divider ($1\text{ k}\Omega$ and $2\text{ k}\Omega$ resistors) is mandatory.** |
| **SIM800L GSM Breakout Board** | Confirmed (`hardware/gsm/serial_gsm.py`) | **CRITICAL:** Inspect board model markings and voltage rating. | **DO NOT connect to Pi 5V or 3.3V power rails.** Requires external $3.7\text{V} - 4.4\text{V}$ power source capable of $2.0\text{A}$ pulse bursts (e.g. 18650 Li-ion cell or LM2596 buck converter). Must share common ground with Pi. Antenna must be attached. |
| **2G/GSM Compatible SIM Card** | Required by SIM800L | Verify carrier supports 2G (850/900/1800/1900 MHz) in your area. | Must have active SMS plan and PIN lock removed before insertion. |
| **Tactile Push Buttons (2 available)** | Confirmed: 1 Button (`hardware/button/gpio_button.py`) | Verify pin continuity with multimeter; identify normally-open (NO) contacts. | **Current software only uses 1 button (Emergency SOS on GPIO 17).** Button 2 is spare/unassigned in code. |
| **Two-Terminal Buzzer / Sounder** | Confirmed (`hardware/alert/gpio_buzzer.py`) | **CRITICAL:** Identify whether buzzer is **ACTIVE** or **PASSIVE**. | An active buzzer has an internal oscillator and sounds on DC. A passive buzzer needs PWM frequency. Pi GPIO output limit is $\sim 16\text{ mA}$; direct buzzer connection can overdraw current. **NPN transistor driver recommended.** |
| **Jumper Wires & Resistors** | Essential accessories | Need $1\text{ k}\Omega$ and $2\text{ k}\Omega$ (or $2.2\text{ k}\Omega$) resistors for voltage divider. | Inspect breadboard and jumper wires for loose Dupont pins. |

---

## 3. Raspberry Pi 4 Master GPIO Wiring Table

The table below lists all GPIO pin assignments derived directly from `config/settings.py` (`PinConfig`). **Zero pin conflicts exist** in the project's pin map.

```
                     Raspberry Pi 4 - 40 Pin Header (J8)
                                    +-----+
           +3.3V DC Power (Pin 1)   | 1  2|   +5.0V DC Power (Pin 2)   ---> HC-SR04 VCC
                                    | 3  4|   +5.0V DC Power (Pin 4)
                                    | 5  6|   Ground / GND   (Pin 6)   ---> Common Ground
                                    | 7  8|   BCM GPIO 14 (TXD0, Pin 8) ---> SIM800L RXD
        Common Ground (Pin 9)       | 9 10|   BCM GPIO 15 (RXD0, Pin 10)<--- SIM800L TXD
Button Pin 1 ---> BCM GPIO 17 (Pin 11)|11 12|   BCM GPIO 18 (Pin 12)     ---> Buzzer Driver Base
                                    |13 14|   Ground / GND   (Pin 14)  ---> Button Pin 2
HC-SR04 ECHO (via divider) -> GPIO 23|15 16|
HC-SR04 TRIG              -> GPIO 24|17 18|   Ground / GND   (Pin 20)
                                    | ... |
                                    +-----+
```

### Complete Pinout Specification

| BCM GPIO # | Physical Pin # | Signal Name | Direction | Connected Device & Pin | Electrical Description & Safety Protection |
|---|---|---|---|---|---|
| **—** | **Pin 2 or 4** | `+5V0` | Output | **HC-SR04 VCC** | $5.0\text{V}$ power rail supplied from Raspberry Pi USB-C input. |
| **—** | **Pin 6 / 9 / 14 / 20** | `GND` | Ground | **Common System Ground** | Common ground for HC-SR04, push button, buzzer, and external SIM800L battery. |
| **GPIO 14** | **Pin 8** | `UART0_TXD` | Output | **SIM800L RXD** | $3.3\text{V}$ logic serial transmit from Pi to modem. (Baud: 9600). |
| **GPIO 15** | **Pin 10** | `UART0_RXD` | Input | **SIM800L TXD** | Serial receive from modem to Pi ($2.8\text{V} - 3.3\text{V}$ logic level). |
| **GPIO 17** | **Pin 11** | `GPIO_GEN0` | Input | **Emergency Push Button Terminal 1** | Configured with internal pull-up (`pull_up=True`). Terminal 2 connects to GND. Shorting to GND triggers SOS. |
| **GPIO 18** | **Pin 12** | `GPIO_GEN1` (PWM0) | Output | **Acoustic Buzzer Driver (Transistor Base)** | $3.3\text{V}$ logic output. Drives base of NPN transistor through $1\text{ k}\Omega$ resistor. |
| **GPIO 23** | **Pin 16** | `GPIO_GEN4` | Input | **HC-SR04 ECHO (Divided to 3.3V)** | **PROTECTED INPUT.** Connected to junction of $1\text{ k}\Omega$ and $2\text{ k}\Omega$ voltage divider. **Never connect directly to 5V ECHO.** |
| **GPIO 24** | **Pin 18** | `GPIO_GEN5` | Output | **HC-SR04 TRIG** | $3.3\text{V}$ trigger pulse from Pi. ($3.3\text{V}$ is recognized as logic HIGH by HC-SR04). |
| **—** | **CSI Port** | `MIPI CSI-2` | Bi-dir | **Raspberry Pi Camera Ribbon** | 15-pin flat flexible ribbon cable connected to CSI connector between HDMI 0 and 3.5mm jack. |
| **—** | **3.5mm Jack** | `Audio Output` | Output | **Wired Earphones** | 4-pole TRRS analog audio jack controlled via ALSA / `aplay`. |

> [!NOTE]
> **Push Button #2 Status**: The workspace code currently only references one button (`emergency_button` on BCM 17 in `config/settings.py`). The second physical button is currently unassigned. If desired in future iterations, it can be assigned to an unused pin (e.g., BCM GPIO 27, Pin 13) for user-facing features like audio status queries.

---

## 4. Primary Objective Integration: Camera + Earphone Voice Alerts

This section covers the primary objective: **live camera capture, MobileNet-SSD detection, and spoken voice alerts through earphones**.

### 4.1 Safe CSI Camera Ribbon Cable Installation

```
            +--------------------------------------------+
            |             Raspberry Pi 4 Model B         |
            |                                            |
            |  [USB-C Power]   [HDMI 0]  [HDMI 1]  [AUDIO|
            |                                        JACK|
            |                            +--------+      |
            |                            |CAMERA  |      |
            |                            |CSI PORT|      |
            |                            +--------+      |
            +--------------------------------------------+
```

#### Step-by-Step Installation Safety Protocol:
1. **POWER OFF THE RASPBERRY PI COMPLETELY.** Unplug the USB-C power supply. Never connect or disconnect the camera ribbon cable while the board is powered.
2. **Locate the CSI Camera Port**: On the Raspberry Pi 4, the camera port is located **between the micro-HDMI 1 port and the 3.5mm audio jack**. (Do not confuse it with the DSI display port located near the USB-C power jack).
3. **Open the Connector Collar**: Gently pull up both sides of the black plastic clip on the camera port. It slides upward $\sim 2\text{ mm}$.
4. **Insert the Ribbon Cable**:
   - The **blue plastic stiffener strip** must face toward the **3.5mm audio jack / Ethernet & USB ports**.
   - The **silver/gold conductive contacts** must face toward the **micro-HDMI ports**.
   - Ensure the cable is inserted straight and fully seated to the bottom of the slot.
5. **Lock the Collar**: Press the black plastic clip straight down until it clicks securely and sits flush with the port.
6. **Connect the Sensor Board**: If your ribbon cable is detached from the camera sensor board itself, repeat the procedure on the camera module: silver contacts face the camera lens, blue tape faces the back of the camera PCB.

#### Operating System Camera Verification:
Power on the Raspberry Pi 4 and run:
```bash
# Check if libcamera recognizes the sensor:
rpicam-hello --list-cameras
```
*Expected Output:*
```text
Available cameras:
0 : imx219 [3280x2464 10-bit RGGB] (/base/soc/i2c0mux/i2c@1/imx219@10)
    Modes: 'SRGGB10_CSI2P' : 640x480 [206.65 fps - ...]
```

Capture a test frame using the native Raspberry Pi camera utility:
```bash
rpicam-still -o test_raw.jpg -t 2000
```

Verify camera capture using the project's camera driver:
```bash
python3 scripts/test_camera.py --output frame.jpg
```
*Expected Output:*
```text
[PASS] Successfully captured frame!
  Shape: (480, 640, 3)
  Type:  uint8
  Size:  921600 bytes
  Saved test image preview to 'frame.jpg' via PIL/OpenCV.
```

---

### 4.2 Earphone Setup (Wired 3.5mm & Bluetooth)

#### Option A: Wired 3.5mm Earphones (Recommended for low latency)
1. Plug your earphones into the 3.5mm TRRS jack on the Raspberry Pi 4.
2. Direct audio output to the 3.5mm jack:
   ```bash
   sudo raspi-config
   # Select: 1 System Options -> S2 Audio -> 1 Headphones (3.5mm jack) -> Finish
   ```
3. Test sound playback via ALSA:
   ```bash
   aplay /usr/share/sounds/alsa/Front_Center.wav
   # Or using speaker-test:
   speaker-test -t wav -c 2 -l 1
   ```

#### Option B: Bluetooth Earphones
1. Launch `bluetoothctl` in terminal:
   ```bash
   bluetoothctl
   ```
2. Put your Bluetooth earphones into pairing mode, then execute:
   ```text
   power on
   agent on
   default-agent
   scan on
   ```
3. Locate your earphone's MAC address (e.g., `XX:XX:XX:XX:XX:XX`) and run:
   ```text
   pair XX:XX:XX:XX:XX:XX
   connect XX:XX:XX:XX:XX:XX
   trust XX:XX:XX:XX:XX:XX
   quit
   ```
4. Verify playback through Bluetooth with `aplay /usr/share/sounds/alsa/Front_Center.wav`.

---

### 4.3 Offline Text-to-Speech (TTS) Engine Installation

Spoken announcements are generated completely offline using `pyttsx3` with the `espeak-ng` speech synthesis backend.

1. Install system speech synthesizer and ALSA audio utilities:
   ```bash
   sudo apt update
   sudo apt install -y espeak-ng alsa-utils
   ```
2. In your virtual environment, install `pyttsx3`:
   ```bash
   pip install pyttsx3>=2.90
   ```
3. Test speech directly through your earphones:
   ```bash
   python3 scripts/test_audio_voice.py
   ```
   *You should hear a prompt sound followed by clearly articulated spoken phrases: `"person detected"` and `"car detected"` through your earphones.*

---

### 4.4 MobileNet-SSD Neural Network Model Installation

Per project rules, binary neural network weights are not bundled in Git. Download the official pre-trained Caffe MobileNet-SSD model files:

```bash
cd /Users/pratikshinde/viss_project  # On Pi: cd ~/viss_project

# 1. Download network structure prototxt (~29 KB):
curl -L -o vision/weights/MobileNetSSD_deploy.prototxt \
  https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/voc/MobileNetSSD_deploy.prototxt

# 2. Download pre-trained weights (~23 MB):
curl -L -o vision/weights/MobileNetSSD_deploy.caffemodel \
  https://github.com/chuanqi305/MobileNet-SSD/raw/master/MobileNetSSD_deploy.caffemodel
```

Verify file presence and sizes:
```bash
ls -lh vision/weights/
# MobileNetSSD_deploy.prototxt   ~29 KB
# MobileNetSSD_deploy.caffemodel ~23 MB
```

---

### 4.5 Verification: Live Camera Detection + Spoken Voice Announcements

Run the end-to-end integration script to test live object detection and spoken alerts together:

```bash
python3 scripts/test_live_inference.py --duration 20 --confidence 0.50
```

**Expected Operation**:
1. Camera starts streaming RGB video frames at $640 \times 480$ resolution.
2. OpenCV DNN resizes and feeds frames into MobileNet-SSD.
3. When a person steps in front of the camera, the console logs:
   ```text
   [12:45:02] Detected targets: person
      -> PERSON (confidence: 0.84, bbox: (140, 60, 420, 460))
   ```
4. Within $< 300\text{ ms}$, your earphones speak: **"Person detected"**.
5. When the person remains in view, the per-label cooldown ($3.0\text{s}$) prevents repetitive announcements.
6. When the person leaves and reappears, the system announces them again.

**Milestones 1 through 8 are now complete.**

---

## 5. Secondary Sensor & Peripheral Integration

After the primary camera + voice alerts objective is confirmed functional, integrate the secondary sensor hardware.

### 5.1 HC-SR04 Ultrasonic Distance Sensor & 3.3V Echo Protection

#### The Electrical Problem:
- The HC-SR04 operates at $5.0\text{V}$ and produces a $5.0\text{V}$ logic HIGH pulse on its `ECHO` pin.
- Raspberry Pi GPIO pins are rated for **maximum $3.3\text{V}$**.
- Connecting the `ECHO` pin directly to GPIO 23 will permanently damage the GPIO pin or the SoC processor.

#### Verified Voltage Divider Circuit:
To safely drop $5.0\text{V}$ down to $\sim 3.33\text{V}$, use two resistors ($R_1 = 1\text{ k}\Omega$ and $R_2 = 2\text{ k}\Omega$, or $R_2 = 2.2\text{ k}\Omega$):

```
       HC-SR04
     +---------+
     |     VCC |--------------------------------------> RPi Pin 2 (+5.0V)
     |         |
     |    TRIG |--------------------------------------> RPi Pin 18 (BCM GPIO 24)
     |         |             R1 (1 kOhm)
     |    ECHO |------------[/\/\/\/\/\\]---+---------> RPi Pin 16 (BCM GPIO 23)
     |         |                           |
     |     GND |---------------+           [ R2 (2 kOhm)
     +---------+               |           [
                               |           |
     RPi Pin 6 / Pin 14 (GND) -+-----------+----------> Common GND
```

#### Voltage Formula Verification:
$$V_{\text{out}} = V_{\text{in}} \times \left( \frac{R_2}{R_1 + R_2} \right) = 5.0\text{V} \times \left( \frac{2000}{1000 + 2000} \right) = 5.0\text{V} \times 0.6667 = 3.33\text{V}$$
*(Safe for Raspberry Pi 3.3V GPIO).*

#### Testing Ultrasonic Distance:
Once wired according to the schematic:
```bash
python3 scripts/test_distance_sensor.py --trig 24 --echo 23 --duration 15
```
Move your hand between $10\text{ cm}$ and $100\text{ cm}$ in front of the two sensor cylinders. Verify stable distance measurements in centimeters on the terminal.

---

### 5.2 Emergency Push Button (Tactile Switch)

The tactile push button triggers the emergency SMS dispatch coordinator (`core/sms_coordinator.py`).

```
                Push Button (Normally Open)
     RPi Pin 11           +-------+
    (BCM GPIO 17) ------->| o   o |<------- RPi Pin 9 / Pin 14 (GND)
                          +-------+
```

#### Electrical Operation:
1. `hardware/button/gpio_button.py` configures `gpiozero.Button(pin=17, pull_up=True, bounce_time=0.05)`.
2. When the button is NOT pressed, the internal $50\text{ k}\Omega$ pull-up resistor pulls GPIO 17 to $3.3\text{V}$ (logic HIGH).
3. When pressed, the contacts close and pull GPIO 17 directly to `GND` (logic LOW).
4. No external resistors are required.
5. Hardware debouncing ($50\text{ ms}$) eliminates mechanical switch bouncing.

#### Verification Command:
```bash
python3 scripts/test_button.py --pin 17 --duration 15
```
Press the button 3 times and confirm that exactly 3 `BUTTON PRESSED` events appear in the console.

---

### 5.3 Acoustic Buzzer Driver & Transistor Circuit

#### 1. Verifying Buzzer Type (Active vs. Passive):
Before connecting the buzzer, determine whether it is **Active** or **Passive**:
- **Test**: Touch the two terminals of the buzzer briefly across a $3\text{V}$ button cell battery (CR2032) or a $3.3\text{V}$ bench supply.
  - If it emits a **continuous, distinct audible tone**, it is an **Active Buzzer** (supported by `gpiozero.Buzzer`).
  - If it emits only a **single faint click** on contact and release, it is a **Passive Buzzer** (requires a PWM frequency generator, not currently supported by direct on/off GPIO logic).

#### 2. Transistor Driver Circuit (Safety Precaution):
Raspberry Pi GPIO pins can supply a maximum of $\sim 16\text{ mA}$. Standard buzzers often draw $25\text{ mA} - 50\text{ mA}$. Directly connecting the buzzer between GPIO 18 and GND risks blowing the pin. Use an inexpensive NPN transistor (e.g. 2N2222, 2N3904, or BC547):

```
                                  +5.0V (RPi Pin 4)
                                         |
                                         +----+
                                         |    |
                                      +--+--+ |
                                      |     | [D1] Flyback Diode (1N4148 / 1N4001)
                         Active Buzzer| (+) | |    Cathode (striped end) to +5V
                                      |     | |
                                      +--+--+ |
                                         |    |
                                         +----+
                                         |
                                         |  Collector (C)
                                      +--+--+
           R_base (1 kOhm)            |     |  NPN Transistor
RPi Pin 12 --[/\/\/\/\/\\]------------| B   |  (2N2222 / BC547)
(BCM 18)                       Base   |     |
                                      +--+--+
                                         |  Emitter (E)
                                         |
                                        GND (RPi Pin 6 / Pin 14)
```

- When GPIO 18 goes HIGH ($3.3\text{V}$), $\sim 2.6\text{ mA}$ flows into the transistor base, switching the transistor fully ON (saturation) and supplying clean $5\text{V}$ to the buzzer.
- The flyback diode (D1) protects against inductive voltage spikes when the buzzer turns off.

---

### 5.4 SIM800L GSM Modem & UART Integration

#### 1. Physical Inspection & Power Specifications:
The SIM800L cellular modem has strict power requirements:
- **Operating Voltage**: $3.7\text{V}$ to $4.4\text{V}$ ($4.0\text{V}$ nominal).
- **Peak Current**: Up to **$2.0\text{A}$** during cellular network transmission bursts.
- **DO NOT connect SIM800L VCC to Raspberry Pi 5V rail** (causes overvoltage damage to bare SIM800L chips).
- **DO NOT connect SIM800L VCC to Raspberry Pi 3.3V rail** (causes immediate undervoltage brownouts and continuous boot loops).
- **Required Supply**: A dedicated $3.7\text{V}$ 18650 Li-ion battery (with protection board) or an adjustable DC-DC buck converter (e.g., LM2596 tuned to $4.0\text{V}$ with $\ge 2\text{A}$ output).

```
   External 3.7V - 4.2V Battery / LM2596
   +------------------------------------+
   |  (+) 4.0V DC ------------------------------------> SIM800L VCC
   |                                    |
   |  (-) Ground -----------------------+-------------> SIM800L GND
   +------------------------------------+     |
                                              +-------> RPi Pin 6 / 14 (Common GND)
```

#### 2. Serial UART Connections:
Connect the UART cross-over lines:
- **RPi Pin 8 (BCM GPIO 14, TXD0)** $\rightarrow$ **SIM800L RXD**
- **RPi Pin 10 (BCM GPIO 15, RXD0)** $\leftarrow$ **SIM800L TXD**
- **External Power GND** $\rightarrow$ **Raspberry Pi GND (Pin 6 or 14)** *(Mandatory common ground).*

#### 3. Raspberry Pi UART OS Configuration:
By default, Raspberry Pi OS assigns a Linux serial login console to the primary UART. You must free this port for VISS:
1. Run `sudo raspi-config`
2. Navigate to: `3 Interface Options` $\rightarrow$ `I6 Serial Port`
3. *"Would you like a login console to be accessible over serial?"* $\rightarrow$ Select **NO**.
4. *"Would you like the serial port hardware to be enabled?"* $\rightarrow$ Select **YES**.
5. Exit and reboot: `sudo reboot`.
6. Add your user account to the `dialout` group:
   ```bash
   sudo usermod -aG dialout $USER
   ```

#### 4. SIM Card & Antenna Prerequisites:
- Attach the spiral spring antenna or IPEX external antenna to the SIM800L board. **Never power on the modem without an antenna attached**, as transmitting into an open circuit can damage the RF power amplifier.
- Insert a nano-SIM (with adapter if needed) supporting 2G/GSM.
- Verify the SIM card has cellular credit and no PIN lock.
- **Inspect Network LED**:
  - Blinking once every $1\text{s}$: Searching for cellular network.
  - Blinking once every $3\text{s}$: **Successfully registered on cellular network.**
  - Blinking rapidly (every $300\text{ ms}$): GPRS data connection active.

#### 5. Verification Command:
```bash
python3 scripts/test_gsm_uart.py --port /dev/ttyS0 --baud 9600
```
*Expected Output:*
```text
1. Checking AT synchronization on /dev/ttyS0...
[PASS] SIM800L responded OK to AT synchronization!
2. Signal Quality (AT+CSQ): +CSQ: 18,0
3. Network Registration (AT+CREG?): +CREG: 0,1
```

---

## 6. Ordered 12-Milestone Deployment Plan

Follow this progression sequentially. Do not advance to sensor integration until the primary camera and speech milestones pass.

```
 [ Milestone 1: OS Boot & Network ]
                 |
 [ Milestone 2: SSH & System Packages ]
                 |
 [ Milestone 3: CSI Camera Verification ]
                 |
 [ Milestone 4: Audio / Earphones TTS ]
                 |
 [ Milestone 5: Neural Network Weights ]
                 |
 [ Milestone 6: Image Inference Test ]
                 |
 [ Milestone 7: Live Camera Inference ]
                 |
 [ Milestone 8: Camera + Earphone Voice Alerts ] <--- PRIMARY OBJECTIVE COMPLETE
                 |
 [ Milestone 9: HC-SR04 Distance Sensor ]
                 |
 [ Milestone 10: Emergency Push Button ]
                 |
 [ Milestone 11: SIM800L GSM Modem ]
                 |
 [ Milestone 12: Full System Integration ]
```

### Detailed Milestone Tasks

| # | Milestone | Command / Action | Pass Criteria |
|---|---|---|---|
| **M1** | **OS Boot & WiFi/Ethernet** | Flash 64-bit Pi OS with Raspberry Pi Imager. Connect via IP or `ssh viss@raspberrypi.local`. | Green LED flashes; board obtains local IP. |
| **M2** | **System Dependencies** | `sudo apt update && sudo apt install -y python3-opencv python3-picamera2 python3-gpiozero python3-lgpio python3-serial python3-numpy alsa-utils espeak-ng` | All packages installed with exit code 0. |
| **M3** | **CSI Camera Installation** | Safe cable insertion (power off). Run `rpicam-hello --list-cameras` and `python3 scripts/test_camera.py`. | Sensor identified; RGB frame captured and saved. |
| **M4** | **Earphones & Offline TTS** | Connect earphones. Run `python3 scripts/test_audio_voice.py`. | Audible WAV beep and clean spoken sentences heard. |
| **M5** | **Download Model Weights** | Run curl commands to download `.prototxt` and `.caffemodel` into `vision/weights/`. | Both files exist in `vision/weights/` ($23\text{ MB}$). |
| **M6** | **Inference Engine Validation** | Run `python3 -m unittest tests/test_vision_detector.py`. | OpenCVInferenceEngine tests pass. |
| **M7** | **Live Camera Inference** | Run `python3 scripts/test_live_inference.py --duration 10`. | Camera streams; MobileNet-SSD detects objects in frame. |
| **M8** | **Camera + Earphone Alerts (PRIMARY)** | Point camera at a person or car with earphones on. | **Spoken alert: `"Person detected"` plays through earphones.** |
| **M9** | **HC-SR04 Distance Sensor** | Wire $1\text{k}\Omega : 2\text{k}\Omega$ voltage divider. Run `python3 scripts/test_distance_sensor.py`. | Distance in centimeters updates smoothly. |
| **M10** | **Emergency Push Button** | Wire button between GPIO 17 and GND. Run `python3 scripts/test_button.py`. | Pressing button logs `BUTTON PRESSED`. |
| **M11** | **SIM800L GSM Modem** | Wire external power + UART. Run `python3 scripts/test_gsm_uart.py --port /dev/ttyS0`. | AT synchronization responds `OK`; network registered. |
| **M12** | **Full System Integration** | Run `python3 main.py --mode hardware`. | Vision, distance, voice, buzzer, and button run concurrently. |

---

## 7. Raspberry Pi OS Installation & Environment Setup

### 7.1 Flash the MicroSD Card
1. Download and open **Raspberry Pi Imager** on your MacBook Air M2.
2. Under **Device**, select **Raspberry Pi 4**.
3. Under **Operating System**, select:
   - `Raspberry Pi OS (other)` $\rightarrow$ `Raspberry Pi OS Lite (64-bit)` *(Debian 12 Bookworm)*
4. Click **Edit Settings**:
   - Set hostname: `viss.local`
   - Set username & password (e.g., `pi`)
   - Configure your home/hotspot Wi-Fi SSID and password
   - Enable **SSH** using password authentication
5. Click **Write** and verify.

### 7.2 Clone Repository & Configure Python Virtual Environment
On the Raspberry Pi terminal via SSH:

```bash
# 1. Update APT repositories:
sudo apt update && sudo apt upgrade -y

# 2. Install required system packages:
sudo apt install -y \
    git \
    python3-pip \
    python3-venv \
    python3-opencv \
    python3-picamera2 \
    python3-gpiozero \
    python3-lgpio \
    python3-serial \
    python3-numpy \
    alsa-utils \
    espeak-ng

# 3. Clone or copy viss_project into home directory:
cd ~
git clone <YOUR_REPO_URL> viss_project
cd viss_project

# 4. Create virtual environment with access to system packages:
# (Crucial: --system-site-packages allows Python to use APT's libcamera/picamera2)
python3 -m venv --system-site-packages venv
source venv/bin/activate

# 5. Install Python dependencies:
pip install -r requirements-pi.txt

# 6. Run readiness verification:
python3 scripts/verify_hardware_readiness.py
```

---

## 8. Application Startup & Operational Commands

### 8.1 Primary Objective Mode (Camera + Earphone Voice Alerts Only)
Run the application with real camera and voice alerts enabled:

```bash
# Run on Raspberry Pi with production hardware:
python3 main.py --mode hardware

# Run with verbose debug output for diagnostic tracing:
python3 main.py --mode hardware --log-level DEBUG

# Run for a timed trial (e.g. 30 seconds) and exit cleanly:
python3 main.py --mode hardware --duration 30
```

### 8.2 Configuration via Environment Variables
All hardware settings can be customized through environment variables without editing code:

```bash
# Set custom guardian emergency phone number:
export VISS_PHONE_NUMBER="+919876543210"

# Change UART port to PL011 UART (/dev/ttyAMA0):
export VISS_UART_PORT="/dev/ttyAMA0"

# Adjust voice announcement cooldown (e.g. 5 seconds):
export VISS_VOICE_COOLDOWN_S="5.0"

# Adjust speech speed (words per minute, default 160):
export VISS_VOICE_RATE="140"

# Run with custom configuration:
python3 main.py --mode hardware
```

### 8.3 Running in Simulation Mode on macOS (Development Host)
On your MacBook Air M2, hardware access is fully simulated with zero external dependencies:

```bash
# Run unit test suite (100 tests):
python3 -m unittest discover -s tests -p "test_*.py" -v

# Run 5-second simulated session:
python3 main.py --mode mock --duration 5
```

---

## 9. Troubleshooting Guide (Based on Project Code)

| Error Message in Logs | Root Cause | Solution |
|---|---|---|
| `RuntimeError: picamera2 is not installed` | Missing libcamera/Picamera2 bindings. | Install via APT: `sudo apt install python3-picamera2`. Virtual environment must use `--system-site-packages`. |
| `RuntimeError: Could not initialize Pi Camera via Picamera2` | Camera ribbon disconnected, inverted, or camera disabled. | Power off Pi. Re-seat ribbon with blue tape facing audio jack. Run `rpicam-hello --list-cameras`. |
| `FileNotFoundError: MobileNet-SSD prototxt file not found` | `vision/weights/MobileNetSSD_deploy.prototxt` missing. | Run the curl command in Section 4.4 to download the prototxt file. |
| `FileNotFoundError: MobileNet-SSD caffemodel weights file not found` | `vision/weights/MobileNetSSD_deploy.caffemodel` missing. | Run the curl command in Section 4.4 to download the caffemodel binary (~23 MB). |
| `[WARNING] pyttsx3 offline TTS engine is not available` | `espeak-ng` system synthesizer or `pyttsx3` missing. | Run `sudo apt install espeak-ng` and `pip install pyttsx3>=2.90`. |
| `RuntimeError: UART port '/dev/ttyS0' could not be opened: [Errno 13] Permission denied` | User lacks serial port permissions. | Add user to dialout group: `sudo usermod -aG dialout $USER`, then log out and log back in. |
| `[FAIL] SIM800L did not respond to 'AT'` | Power starvation, missing antenna, or inverted TX/RX lines. | Ensure SIM800L has dedicated 3.7V - 4.4V ($\ge 2\text{A}$) supply. Common GND must be connected to Pi. Verify Pi TX (Pin 8) connects to SIM RX. |
| `gpiozero.exc.BadPinFactory: Unable to load any default pin factory` | Missing `lgpio` backend on Bookworm. | Install `sudo apt install python3-lgpio python3-gpiozero`. |

---

## 10. Safety Blockers & Unresolved Hardware Questions

Before wiring the secondary components to your Raspberry Pi 4, review these safety checks:

```
[ SAFETY BLOCKER 1: HC-SR04 ECHO VOLTAGE PROTECTION ]
Status: MANDATORY BEFORE CONNECTING HC-SR04
Action: Do not connect ECHO directly to GPIO 23. You must install a 1k:2k voltage divider.

[ SAFETY BLOCKER 2: SIM800L POWER SUPPLY & BREAKOUT MODEL ]
Status: MANDATORY BEFORE CONNECTING SIM800L
Action: Do not power from Pi 5V or 3.3V rails. Provide a dedicated 3.7V-4.4V 2A supply with common ground.
Identify whether your SIM800L breakout has an onboard regulator before wiring.

[ SAFETY BLOCKER 3: BUZZER ELECTRICAL CHARACTERISTICS ]
Status: MANDATORY BEFORE CONNECTING BUZZER
Action: Verify whether your buzzer is Active or Passive using a 3V battery test.
Do not draw >16 mA directly from GPIO 18; use an NPN transistor driver.

[ UNRESOLVED: SECOND PUSH BUTTON ]
Status: INFORMATIONAL
Action: The current software only defines 1 emergency button on GPIO 17. Button #2 is spare.
```
