# Nexus Home Terminal - Raspberry Pi Setup

Turn a Raspberry Pi into a dedicated wall-mounted home terminal running the Nexus Jarvis dashboard.

## Hardware Requirements

- **Raspberry Pi 4 or 5** (2GB+ RAM recommended)
- **7-10" touchscreen display** (official Raspberry Pi Touch Display or similar)
- **microSD card** (16GB+ with Raspberry Pi OS Bookworm 64-bit)
- **Power supply** (USB-C, 5V 3A)
- **Case / wall mount** for the display

### Optional

- **ReSpeaker mic array** (2-mic or 4-mic HAT) for voice activation
- **Speaker** (3.5mm or USB) for audio feedback

## Quick Start

### 1. Flash Raspberry Pi OS

Use the [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to flash **Raspberry Pi OS (64-bit, Desktop)** to your microSD card. Enable SSH in the imager settings for headless setup.

### 2. Run the Setup Script

SSH into your Pi or open a terminal, then:

```bash
# Clone the Nexus repository (or copy this directory to the Pi)
git clone https://github.com/your-org/nexus.git
cd nexus/home/raspberry-pi

# Make the script executable
chmod +x setup.sh

# Run with your Nexus instance URL
sudo ./setup.sh --url https://your-nexus-instance.com/terminal
```

### 3. Reboot

```bash
sudo reboot
```

The Pi will boot directly into the Nexus Terminal dashboard in fullscreen kiosk mode.

## Setup Options

| Flag | Description | Default |
|------|-------------|---------|
| `--url <URL>` | Nexus terminal URL | `http://localhost:3000/terminal` |
| `--timezone <TZ>` | System timezone | `America/New_York` |
| `--wifi-ssid <SSID>` | WiFi network name | _(none)_ |
| `--wifi-pass <PASS>` | WiFi password | _(none)_ |
| `--respeaker` | Install ReSpeaker audio drivers | disabled |
| `--user <USERNAME>` | Linux user for the kiosk | `pi` |

You can also set these via environment variables:

```bash
sudo NEXUS_URL=https://nexus.local/terminal TIMEZONE=America/Chicago ./setup.sh
```

## What the Script Does

1. **Updates system packages** to latest versions
2. **Installs Chromium**, Openbox, and display dependencies
3. **Sets timezone** to your locale
4. **Configures WiFi** (if SSID provided) via NetworkManager or wpa_supplicant
5. **Disables screen blanking** and DPMS power management
6. **Creates a kiosk launcher script** at `~/.nexus/kiosk.sh`
7. **Creates a systemd service** (`nexus-terminal.service`) for auto-start
8. **Configures Openbox** and LightDM for auto-login
9. **Installs ReSpeaker drivers** (optional, for voice input)
10. **Sets up a health check watchdog** that restarts Chromium if it crashes

## Managing the Terminal

### Check Status

```bash
systemctl status nexus-terminal
```

### View Logs

```bash
journalctl -u nexus-terminal -f
```

### Restart the Terminal

```bash
sudo systemctl restart nexus-terminal
```

### Change the URL

Edit the kiosk script and restart:

```bash
nano ~/.nexus/kiosk.sh
# Change the URL at the bottom of the file
sudo systemctl restart nexus-terminal
```

### Temporarily Exit Kiosk Mode

Press `Alt+F4` to close Chromium, then use `Ctrl+Alt+T` to open a terminal (if Openbox keyboard shortcuts are configured). Alternatively, SSH in from another machine.

## Troubleshooting

### Black screen after boot

- SSH in and check: `systemctl status nexus-terminal`
- Verify X is running: `ps aux | grep Xorg`
- Check lightdm: `systemctl status lightdm`

### Chromium shows "cannot reach site"

- Verify the Nexus server is running and accessible from the Pi
- Test with: `curl -I <your-nexus-url>`
- Check WiFi: `nmcli device status`

### Touchscreen not responding

- Verify the display is detected: `ls /dev/input/`
- For official Pi touchscreen, it should work out of the box
- For USB touchscreens, you may need `xinput` calibration

### Screen goes blank after a while

- Re-run the screen blanking step or manually run:
  ```bash
  xset s off && xset s noblank && xset -dpms
  ```

## Network Requirements

The Pi needs network access to reach your Nexus instance. For local-only setups, run the Nexus backend on the same network and use a local IP or mDNS hostname (e.g., `http://nexus.local:3000/terminal`).

## Security Notes

- The kiosk runs in Chromium's incognito mode to avoid storing session data
- Consider setting up a firewall on the Pi if it is exposed to untrusted networks
- Use HTTPS for the Nexus URL in production environments
- The Pi auto-logs in without a password; physical security of the device matters
