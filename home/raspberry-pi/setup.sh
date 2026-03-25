#!/usr/bin/env bash
# =============================================================================
# Nexus Home Terminal - Raspberry Pi Setup Script
# =============================================================================
#
# Configures a Raspberry Pi as a dedicated wall-mounted home terminal running
# the Nexus Jarvis Terminal dashboard in Chromium kiosk mode.
#
# Tested on: Raspberry Pi OS (Bookworm, 64-bit)
# Hardware:  Raspberry Pi 4 / Pi 5 with 7-10" touchscreen display
#
# Usage:
#   chmod +x setup.sh
#   sudo ./setup.sh --url https://your-nexus-instance.com/terminal
#
# =============================================================================

set -euo pipefail

# ---------- Configuration Defaults ----------

NEXUS_URL="${NEXUS_URL:-http://localhost:3000/terminal}"
TIMEZONE="${TIMEZONE:-America/New_York}"
WIFI_SSID="${WIFI_SSID:-}"
WIFI_PASSWORD="${WIFI_PASSWORD:-}"
INSTALL_RESPEAKER="${INSTALL_RESPEAKER:-false}"
KIOSK_USER="${KIOSK_USER:-pi}"
LOG_FILE="/var/log/nexus-terminal-setup.log"

# ---------- Colors ----------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No color

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

# ---------- Parse Arguments ----------

usage() {
  cat <<EOF
Usage: sudo $0 [OPTIONS]

Options:
  --url <URL>           Nexus terminal URL (default: $NEXUS_URL)
  --timezone <TZ>       Timezone (default: $TIMEZONE)
  --wifi-ssid <SSID>    WiFi network name (optional)
  --wifi-pass <PASS>    WiFi password (optional)
  --respeaker           Install ReSpeaker audio drivers
  --user <USERNAME>     Kiosk user (default: $KIOSK_USER)
  -h, --help            Show this help message

Environment Variables:
  NEXUS_URL             Same as --url
  TIMEZONE              Same as --timezone
  WIFI_SSID             Same as --wifi-ssid
  WIFI_PASSWORD         Same as --wifi-pass
  INSTALL_RESPEAKER     Set to "true" to install ReSpeaker drivers
  KIOSK_USER            Same as --user

EOF
  exit 0
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --url)        NEXUS_URL="$2";       shift 2 ;;
      --timezone)   TIMEZONE="$2";        shift 2 ;;
      --wifi-ssid)  WIFI_SSID="$2";       shift 2 ;;
      --wifi-pass)  WIFI_PASSWORD="$2";   shift 2 ;;
      --respeaker)  INSTALL_RESPEAKER="true"; shift ;;
      --user)       KIOSK_USER="$2";      shift 2 ;;
      -h|--help)    usage ;;
      *)            die "Unknown option: $1. Use --help for usage." ;;
    esac
  done
}

# ---------- Steps ----------

step_system_update() {
  log "Updating system packages..."
  apt-get update -qq
  apt-get upgrade -y -qq
  log "System packages updated."
}

step_install_dependencies() {
  log "Installing required packages..."
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
    git
  log "Dependencies installed."
}

step_configure_timezone() {
  log "Setting timezone to ${TIMEZONE}..."
  timedatectl set-timezone "$TIMEZONE" || warn "Could not set timezone. Set it manually with: timedatectl set-timezone $TIMEZONE"
  log "Timezone set."
}

step_configure_wifi() {
  if [[ -z "$WIFI_SSID" ]]; then
    info "No WiFi SSID provided, skipping WiFi configuration."
    return
  fi

  log "Configuring WiFi for SSID: ${WIFI_SSID}..."

  # Use nmcli if available (Bookworm default), otherwise fall back to wpa_supplicant
  if command -v nmcli &>/dev/null; then
    nmcli device wifi connect "$WIFI_SSID" password "$WIFI_PASSWORD" || {
      warn "nmcli WiFi connection failed. You may need to configure manually."
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

step_disable_screen_blanking() {
  log "Disabling screen blanking and power management..."

  # X11 power management
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

  # DPMS off via lightdm
  local LIGHTDM_CONF="/etc/lightdm/lightdm.conf.d/50-nexus.conf"
  mkdir -p "$(dirname "$LIGHTDM_CONF")"
  cat > "$LIGHTDM_CONF" <<'LEOF'
[Seat:*]
xserver-command=X -s 0 -dpms
LEOF

  # Console blanking
  if ! grep -q "consoleblank=0" /boot/cmdline.txt 2>/dev/null; then
    sed -i 's/$/ consoleblank=0/' /boot/cmdline.txt 2>/dev/null || true
  fi
  if ! grep -q "consoleblank=0" /boot/firmware/cmdline.txt 2>/dev/null; then
    sed -i 's/$/ consoleblank=0/' /boot/firmware/cmdline.txt 2>/dev/null || true
  fi

  log "Screen blanking disabled."
}

step_create_kiosk_script() {
  log "Creating kiosk launch script..."

  local KIOSK_DIR="/home/${KIOSK_USER}/.nexus"
  mkdir -p "$KIOSK_DIR"

  cat > "${KIOSK_DIR}/kiosk.sh" <<KEOF
#!/usr/bin/env bash
# Nexus Terminal Kiosk Launcher
# Auto-generated by setup.sh

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

# Launch Chromium in kiosk mode
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
  "${NEXUS_URL}"
KEOF

  chmod +x "${KIOSK_DIR}/kiosk.sh"
  chown -R "${KIOSK_USER}:${KIOSK_USER}" "$KIOSK_DIR"

  log "Kiosk script created at ${KIOSK_DIR}/kiosk.sh"
}

step_create_systemd_service() {
  log "Creating systemd service for auto-start..."

  cat > /etc/systemd/system/nexus-terminal.service <<SEOF
[Unit]
Description=Nexus Home Terminal (Chromium Kiosk)
Wants=graphical.target
After=graphical.target

[Service]
Type=simple
User=${KIOSK_USER}
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/${KIOSK_USER}/.Xauthority
ExecStartPre=/bin/sleep 5
ExecStart=/home/${KIOSK_USER}/.nexus/kiosk.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=graphical.target
SEOF

  systemctl daemon-reload
  systemctl enable nexus-terminal.service

  log "Systemd service created and enabled."
}

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

step_install_respeaker() {
  if [[ "$INSTALL_RESPEAKER" != "true" ]]; then
    info "Skipping ReSpeaker driver installation (use --respeaker to enable)."
    return
  fi

  log "Installing ReSpeaker audio drivers..."

  local RESPEAKER_DIR="/tmp/seeed-voicecard"

  if [[ -d "$RESPEAKER_DIR" ]]; then
    rm -rf "$RESPEAKER_DIR"
  fi

  git clone --depth 1 https://github.com/respeaker/seeed-voicecard.git "$RESPEAKER_DIR" || {
    warn "Failed to clone ReSpeaker repository. Audio drivers not installed."
    return
  }

  cd "$RESPEAKER_DIR"
  ./install.sh || {
    warn "ReSpeaker driver installation failed. You may need to install manually."
    return
  }
  cd /

  log "ReSpeaker drivers installed. A reboot is required to activate."
}

step_create_health_check() {
  log "Creating health check / watchdog script..."

  local HC_SCRIPT="/home/${KIOSK_USER}/.nexus/health-check.sh"
  cat > "$HC_SCRIPT" <<'HEOF'
#!/usr/bin/env bash
# Nexus Terminal Health Check
# Restarts Chromium if it crashes or becomes unresponsive

if ! pgrep -x "chromium-browser" > /dev/null 2>&1; then
  echo "[$(date)] Chromium not running, restarting service..."
  systemctl restart nexus-terminal.service
fi
HEOF

  chmod +x "$HC_SCRIPT"
  chown "${KIOSK_USER}:${KIOSK_USER}" "$HC_SCRIPT"

  # Run health check every 2 minutes via cron
  local CRON_ENTRY="*/2 * * * * ${HC_SCRIPT} >> /var/log/nexus-health.log 2>&1"
  (crontab -u root -l 2>/dev/null | grep -v "nexus.*health-check"; echo "$CRON_ENTRY") | crontab -u root -

  log "Health check watchdog installed (cron, every 2 min)."
}

# ---------- Summary ----------

print_summary() {
  echo ""
  echo -e "${GREEN}============================================================${NC}"
  echo -e "${GREEN}  Nexus Home Terminal - Setup Complete                       ${NC}"
  echo -e "${GREEN}============================================================${NC}"
  echo ""
  echo -e "  ${CYAN}Terminal URL:${NC}    ${NEXUS_URL}"
  echo -e "  ${CYAN}Kiosk User:${NC}     ${KIOSK_USER}"
  echo -e "  ${CYAN}Timezone:${NC}       ${TIMEZONE}"
  echo -e "  ${CYAN}WiFi:${NC}           ${WIFI_SSID:-Not configured}"
  echo -e "  ${CYAN}ReSpeaker:${NC}      ${INSTALL_RESPEAKER}"
  echo -e "  ${CYAN}Service:${NC}        nexus-terminal.service"
  echo -e "  ${CYAN}Kiosk Script:${NC}   /home/${KIOSK_USER}/.nexus/kiosk.sh"
  echo -e "  ${CYAN}Log File:${NC}       ${LOG_FILE}"
  echo ""
  echo -e "  ${YELLOW}Next Steps:${NC}"
  echo -e "    1. Reboot the Pi:  ${CYAN}sudo reboot${NC}"
  echo -e "    2. The terminal should auto-launch in Chromium kiosk mode."
  echo -e "    3. To change the URL later, edit /home/${KIOSK_USER}/.nexus/kiosk.sh"
  echo -e "    4. To check status:  ${CYAN}systemctl status nexus-terminal${NC}"
  echo -e "    5. To view logs:     ${CYAN}journalctl -u nexus-terminal -f${NC}"
  echo ""
  echo -e "${GREEN}============================================================${NC}"
}

# ---------- Main ----------

main() {
  parse_args "$@"
  check_root

  log "Starting Nexus Home Terminal setup..."
  log "Target URL: ${NEXUS_URL}"
  log "Log file:   ${LOG_FILE}"

  step_system_update
  step_install_dependencies
  step_configure_timezone
  step_configure_wifi
  step_disable_screen_blanking
  step_create_kiosk_script
  step_create_systemd_service
  step_configure_openbox_autostart
  step_configure_autologin
  step_install_respeaker
  step_create_health_check

  print_summary
}

main "$@"
