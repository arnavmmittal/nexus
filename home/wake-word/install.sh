#!/usr/bin/env bash
# Nexus Wake Word Detection Service - Installer
# Run: chmod +x install.sh && ./install.sh
#
# Installs system dependencies, creates a Python virtualenv,
# installs Python packages, generates placeholder sounds,
# and optionally creates a systemd service for auto-start.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"
SERVICE_NAME="nexus-wake-word"
SERVICE_USER="${USER}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[-]${NC} $*"; }
step()  { echo -e "\n${CYAN}==> $*${NC}"; }

# -------------------------------------------------------------------
# Detect platform
# -------------------------------------------------------------------
detect_platform() {
    if [[ -f /proc/device-tree/model ]] && grep -qi "raspberry" /proc/device-tree/model 2>/dev/null; then
        PLATFORM="rpi"
    elif [[ "$(uname -s)" == "Linux" ]]; then
        PLATFORM="linux"
    elif [[ "$(uname -s)" == "Darwin" ]]; then
        PLATFORM="macos"
    else
        PLATFORM="unknown"
    fi
    info "Detected platform: ${PLATFORM}"
}

# -------------------------------------------------------------------
# Install system dependencies
# -------------------------------------------------------------------
install_system_deps() {
    step "Installing system dependencies"

    case "${PLATFORM}" in
        rpi|linux)
            sudo apt-get update -qq
            sudo apt-get install -y -qq \
                python3 python3-venv python3-pip \
                portaudio19-dev libsndfile1 \
                alsa-utils sox
            # Optional: GPIO support for Raspberry Pi
            if [[ "${PLATFORM}" == "rpi" ]]; then
                sudo apt-get install -y -qq python3-rpi.gpio
            fi
            ;;
        macos)
            if command -v brew &>/dev/null; then
                brew install portaudio libsndfile sox 2>/dev/null || true
            else
                warn "Homebrew not found. Install portaudio and libsndfile manually."
            fi
            ;;
        *)
            warn "Unknown platform. Install portaudio and libsndfile manually."
            ;;
    esac

    info "System dependencies installed"
}

# -------------------------------------------------------------------
# Create virtualenv and install Python packages
# -------------------------------------------------------------------
setup_python() {
    step "Setting up Python virtual environment"

    if [[ -d "${VENV_DIR}" ]]; then
        warn "Virtualenv already exists at ${VENV_DIR}"
    else
        python3 -m venv "${VENV_DIR}"
        info "Created virtualenv at ${VENV_DIR}"
    fi

    source "${VENV_DIR}/bin/activate"

    pip install --upgrade pip setuptools wheel -q
    pip install -r "${SCRIPT_DIR}/requirements.txt" -q

    # Install RPi.GPIO on Raspberry Pi
    if [[ "${PLATFORM}" == "rpi" ]]; then
        pip install RPi.GPIO -q 2>/dev/null || warn "Could not install RPi.GPIO"
    fi

    info "Python packages installed"
}

# -------------------------------------------------------------------
# Generate placeholder sound files using sox
# -------------------------------------------------------------------
generate_sounds() {
    step "Generating acknowledgment sounds"

    local sounds_dir="${SCRIPT_DIR}/sounds"
    mkdir -p "${sounds_dir}"

    if command -v sox &>/dev/null; then
        # Ack sound: short rising tone (wake word detected)
        if [[ ! -f "${sounds_dir}/ack.wav" ]]; then
            sox -n -r 16000 -c 1 "${sounds_dir}/ack.wav" \
                synth 0.15 sine 880 fade l 0 0.15 0.05 gain -6 2>/dev/null
            info "Generated ack.wav"
        fi

        # Done sound: two quick tones (success)
        if [[ ! -f "${sounds_dir}/done.wav" ]]; then
            sox -n -r 16000 -c 1 "${sounds_dir}/done.wav" \
                synth 0.1 sine 660 : synth 0.1 sine 880 fade l 0 0.2 0.05 gain -6 2>/dev/null
            info "Generated done.wav"
        fi

        # Error sound: low descending tone
        if [[ ! -f "${sounds_dir}/error.wav" ]]; then
            sox -n -r 16000 -c 1 "${sounds_dir}/error.wav" \
                synth 0.3 sine 330:220 fade l 0 0.3 0.1 gain -6 2>/dev/null
            info "Generated error.wav"
        fi
    else
        warn "sox not found - sound files not generated."
        warn "You can place your own ack.wav, done.wav, error.wav in ${sounds_dir}/"
    fi
}

# -------------------------------------------------------------------
# Create systemd service (Linux only)
# -------------------------------------------------------------------
create_systemd_service() {
    if [[ "${PLATFORM}" != "rpi" && "${PLATFORM}" != "linux" ]]; then
        info "Skipping systemd setup (not Linux)"
        return
    fi

    step "Creating systemd service"

    local service_file="/etc/systemd/system/${SERVICE_NAME}.service"

    sudo tee "${service_file}" > /dev/null <<UNIT
[Unit]
Description=Nexus Wake Word Detection Service
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${VENV_DIR}/bin/python ${SCRIPT_DIR}/wake_word_service.py --config ${SCRIPT_DIR}/config.yaml
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

# Environment variables (edit as needed)
# Environment=PICOVOICE_ACCESS_KEY=your_key_here
# Environment=NEXUS_API_KEY=your_key_here
EnvironmentFile=-${SCRIPT_DIR}/.env

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=${SCRIPT_DIR}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT

    sudo systemctl daemon-reload
    info "Systemd service created: ${SERVICE_NAME}"
    info "  Enable:  sudo systemctl enable ${SERVICE_NAME}"
    info "  Start:   sudo systemctl start ${SERVICE_NAME}"
    info "  Logs:    journalctl -u ${SERVICE_NAME} -f"
}

# -------------------------------------------------------------------
# Create .env template
# -------------------------------------------------------------------
create_env_template() {
    step "Creating .env template"

    local env_file="${SCRIPT_DIR}/.env"
    if [[ ! -f "${env_file}" ]]; then
        cat > "${env_file}" <<'ENVFILE'
# Nexus Wake Word Service - Environment Variables
# Fill in your keys below.

# Picovoice access key (free at https://console.picovoice.ai/)
PICOVOICE_ACCESS_KEY=

# Nexus API key (from your Nexus backend)
NEXUS_API_KEY=
ENVFILE
        info "Created ${env_file} - fill in your API keys"
    else
        warn ".env file already exists, not overwriting"
    fi
}

# -------------------------------------------------------------------
# Print summary
# -------------------------------------------------------------------
print_summary() {
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN} Nexus Wake Word Service - Installation Complete${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "  1. Get a free Picovoice access key:"
    echo "     https://console.picovoice.ai/"
    echo ""
    echo "  2. Set your API keys in one of:"
    echo "     - ${SCRIPT_DIR}/.env"
    echo "     - ${SCRIPT_DIR}/config.yaml"
    echo "     - Environment variables"
    echo ""
    echo "  3. Test the microphone:"
    echo "     source ${VENV_DIR}/bin/activate"
    echo "     python wake_word_service.py --list-devices"
    echo ""
    echo "  4. Run the service:"
    echo "     python wake_word_service.py -v"
    echo ""
    if [[ "${PLATFORM}" == "rpi" || "${PLATFORM}" == "linux" ]]; then
        echo "  5. Auto-start on boot:"
        echo "     sudo systemctl enable ${SERVICE_NAME}"
        echo "     sudo systemctl start ${SERVICE_NAME}"
        echo ""
    fi
    echo "  Say \"Jarvis\" to activate!"
    echo ""
}

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
main() {
    echo -e "${CYAN}"
    echo "  _   _                       __        __    _"
    echo " | \\ | | _____  ___   _ ___  \\ \\      / /_ _| | _____"
    echo " |  \\| |/ _ \\ \\/ / | | / __|  \\ \\ /\\ / / _\` | |/ / _ \\"
    echo " | |\\  |  __/>  <| |_| \\__ \\   \\ V  V / (_| |   <  __/"
    echo " |_| \\_|\\___/_/\\_\\\\__,_|___/    \\_/\\_/ \\__,_|_|\\_\\___|"
    echo -e "${NC}"
    echo " Wake Word Detection Service Installer"
    echo ""

    detect_platform
    install_system_deps
    setup_python
    generate_sounds
    create_env_template
    create_systemd_service
    print_summary
}

main "$@"
