#!/usr/bin/env bash
# =============================================================================
# Nexus Home Terminal - Enhanced Raspberry Pi 5 Setup Script
# =============================================================================
#
# Configures a Raspberry Pi 5 as a dedicated wall-mounted home terminal with:
#   - 7-10" capacitive touchscreen display
#   - ReSpeaker 6-Mic Circular Array (via USB / I2C)
#   - WS2812B RGB LED ring (via SPI/PWM, controlled by led_controller.py)
#   - Camera module (for presence detection / future use)
#   - Chromium kiosk pointing to Nexus terminal dashboard
#   - Systemd services for kiosk, LED controller, and health monitor
#   - Network watchdog, crash recovery, auto-start on boot
#
# Tested on: Raspberry Pi OS (Bookworm, 64-bit) on Pi 5
#
# Usage:
#   chmod +x setup.sh
#   sudo ./setup.sh --url https://your-nexus-instance.com/terminal
#
# =============================================================================

set -euo pipefail

# ---------- Configuration Defaults ----------

NEXUS_URL="${NEXUS_URL:-http://localhost:3000/terminal}"
NEXUS_API_URL="${NEXUS_API_URL:-http://localhost:3001}"
TIMEZONE="${TIMEZONE:-America/New_York}"
WIFI_SSID="${WIFI_SSID:-}"
WIFI_PASSWORD="${WIFI_PASSWORD:-}"
KIOSK_USER="${KIOSK_USER:-pi}"
LOG_FILE="/var/log/nexus-terminal-setup.log"
HARDWARE_DIR="$(cd "$(dirname "$0")" && pwd)"

# Hardware flags (all enabled by default for the full terminal build)
INSTALL_RESPEAKER="${INSTALL_RESPEAKER:-true}"
INSTALL_LED_RING="${INSTALL_LED_RING:-true}"
INSTALL_CAMERA="${INSTALL_CAMERA:-true}"

# Display schedule (24h format)
DISPLAY_ON_HOUR="${DISPLAY_ON_HOUR:-6}"
DISPLAY_OFF_HOUR="${DISPLAY_OFF_HOUR:-23}"

# ---------- Colors ----------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ---------- Helpers ----------

log()   { echo -e "${GREEN}[NEXUS]${NC} $*" | tee -a "$LOG_FILE"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"  | tee -a "$LOG_FILE"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"    | tee -a "$LOG_FILE" >&2; }
info()  { echo -e "${CYAN}[INFO]${NC} $*"    | tee -a "$LOG_FILE"; }

die() {
  err "$@"
  exit 1
}

check_root() {
  if [[ $EUID -ne 0 ]]; then
    die "This script must be run as root. Try: sudo $0"
  fi
}

check_pi5() {
  if grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
    log "Detected Raspberry Pi 5."
  else
    warn "This script is optimized for Raspberry Pi 5. Proceeding anyway."
  fi
}

# ---------- Parse Arguments ----------

usage() {
  cat <<EOF
Usage: sudo $0 [OPTIONS]

Options:
  --url <URL>           Nexus terminal URL (default: $NEXUS_URL)
  --api-url <URL>       Nexus API base URL (default: $NEXUS_API_URL)
  --timezone <TZ>       Timezone (default: $TIMEZONE)
  --wifi-ssid <SSID>    WiFi network name (optional)
  --wifi-pass <PASS>    WiFi password (optional)
  --user <USERNAME>     Kiosk user (default: $KIOSK_USER)
  --no-respeaker        Skip ReSpeaker 6-mic array setup
  --no-led              Skip LED ring setup
  --no-camera           Skip camera setup
  --display-on <HOUR>   Hour to turn display on (default: $DISPLAY_ON_HOUR)
  --display-off <HOUR>  Hour to turn display off (default: $DISPLAY_OFF_HOUR)
  -h, --help            Show this help message

Environment Variables:
  NEXUS_URL, NEXUS_API_URL, TIMEZONE, WIFI_SSID, WIFI_PASSWORD,
  KIOSK_USER, INSTALL_RESPEAKER, INSTALL_LED_RING, INSTALL_CAMERA,
  DISPLAY_ON_HOUR, DISPLAY_OFF_HOUR

EOF
  exit 0
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --url)           NEXUS_URL="$2";          shift 2 ;;
      --api-url)       NEXUS_API_URL="$2";      shift 2 ;;
      --timezone)      TIMEZONE="$2";           shift 2 ;;
      --wifi-ssid)     WIFI_SSID="$2";          shift 2 ;;
      --wifi-pass)     WIFI_PASSWORD="$2";      shift 2 ;;
      --user)          KIOSK_USER="$2";         shift 2 ;;
      --no-respeaker)  INSTALL_RESPEAKER="false"; shift ;;
      --no-led)        INSTALL_LED_RING="false"; shift ;;
      --no-camera)     INSTALL_CAMERA="false";  shift ;;
      --display-on)    DISPLAY_ON_HOUR="$2";    shift 2 ;;
      --display-off)   DISPLAY_OFF_HOUR="$2";   shift 2 ;;
      -h|--help)       usage ;;
      *)               die "Unknown option: $1. Use --help for usage." ;;
    esac
  done
}

# ---------- Step: System Update ----------

step_system_update() {
  log "Updating system packages..."
  apt-get update -qq
  apt-get upgrade -y -qq
  log "System packages updated."
}

# ---------- Step: Core Dependencies ----------

step_install_dependencies() {
  log "Installing core packages..."
  apt-get install -y -qq \
    chromium-browser \
    unclutter \
    xdotool \
    xserver-xorg \
    x11-xserver-utils \
    lightdm \
    openbox \
    pulseaudio \
    alsa-utils \
    wget \
    curl \
    git \
    python3 \
    python3-pip \
    python3-venv \
    i2c-tools \
    libgpiod-dev \
    logrotate
  log "Core packages installed."
}

# ---------- Step: I2C and SPI Interfaces ----------

step_configure_interfaces() {
  log "Configuring I2C and SPI interfaces..."

  local BOOT_CONFIG=""
  if [[ -f /boot/firmware/config.txt ]]; then
    BOOT_CONFIG="/boot/firmware/config.txt"
  elif [[ -f /boot/config.txt ]]; then
    BOOT_CONFIG="/boot/config.txt"
  else
    warn "Could not find boot config.txt. Skipping interface configuration."
    return
  fi

  # Enable I2C
  if ! grep -q "^dtparam=i2c_arm=on" "$BOOT_CONFIG"; then
    echo "dtparam=i2c_arm=on" >> "$BOOT_CONFIG"
    log "I2C enabled."
  else
    info "I2C already enabled."
  fi

  # Enable SPI (needed for LED ring via SPI)
  if ! grep -q "^dtparam=spi=on" "$BOOT_CONFIG"; then
    echo "dtparam=spi=on" >> "$BOOT_CONFIG"
    log "SPI enabled."
  else
    info "SPI already enabled."
  fi

  # Enable I2S for audio (ReSpeaker)
  if ! grep -q "^dtparam=i2s=on" "$BOOT_CONFIG"; then
    echo "dtparam=i2s=on" >> "$BOOT_CONFIG"
    log "I2S enabled."
  else
    info "I2S already enabled."
  fi

  # Load i2c kernel modules
  if ! grep -q "^i2c-dev" /etc/modules 2>/dev/null; then
    echo "i2c-dev" >> /etc/modules
  fi
  if ! grep -q "^i2c-bcm2835" /etc/modules 2>/dev/null; then
    echo "i2c-bcm2835" >> /etc/modules
  fi

  # Add user to i2c and spi groups
  usermod -aG i2c "$KIOSK_USER" 2>/dev/null || true
  usermod -aG spi "$KIOSK_USER" 2>/dev/null || true
  usermod -aG gpio "$KIOSK_USER" 2>/dev/null || true

  log "I2C/SPI interfaces configured."
}

# ---------- Step: Timezone ----------

step_configure_timezone() {
  log "Setting timezone to ${TIMEZONE}..."
  timedatectl set-timezone "$TIMEZONE" || warn "Could not set timezone."
  log "Timezone set."
}

# ---------- Step: WiFi ----------

step_configure_wifi() {
  if [[ -z "$WIFI_SSID" ]]; then
    info "No WiFi SSID provided, skipping WiFi configuration."
    return
  fi

  log "Configuring WiFi for SSID: ${WIFI_SSID}..."

  if command -v nmcli &>/dev/null; then
    nmcli device wifi connect "$WIFI_SSID" password "$WIFI_PASSWORD" || {
      warn "nmcli WiFi connection failed. Configure manually."
      return
    }
  else
    local WPA_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
    cat >> "$WPA_CONF" <<WPAEOF

network={
    ssid="$WIFI_SSID"
    psk="$WIFI_PASSWORD"
    key_mgmt=WPA-PSK
}
WPAEOF
    wpa_cli -i wlan0 reconfigure || warn "wpa_cli reconfigure failed."
  fi

  log "WiFi configured."
}

# ---------- Step: ReSpeaker 6-Mic Array ----------

step_install_respeaker() {
  if [[ "$INSTALL_RESPEAKER" != "true" ]]; then
    info "Skipping ReSpeaker setup (use --no-respeaker to disable, enabled by default)."
    return
  fi

  log "Installing ReSpeaker 6-Mic Circular Array drivers..."

  # Install audio dependencies
  apt-get install -y -qq \
    portaudio19-dev \
    libatlas-base-dev \
    libasound2-dev

  # Clone and install ReSpeaker drivers
  local RESPEAKER_DIR="/tmp/seeed-voicecard"
  rm -rf "$RESPEAKER_DIR"

  git clone --depth 1 https://github.com/respeaker/seeed-voicecard.git "$RESPEAKER_DIR" || {
    warn "Failed to clone ReSpeaker repository."
    return
  }

  cd "$RESPEAKER_DIR"
  ./install.sh || {
    warn "ReSpeaker driver installation failed."
    cd /
    return
  }
  cd /

  # Create ALSA configuration for ReSpeaker 6-mic array
  log "Writing ALSA configuration for ReSpeaker..."
  cat > "/home/${KIOSK_USER}/.asoundrc" <<'ALSAEOF'
# ALSA configuration for ReSpeaker 6-Mic Circular Array
# Card 0 = ReSpeaker, Card 1 = HDMI/onboard (adjust if needed)

# Default to ReSpeaker for capture, HDMI for playback
pcm.!default {
    type asym
    playback.pcm "speaker"
    capture.pcm "mic_array"
}

ctl.!default {
    type hw
    card seeed8micvoicec
}

# ReSpeaker 6-mic capture (channel 0 for beamformed audio)
pcm.mic_array {
    type plug
    slave {
        pcm "hw:seeed8micvoicec,0"
        channels 8
    }
    # Downmix 8 channels to mono using channel 0 (beamformed)
    ttable.0.0 1.0
}

# Speaker output via HDMI or 3.5mm
pcm.speaker {
    type plug
    slave {
        pcm "hw:0,0"
    }
}

# Individual mic channels for advanced processing
pcm.mic_channel_0 {
    type plug
    slave {
        pcm "hw:seeed8micvoicec,0"
        channels 8
    }
    ttable.0.0 1.0
}
ALSAEOF

  chown "${KIOSK_USER}:${KIOSK_USER}" "/home/${KIOSK_USER}/.asoundrc"

  log "ReSpeaker 6-Mic Array configured."
}

# ---------- Step: Camera Module ----------

step_install_camera() {
  if [[ "$INSTALL_CAMERA" != "true" ]]; then
    info "Skipping camera setup."
    return
  fi

  log "Configuring camera module..."

  local BOOT_CONFIG=""
  if [[ -f /boot/firmware/config.txt ]]; then
    BOOT_CONFIG="/boot/firmware/config.txt"
  elif [[ -f /boot/config.txt ]]; then
    BOOT_CONFIG="/boot/config.txt"
  fi

  if [[ -n "$BOOT_CONFIG" ]]; then
    # Pi 5 uses libcamera by default, ensure camera is enabled
    if ! grep -q "^camera_auto_detect=1" "$BOOT_CONFIG"; then
      echo "camera_auto_detect=1" >> "$BOOT_CONFIG"
    fi
  fi

  # Install libcamera tools
  apt-get install -y -qq \
    libcamera-apps \
    python3-libcamera \
    python3-picamera2 \
    2>/dev/null || warn "Some camera packages not available. libcamera may already be installed."

  # Add user to video group
  usermod -aG video "$KIOSK_USER" 2>/dev/null || true

  log "Camera module configured."
}

# ---------- Step: LED Ring Dependencies ----------

step_install_led_deps() {
  if [[ "$INSTALL_LED_RING" != "true" ]]; then
    info "Skipping LED ring setup."
    return
  fi

  log "Installing LED ring (WS2812B) dependencies..."

  # Create a Python virtual environment for the LED controller
  local VENV_DIR="/home/${KIOSK_USER}/.nexus/venv"
  python3 -m venv "$VENV_DIR"

  # Install rpi_ws281x and HTTP server dependencies
  "$VENV_DIR/bin/pip" install --quiet \
    rpi_ws281x \
    adafruit-circuitpython-neopixel \
    psutil \
    requests

  chown -R "${KIOSK_USER}:${KIOSK_USER}" "$VENV_DIR"

  log "LED ring dependencies installed."
}

# ---------- Step: Screen Blanking ----------

step_disable_screen_blanking() {
  log "Disabling screen blanking and power management..."

  local XORG_CONF="/etc/X11/xorg.conf.d/10-blanking.conf"
  mkdir -p "$(dirname "$XORG_CONF")"
  cat > "$XORG_CONF" <<'XEOF'
Section "ServerFlags"
    Option "blank time" "0"
    Option "standby time" "0"
    Option "suspend time" "0"
    Option "off time" "0"
EndSection

Section "ServerLayout"
    Option "BlankTime" "0"
    Option "StandbyTime" "0"
    Option "SuspendTime" "0"
    Option "OffTime" "0"
EndSection
XEOF

  local LIGHTDM_CONF="/etc/lightdm/lightdm.conf.d/50-nexus.conf"
  mkdir -p "$(dirname "$LIGHTDM_CONF")"
  cat > "$LIGHTDM_CONF" <<'LEOF'
[Seat:*]
xserver-command=X -s 0 -dpms
LEOF

  # Console blanking off
  for cmdline in /boot/cmdline.txt /boot/firmware/cmdline.txt; do
    if [[ -f "$cmdline" ]] && ! grep -q "consoleblank=0" "$cmdline"; then
      sed -i 's/$/ consoleblank=0/' "$cmdline"
    fi
  done

  log "Screen blanking disabled."
}

# ---------- Step: Touchscreen Calibration ----------

step_configure_touchscreen() {
  log "Configuring touchscreen..."

  # Install touchscreen calibration tools
  apt-get install -y -qq \
    xinput-calibrator \
    libinput-tools \
    2>/dev/null || warn "Touchscreen tools may not all be available."

  # Create udev rule for touchscreen permissions
  cat > /etc/udev/rules.d/99-touchscreen.rules <<'TEOF'
# Allow kiosk user access to touchscreen input devices
SUBSYSTEM=="input", ATTRS{name}=="*touch*", MODE="0666"
SUBSYSTEM=="input", ATTRS{name}=="*Touch*", MODE="0666"
# Capacitive touchscreen on DSI
SUBSYSTEM=="input", ATTRS{name}=="*FT5406*", MODE="0666"
SUBSYSTEM=="input", ATTRS{name}=="*Goodix*", MODE="0666"
TEOF

  udevadm control --reload-rules 2>/dev/null || true

  log "Touchscreen configured."
}

# ---------- Step: Kiosk Script ----------

step_create_kiosk_script() {
  log "Creating kiosk launch script..."

  local KIOSK_DIR="/home/${KIOSK_USER}/.nexus"
  mkdir -p "$KIOSK_DIR"

  cat > "${KIOSK_DIR}/kiosk.sh" <<KEOF
#!/usr/bin/env bash
# Nexus Terminal Kiosk Launcher (Enhanced for Pi 5 hardware terminal)

# Wait for X to be ready
sleep 2

# Disable screen saver and DPMS
xset s off
xset s noblank
xset -dpms

# Hide mouse cursor after 3 seconds of inactivity
unclutter -idle 3 -root &

# Remove any Chromium crash flags
CHROME_DIR="/home/${KIOSK_USER}/.config/chromium"
mkdir -p "\$CHROME_DIR/Default"
sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' "\$CHROME_DIR/Default/Preferences" 2>/dev/null || true
sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' "\$CHROME_DIR/Default/Preferences" 2>/dev/null || true

# Launch Chromium in kiosk mode with hardware acceleration and mic/camera access
exec chromium-browser \\
  --noerrdialogs \\
  --disable-infobars \\
  --disable-session-crashed-bubble \\
  --disable-restore-session-state \\
  --kiosk \\
  --incognito \\
  --disable-translate \\
  --disable-features=TranslateUI \\
  --disable-pinch \\
  --overscroll-history-navigation=0 \\
  --check-for-update-interval=31536000 \\
  --autoplay-policy=no-user-gesture-required \\
  --disable-component-update \\
  --no-first-run \\
  --start-fullscreen \\
  --window-size=1920,1080 \\
  --window-position=0,0 \\
  --enable-gpu-rasterization \\
  --enable-zero-copy \\
  --ignore-gpu-blocklist \\
  --use-fake-ui-for-media-stream \\
  --enable-features=WebRTC \\
  --allow-running-insecure-content \\
  "${NEXUS_URL}"
KEOF

  chmod +x "${KIOSK_DIR}/kiosk.sh"
  chown -R "${KIOSK_USER}:${KIOSK_USER}" "$KIOSK_DIR"

  log "Kiosk script created at ${KIOSK_DIR}/kiosk.sh"
}

# ---------- Step: Deploy Python Scripts ----------

step_deploy_python_scripts() {
  log "Deploying LED controller and health monitor scripts..."

  local NEXUS_DIR="/home/${KIOSK_USER}/.nexus"
  mkdir -p "$NEXUS_DIR"

  # Copy led_controller.py and health_monitor.py from this directory
  if [[ -f "${HARDWARE_DIR}/led_controller.py" ]]; then
    cp "${HARDWARE_DIR}/led_controller.py" "${NEXUS_DIR}/led_controller.py"
    chmod +x "${NEXUS_DIR}/led_controller.py"
    log "LED controller deployed."
  else
    warn "led_controller.py not found in ${HARDWARE_DIR}. Skipping."
  fi

  if [[ -f "${HARDWARE_DIR}/health_monitor.py" ]]; then
    cp "${HARDWARE_DIR}/health_monitor.py" "${NEXUS_DIR}/health_monitor.py"
    chmod +x "${NEXUS_DIR}/health_monitor.py"
    log "Health monitor deployed."
  else
    warn "health_monitor.py not found in ${HARDWARE_DIR}. Skipping."
  fi

  # Write config file for the Python scripts
  cat > "${NEXUS_DIR}/config.env" <<CEOF
NEXUS_URL=${NEXUS_URL}
NEXUS_API_URL=${NEXUS_API_URL}
DISPLAY_ON_HOUR=${DISPLAY_ON_HOUR}
DISPLAY_OFF_HOUR=${DISPLAY_OFF_HOUR}
LED_COUNT=24
LED_PIN=18
LED_BRIGHTNESS=0.5
CEOF

  chown -R "${KIOSK_USER}:${KIOSK_USER}" "$NEXUS_DIR"

  log "Python scripts deployed."
}

# ---------- Step: Systemd Services ----------

step_create_systemd_services() {
  log "Creating systemd services..."

  local NEXUS_DIR="/home/${KIOSK_USER}/.nexus"
  local VENV_PYTHON="${NEXUS_DIR}/venv/bin/python3"

  # --- 1. Kiosk Browser Service ---
  cat > /etc/systemd/system/nexus-kiosk.service <<SEOF
[Unit]
Description=Nexus Home Terminal - Chromium Kiosk
Wants=graphical.target
After=graphical.target network-online.target
Requires=network-online.target

[Service]
Type=simple
User=${KIOSK_USER}
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/${KIOSK_USER}/.Xauthority
ExecStartPre=/bin/sleep 5
ExecStart=${NEXUS_DIR}/kiosk.sh
Restart=on-failure
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5

[Install]
WantedBy=graphical.target
SEOF

  # --- 2. LED Controller Service ---
  cat > /etc/systemd/system/nexus-led.service <<SEOF
[Unit]
Description=Nexus Home Terminal - LED Ring Controller
After=network.target

[Service]
Type=simple
User=root
EnvironmentFile=${NEXUS_DIR}/config.env
ExecStart=${VENV_PYTHON} ${NEXUS_DIR}/led_controller.py
Restart=on-failure
RestartSec=5
StartLimitIntervalSec=300
StartLimitBurst=10

[Install]
WantedBy=multi-user.target
SEOF

  # --- 3. Health Monitor Service ---
  cat > /etc/systemd/system/nexus-health.service <<SEOF
[Unit]
Description=Nexus Home Terminal - Health Monitor
After=network-online.target nexus-kiosk.service
Wants=network-online.target

[Service]
Type=simple
User=root
EnvironmentFile=${NEXUS_DIR}/config.env
ExecStart=${VENV_PYTHON} ${NEXUS_DIR}/health_monitor.py
Restart=on-failure
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
SEOF

  # --- 4. Network Watchdog Service ---
  cat > /etc/systemd/system/nexus-watchdog.service <<SEOF
[Unit]
Description=Nexus Home Terminal - Network Watchdog
After=network-online.target

[Service]
Type=simple
User=root
ExecStart=/bin/bash -c 'while true; do if ! ping -c 1 -W 5 8.8.8.8 >/dev/null 2>&1 && ! ping -c 1 -W 5 1.1.1.1 >/dev/null 2>&1; then echo "[nexus-watchdog] Network down, restarting networking..." | tee -a /var/log/nexus-watchdog.log; systemctl restart NetworkManager 2>/dev/null || systemctl restart networking 2>/dev/null; sleep 30; if ! ping -c 1 -W 5 8.8.8.8 >/dev/null 2>&1; then echo "[nexus-watchdog] Network still down after restart, rebooting..." | tee -a /var/log/nexus-watchdog.log; reboot; fi; fi; sleep 60; done'
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
SEOF

  # Enable all services
  systemctl daemon-reload
  systemctl enable nexus-kiosk.service
  systemctl enable nexus-led.service
  systemctl enable nexus-health.service
  systemctl enable nexus-watchdog.service

  log "All systemd services created and enabled."
}

# ---------- Step: Openbox Autostart ----------

step_configure_openbox_autostart() {
  log "Configuring Openbox autostart..."

  local OB_DIR="/home/${KIOSK_USER}/.config/openbox"
  mkdir -p "$OB_DIR"

  cat > "${OB_DIR}/autostart" <<OEOF
# Nexus Terminal Kiosk Autostart
/home/${KIOSK_USER}/.nexus/kiosk.sh &
OEOF

  chown -R "${KIOSK_USER}:${KIOSK_USER}" "$OB_DIR"
  log "Openbox autostart configured."
}

# ---------- Step: Autologin ----------

step_configure_autologin() {
  log "Configuring auto-login for ${KIOSK_USER}..."

  local LIGHTDM_AUTOLOGIN="/etc/lightdm/lightdm.conf.d/60-autologin.conf"
  mkdir -p "$(dirname "$LIGHTDM_AUTOLOGIN")"
  cat > "$LIGHTDM_AUTOLOGIN" <<AEOF
[Seat:*]
autologin-user=${KIOSK_USER}
autologin-session=openbox
user-session=openbox
AEOF

  log "Auto-login configured."
}

# ---------- Step: Log Rotation ----------

step_configure_logrotate() {
  log "Configuring log rotation..."

  cat > /etc/logrotate.d/nexus-terminal <<'LREOF'
/var/log/nexus-*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0644 root root
    sharedscripts
    postrotate
        systemctl reload rsyslog 2>/dev/null || true
    endscript
}
LREOF

  log "Log rotation configured."
}

# ---------- Summary ----------

print_summary() {
  echo ""
  echo -e "${GREEN}================================================================${NC}"
  echo -e "${GREEN}  Nexus Home Terminal (Pi 5 Enhanced) - Setup Complete           ${NC}"
  echo -e "${GREEN}================================================================${NC}"
  echo ""
  echo -e "  ${CYAN}Terminal URL:${NC}    ${NEXUS_URL}"
  echo -e "  ${CYAN}API URL:${NC}        ${NEXUS_API_URL}"
  echo -e "  ${CYAN}Kiosk User:${NC}     ${KIOSK_USER}"
  echo -e "  ${CYAN}Timezone:${NC}       ${TIMEZONE}"
  echo -e "  ${CYAN}WiFi:${NC}           ${WIFI_SSID:-Not configured}"
  echo -e "  ${CYAN}ReSpeaker:${NC}      ${INSTALL_RESPEAKER}"
  echo -e "  ${CYAN}LED Ring:${NC}       ${INSTALL_LED_RING}"
  echo -e "  ${CYAN}Camera:${NC}         ${INSTALL_CAMERA}"
  echo -e "  ${CYAN}Display Hours:${NC}  ${DISPLAY_ON_HOUR}:00 - ${DISPLAY_OFF_HOUR}:00"
  echo ""
  echo -e "  ${CYAN}Services:${NC}"
  echo -e "    - nexus-kiosk.service     (Chromium kiosk browser)"
  echo -e "    - nexus-led.service       (LED ring controller on :8080)"
  echo -e "    - nexus-health.service    (Health monitor + crash recovery)"
  echo -e "    - nexus-watchdog.service  (Network watchdog)"
  echo ""
  echo -e "  ${CYAN}Files:${NC}"
  echo -e "    - /home/${KIOSK_USER}/.nexus/kiosk.sh"
  echo -e "    - /home/${KIOSK_USER}/.nexus/led_controller.py"
  echo -e "    - /home/${KIOSK_USER}/.nexus/health_monitor.py"
  echo -e "    - /home/${KIOSK_USER}/.nexus/config.env"
  echo ""
  echo -e "  ${YELLOW}Next Steps:${NC}"
  echo -e "    1. Reboot: ${CYAN}sudo reboot${NC}"
  echo -e "    2. Terminal auto-launches in kiosk mode"
  echo -e "    3. Check status: ${CYAN}systemctl status nexus-kiosk nexus-led nexus-health${NC}"
  echo -e "    4. View logs: ${CYAN}journalctl -u nexus-kiosk -f${NC}"
  echo -e "    5. LED API: ${CYAN}curl -X POST http://localhost:8080/led/state -d '{\"state\":\"listening\"}'${NC}"
  echo ""
  echo -e "${GREEN}================================================================${NC}"
}

# ---------- Main ----------

main() {
  parse_args "$@"
  check_root
  check_pi5

  log "Starting Nexus Home Terminal (Enhanced) setup..."
  log "Target URL: ${NEXUS_URL}"
  log "Log file:   ${LOG_FILE}"

  step_system_update
  step_install_dependencies
  step_configure_interfaces
  step_configure_timezone
  step_configure_wifi
  step_configure_touchscreen
  step_disable_screen_blanking
  step_install_respeaker
  step_install_camera
  step_install_led_deps
  step_create_kiosk_script
  step_deploy_python_scripts
  step_create_systemd_services
  step_configure_openbox_autostart
  step_configure_autologin
  step_configure_logrotate

  print_summary
}

main "$@"
