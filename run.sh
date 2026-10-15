#!/usr/bin/env bash
# ==============================================================================
# VISS (Visual Impairment Support System) - Laptop Test & Simulation Runner
# ==============================================================================
# Supports both:
#   1. Mock simulation mode (runs offline with zero hardware)
#   2. Real macOS mode (uses real Mac webcam, MobileNet-SSD Caffe DNN, and native speech)
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# Determine Python command
PYTHON_CMD="python3"
if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
    PYTHON_CMD="python"
fi

show_banner() {
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BOLD}${CYAN}  Visual Impairment Support System (VISS) — macOS Test Runner${NC}"
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "Platform: $(uname -s) ($(uname -m))"
    echo -e "Python:   $($PYTHON_CMD --version 2>&1)"
    echo -e "${BLUE}----------------------------------------------------------------------${NC}"
}

run_tests() {
    echo -e "\n${BOLD}${YELLOW}Running Full Automated Unit & Integration Test Suite...${NC}"
    $PYTHON_CMD -m unittest discover -s tests -p "test_*.py" -v
    echo -e "${GREEN}[PASS] All test suite assertions passed successfully.${NC}\n"
}

run_readiness() {
    echo -e "${BOLD}${YELLOW}Checking System & Diagnostics Readiness...${NC}"
    $PYTHON_CMD scripts/verify_hardware_readiness.py
    echo ""
}

run_smoke() {
    echo -e "\n${BOLD}${YELLOW}Running Test B: MobileNet-SSD Model Loading Smoke Test...${NC}\n"
    $PYTHON_CMD scripts/test_model_smoke.py
}

run_image() {
    local img="${1:-vision/test_assets/sample_cat.jpg}"
    local targets="${2:-all}"
    echo -e "\n${BOLD}${YELLOW}Running Test C: Still Image Inference with MobileNet-SSD...${NC}"
    echo -e "Testing on image: ${CYAN}${img}${NC} (Targets: ${targets})\n"
    $PYTHON_CMD scripts/test_image_inference.py --image "$img" --confidence 0.40 --speak --target-classes "$targets"
}

run_camera() {
    local dev="${1:-0}"
    echo -e "\n${BOLD}${YELLOW}Running Test D: Mac Webcam (OpenCVCamera) Verification...${NC}\n"
    $PYTHON_CMD scripts/test_mac_webcam.py --device-index "$dev"
}

run_audio() {
    echo -e "\n${BOLD}${YELLOW}Running Test E: Audio Alerts & Spoken Speech Synthesis...${NC}\n"
    $PYTHON_CMD scripts/test_audio_voice.py
}

run_pipeline() {
    local dur="${1:-15}"
    local targets="${2:-all}"
    echo -e "\n${BOLD}${YELLOW}Running Test F: Real Webcam -> Inference -> Spoken Speech Pipeline...${NC}"
    echo -e "Duration: ${dur}s (Targets: ${targets}, Press Ctrl+C to stop early)\n"
    $PYTHON_CMD scripts/test_real_pipeline_mac.py --duration "$dur" --confidence 0.45 --target-classes "$targets"
}

run_mac_app() {
    local dur="${1:-20}"
    local targets="${2:-all}"
    echo -e "\n${BOLD}${YELLOW}Launching VISS Application in macOS Real Mode (${dur}s)...${NC}"
    echo -e "Real webcam + Real MobileNet-SSD + Real Spoken Alerts + Mock GPIO (Targets: ${targets})\n"
    $PYTHON_CMD main.py --mode mac --duration "$dur" --target-classes "$targets"
}

run_demo() {
    local duration="${1:-5}"
    echo -e "\n${BOLD}${YELLOW}Running VISS Application Simulation (${duration}s Demo)...${NC}"
    $PYTHON_CMD main.py --mode mock --duration "$duration"
    echo -e "\n${GREEN}[SUCCESS] VISS simulation completed cleanly.${NC}"
}

run_live() {
    echo -e "\n${BOLD}${YELLOW}Launching VISS Continuous Simulation...${NC}"
    echo -e "Press ${BOLD}Ctrl+C${NC} anytime to stop.\n"
    $PYTHON_CMD main.py --mode mock
}

show_help() {
    echo -e "${BOLD}Usage:${NC} ./run.sh [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  (no args)       Run automated tests, readiness check, and 5-second simulated demo."
    echo "  test            Run full automated unit & integration test suite."
    echo "  smoke           Test B: MobileNet-SSD model loading smoke test."
    echo "  image [path]    Test C: Real object detection on a static image (with spoken alerts)."
    echo "  camera [index]  Test D: Mac webcam capture and resolution check."
    echo "  audio           Test E: Earphone audio tones and offline spoken speech synthesis."
    echo "  pipeline [sec]  Test F: Integrated Real Webcam -> Neural Network -> Speech pipeline."
    echo "  mac [sec]       Run main.py in real macOS mode (real camera + model + voice alerts)."
    echo "  demo [sec]      Run simulated application for N seconds in mock mode (default: 5)."
    echo "  live            Run continuous simulation in mock mode until Ctrl+C."
    echo "  check           Run hardware & dependency readiness diagnostics."
    echo "  help            Display this help message."
    echo ""
    echo "Examples:"
    echo "  ./run.sh smoke                 # Quick check if neural network weights load"
    echo "  ./run.sh image                 # Detect objects on sample image and speak"
    echo "  ./run.sh image vision/test_assets/sample_person.png"
    echo "  ./run.sh camera                # Test Mac FaceTime webcam capture"
    echo "  ./run.sh pipeline 15           # 15s live webcam detection with voice alerts"
    echo "  ./run.sh mac 30                # Run VISS main app in macOS real mode"
}

show_banner

case "${1:-default}" in
    default)
        run_tests
        run_readiness
        run_demo 5
        echo -e "\n${BOLD}${GREEN}======================================================================${NC}"
        echo -e "${BOLD}${GREEN}  All Laptop Tests Passed! Project is ready for development & deployment.${NC}"
        echo -e "${BOLD}${GREEN}======================================================================${NC}"
        echo -e "To test model on an image:      ${CYAN}./run.sh image${NC}"
        echo -e "To test webcam detection:       ${CYAN}./run.sh pipeline 15${NC}"
        echo -e "To test audio & speech:         ${CYAN}./run.sh audio${NC}"
        echo -e "To run main app in macOS mode:  ${CYAN}./run.sh mac 20${NC}\n"
        ;;
    test)
        run_tests
        ;;
    smoke)
        run_smoke
        ;;
    image)
        run_image "${2:-vision/test_assets/sample_cat.jpg}"
        ;;
    camera)
        run_camera "${2:-0}"
        ;;
    audio)
        run_audio
        ;;
    pipeline)
        run_pipeline "${2:-15}"
        ;;
    mac)
        run_mac_app "${2:-20}"
        ;;
    demo)
        run_demo "${2:-5}"
        ;;
    live)
        run_live
        ;;
    check)
        run_readiness
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}\n"
        show_help
        exit 1
        ;;
esac
