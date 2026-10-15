# VISS — Pretrained Object Detection Model Selection & Evaluation

> **Authoritative Technical Evaluation**  
> **Target Deployments**: macOS Apple Silicon (M2 / M3) & Raspberry Pi 5 (ARM64 Cortex-A76 @ 2.4 GHz)  
> **Application**: Real-Time Assistive Wearable Object Detection with Low Latency and Offline Execution.

---

## 1. Evaluation & Research Summary

For an assistive navigation system running on edge/embedded CPU platforms (Raspberry Pi 5 and Apple Silicon Macs), the detection model must satisfy five non-negotiable criteria:
1. **Low Latency & High Frame Rate on CPU**: Real-time obstacle awareness requires $\ge 8\text{ to }15\text{ FPS}$ on a CPU without requiring external cloud GPUs or edge TPUs.
2. **Minimal Resource Footprint**: Small memory footprint ($< 100\text{ MB}$ RAM) and compact binary weight size ($< 30\text{ MB}$).
3. **Robust Target Class Taxonomy**: Capable of detecting the primary hazard categories: people, vehicles, and domestic animals (`person`, `car`, `dog`, `cat`).
4. **Offline, Deterministic Inference**: Pure local execution using standard, mature C++ / Python computer-vision runtimes (e.g., OpenCV DNN) with zero runtime network calls.
5. **Permissive, Transparent Licensing**: Verified model origins, reproducible weights, and clear licensing for open distribution.

---

## 2. Comparative Model Analysis

| Candidate Model | Framework / Runtime | Model Size | Parameter Count | Latency on Pi 5 / M2 | Taxonomy | License | Verdict |
|---|---|---|---|---|---|---|---|
| **MobileNet-SSD v1 (Pascal VOC)** *(Selected)* | OpenCV DNN (Caffe) | **23.3 MB** | ~3.3M | **~25 ms (M2)**<br>**~45 ms (Pi 5)** | 20 Classes (includes `person`, `car`, `dog`, `cat`) | Apache 2.0 / BSD | **SELECTED.** Native OpenCV integration, zero extra runtime dependencies, rock-solid CPU performance, exactly matches the foundational VISS architecture. |
| **YOLOv8n (Nano)** | PyTorch / Ultralytics ONNX | ~6.5 MB | ~3.2M | ~30 ms (M2)<br>~60 ms (Pi 5) | 80 Classes (COCO) | AGPL-3.0 (Restrictive) | Rejected due to AGPL-3.0 copyleft license restrictions and heavy PyTorch/Ultralytics dependency overhead. |
| **SSDLite MobileNetV2 (COCO)** | TensorFlow Lite / ONNX | ~18 MB | ~4.3M | ~35 ms (M2)<br>~70 ms (Pi 5) | 90 Classes (COCO) | Apache 2.0 | Viable alternative, but requires tflite-runtime or onnxruntime dependencies which have complex ARM64 wheel builds across Python 3.12/3.14. |
| **Tiny-YOLOv4** | OpenCV DNN (Darknet) | ~23 MB | ~6.0M | ~40 ms (M2)<br>~90 ms (Pi 5) | 80 Classes (COCO) | Public Domain | Slower inference throughput on quad-core ARM compared to depthwise-separable MobileNet. |

---

## 3. Selected Model Specification

### Model Identity
- **Architecture**: MobileNet-SSD (Single Shot MultiBox Detector with Depthwise Separable Convolutions)
- **Base Network**: MobileNet v1 (Howard et al., Google)
- **Detection Head**: SSD MultiBox 300 (Liu et al.)
- **Fine-Tuning Dataset**: PASCAL VOC 2007 + 2012 (20 object classes)
- **Implementation & Weights Origin**: Chuanqi305 MobileNet-SSD Caffe Port
- **Upstream Repository**: [`https://github.com/chuanqi305/MobileNet-SSD`](https://github.com/chuanqi305/MobileNet-SSD)

### Provenance, Source URLs & Checksums
| File | Size | Source URL | Verified SHA256 Checksum |
|---|---|---|---|
| **`MobileNetSSD_deploy.prototxt`** | 29,353 bytes | `https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt` | `2d180f723b3109e21f8287f6b3c691390d07b60eed998327cd3259ffa0e50608` |
| **`MobileNetSSD_deploy.caffemodel`** | 23,306,119 bytes | `https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/mobilenet_iter_73000.caffemodel` | `52eed8be80522c152a17fb56740de705b79881bde1a167e0e747310523685fc7` |

---

## 4. Input Preprocessing & Output Decoding

### Input Tensor Specifications
- **Input Dimensions**: $300 \times 300$ pixels
- **Aspect Ratio Handling**: OpenCV `cv2.resize()` scales captured frame ($640 \times 480$) to inference buffer ($320 \times 240$) then into the $300 \times 300$ DNN blob.
- **Color Format**: BGR format (the Caffe weights expect BGR channel order).
  - Since `BaseCamera` (and `OpenCVCamera` / `PiCamera2Driver`) outputs canonical **RGB**, the OpenCV DNN blob preprocessor is invoked with `swapRB=True` to convert RGB to BGR in-place.
- **Scale Factor**: $0.007843$ ($\approx \frac{1}{127.5}$)
- **Mean Subtraction**: $(127.5, 127.5, 127.5)$
- **Normalized Range**: $[-1.0, 1.0]$

```python
blob = cv2.dnn.blobFromImage(
    frame_resized,
    scalefactor=0.007843,
    size=(300, 300),
    mean=(127.5, 127.5, 127.5),
    swapRB=True,
    crop=False,
)
```

### Output Tensor Decoding
- **Output Shape**: `[1, 1, N, 7]` where $N$ is the number of candidate bounding boxes (up to 100).
- **Detection Row Format**:
  - `row[0]`: Batch index (always 0)
  - `row[1]`: Class ID (integer, $0 \dots 20$)
  - `row[2]`: Confidence score (float, $0.0 \dots 1.0$)
  - `row[3]`: Normalized $X_{\min}$ (clamped to $[0.0, 1.0]$)
  - `row[4]`: Normalized $Y_{\min}$ (clamped to $[0.0, 1.0]$)
  - `row[5]`: Normalized $X_{\max}$ (clamped to $[0.0, 1.0]$)
  - `row[6]`: Normalized $Y_{\max}$ (clamped to $[0.0, 1.0]$)

### Supported Pascal VOC Class Mapping
```text
 0: background       1: aeroplane        2: bicycle          3: bird
 4: boat             5: bottle           6: bus              7: car (Target)
 8: cat (Target)     9: chair           10: cow             11: diningtable
12: dog (Target)    13: horse           14: motorbike       15: person (Target)
16: pottedplant     17: sheep           18: sofa            19: train
20: tvmonitor
```
*VISS Target Classes*: `person` (15), `car` (7), `dog` (12), `cat` (8).

---

## 5. Licensing & Attribution

- **Caffe Framework**: BSD 2-Clause License (UC Berkeley).
- **MobileNet Architecture**: Apache License 2.0 (Google LLC).
- **MobileNet-SSD Port**: Apache License 2.0 (Chuanqi305).
- **OpenCV DNN Inference Engine**: Apache License 2.0 (OpenCV Foundation).
- **No Commercial Telemetry or Cloud Dependency**: All weights and graphs execute 100% locally on the host CPU.
