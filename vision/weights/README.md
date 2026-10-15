# MobileNet-SSD Caffe Model Files

This directory is the designated location for the MobileNet-SSD model files used by the Visual Impairment Support System (VISS).

## Required Files

1. **`MobileNetSSD_deploy.prototxt`**
   - The network architecture definition for MobileNet-SSD.
   - Text file (~29 KB).
2. **`MobileNetSSD_deploy.caffemodel`**
   - Pre-trained weights trained on the 20-class Pascal VOC dataset.
   - Binary file (~23 MB).

## How to Obtain These Files

Per project instructions, binary weights are **not** bundled or silently downloaded automatically. When deploying on a physical Raspberry Pi 4 or using a local webcam on macOS, download them from the official OpenCV / Caffe sources:

```bash
# From the project root:

# 1. Download the prototxt definition (matching caffemodel layers)
curl -L -o vision/weights/MobileNetSSD_deploy.prototxt \
  https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt

# 2. Download the pre-trained weights
curl -L -o vision/weights/MobileNetSSD_deploy.caffemodel \
  https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/mobilenet_iter_73000.caffemodel
```

### Verified SHA256 Checksums
- `MobileNetSSD_deploy.prototxt`: `2d180f723b3109e21f8287f6b3c691390d07b60eed998327cd3259ffa0e50608`
- `MobileNetSSD_deploy.caffemodel`: `52eed8be80522c152a17fb56740de705b79881bde1a167e0e747310523685fc7`

## Preprocessing Settings
- Input image size: `300 x 300` (resized from `320 x 240`)
- Scale factor: `0.007843` ($1 / 127.5$)
- Mean subtraction: `(127.5, 127.5, 127.5)`
- Color channel conversion: `swapRB=True` (since `BaseCamera` supplies standard RGB numpy arrays, `swapRB=True` converts RGB to the BGR format expected by Caffe)
- Target classes: `person` (ID 15), `car` (ID 7), `dog` (ID 12), `cat` (ID 8)
