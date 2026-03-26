#!/usr/bin/env python3
"""
Nexus Home Terminal - RGB LED Ring Controller
==============================================

Controls a WS2812B (NeoPixel) LED ring connected to a Raspberry Pi 5 via
GPIO 18 (PWM). Provides animated lighting patterns tied to the terminal's
voice assistant state and exposes an HTTP API on localhost:8080 so the
browser-based terminal page can drive the LEDs in real time.

Hardware: WS2812B ring (default 24 LEDs) on GPIO 18 (PWM0)
Library:  rpi_ws281x (NeoPixel)

Systemd:  nexus-led.service (runs as root for GPIO access)
"""

import json
import math
import os
import signal
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# ---------------------------------------------------------------------------
# Configuration (from environment / config.env)
# ---------------------------------------------------------------------------

LED_COUNT = int(os.environ.get("LED_COUNT", "24"))
LED_PIN = int(os.environ.get("LED_PIN", "18"))  # GPIO 18 = PWM0
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = int(float(os.environ.get("LED_BRIGHTNESS", "0.5")) * 255)
LED_INVERT = False
LED_CHANNEL = 0

# ---------------------------------------------------------------------------
# Try to import the real library; fall back to a stub for dev/testing
# ---------------------------------------------------------------------------

try:
    from rpi_ws281x import PixelStrip, Color

    _REAL_HARDWARE = True
except ImportError:
    _REAL_HARDWARE = False

    class Color:  # type: ignore[no-redef]
        """Stub Color that packs RGB into a 24-bit int."""

        def __new__(cls, r: int, g: int, b: int) -> int:
            return (r << 16) | (g << 8) | b

    class PixelStrip:  # type: ignore[no-redef]
        """Stub PixelStrip for development without hardware."""

        def __init__(self, num, pin, freq_hz=800000, dma=10, invert=False,
                     brightness=255, channel=0):
            self._leds = [0] * num
            self._brightness = brightness
            self.num = num

        def begin(self):
            pass

        def show(self):
            pass

        def setPixelColor(self, n, color):
            if 0 <= n < self.num:
                self._leds[n] = color

        def setBrightness(self, b):
            self._brightness = b

        def numPixels(self):
            return self.num


# ---------------------------------------------------------------------------
# LED Controller Class
# ---------------------------------------------------------------------------

class LedController:
    """Manages the WS2812B LED ring with animated state patterns."""

    STATES = ("idle", "listening", "thinking", "speaking", "error", "alert", "off")

    def __init__(self):
        self._strip = PixelStrip(
            LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
            LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL,
        )
        self._strip.begin()

        self._state: str = "idle"
        self._solid_color: tuple[int, int, int] | None = None
        self._brightness: float = float(os.environ.get("LED_BRIGHTNESS", "0.5"))
        self._running = True
        self._lock = threading.Lock()

        # Animation thread
        self._thread = threading.Thread(target=self._animation_loop, daemon=True)
        self._thread.start()

    # -- Public API ----------------------------------------------------------

    def set_state(self, state: str) -> None:
        """Change the current animation pattern."""
        state = state.lower().strip()
        if state not in self.STATES:
            raise ValueError(f"Unknown state: {state}. Must be one of {self.STATES}")
        with self._lock:
            self._state = state
            self._solid_color = None  # Clear any solid override

    def set_color(self, r: int, g: int, b: int) -> None:
        """Set a static solid color on all LEDs."""
        with self._lock:
            self._solid_color = (
                max(0, min(255, r)),
                max(0, min(255, g)),
                max(0, min(255, b)),
            )

    def set_brightness(self, level: float) -> None:
        """Set brightness (0.0 to 1.0)."""
        level = max(0.0, min(1.0, level))
        with self._lock:
            self._brightness = level
            self._strip.setBrightness(int(level * 255))

    def shutdown(self) -> None:
        """Turn off all LEDs and stop the animation thread."""
        self._running = False
        self._clear()

    # -- Internal helpers ----------------------------------------------------

    def _clear(self) -> None:
        for i in range(self._strip.numPixels()):
            self._strip.setPixelColor(i, Color(0, 0, 0))
        self._strip.show()

    def _fill(self, r: int, g: int, b: int) -> None:
        color = Color(r, g, b)
        for i in range(self._strip.numPixels()):
            self._strip.setPixelColor(i, color)
        self._strip.show()

    def _set_pixel(self, i: int, r: int, g: int, b: int) -> None:
        self._strip.setPixelColor(i % self._strip.numPixels(), Color(r, g, b))

    # -- Animation loop ------------------------------------------------------

    def _animation_loop(self) -> None:
        """Main animation loop, runs in a dedicated thread at ~60 fps."""
        frame = 0
        while self._running:
            with self._lock:
                state = self._state
                solid = self._solid_color

            if solid is not None:
                self._fill(*solid)
            elif state == "idle":
                self._anim_idle_pulse(frame)
            elif state == "listening":
                self._anim_listening_spin(frame)
            elif state == "thinking":
                self._anim_thinking_chase(frame)
            elif state == "speaking":
                self._anim_speaking_wave(frame)
            elif state == "error":
                self._anim_error_flash(frame)
            elif state == "alert":
                self._anim_alert_flash(frame)
            elif state == "off":
                self._clear()

            frame += 1
            time.sleep(1 / 60)  # ~60 fps

    # -- Pattern: Idle (slow blue pulse) -------------------------------------

    def _anim_idle_pulse(self, frame: int) -> None:
        t = frame / 60.0
        # Gentle sine-wave brightness modulation
        intensity = 0.3 + 0.2 * math.sin(t * 1.2)
        r, g, b = 10, 40, 180  # Deep blue
        r = int(r * intensity)
        g = int(g * intensity)
        b = int(b * intensity)
        self._fill(r, g, b)

    # -- Pattern: Listening (green spin) -------------------------------------

    def _anim_listening_spin(self, frame: int) -> None:
        n = self._strip.numPixels()
        t = frame / 60.0
        head = int(t * 12) % n  # Spinning dot position

        for i in range(n):
            dist = (i - head) % n
            if dist > n // 2:
                dist = n - dist
            # Tail fade: bright at head, fading behind
            fade = max(0.0, 1.0 - dist / 6.0)
            r = int(16 * fade)
            g = int(220 * fade)
            b = int(80 * fade)
            self._set_pixel(i, r, g, b)
        self._strip.show()

    # -- Pattern: Thinking (amber chase) -------------------------------------

    def _anim_thinking_chase(self, frame: int) -> None:
        n = self._strip.numPixels()
        t = frame / 60.0

        for i in range(n):
            # Two chasing dots going opposite directions
            phase1 = (i / n + t * 0.8) % 1.0
            phase2 = (i / n - t * 0.6) % 1.0
            wave1 = max(0.0, math.cos(phase1 * math.pi * 4) * 0.5 + 0.5)
            wave2 = max(0.0, math.cos(phase2 * math.pi * 4) * 0.5 + 0.5)
            intensity = max(wave1, wave2)
            # Amber/gold color
            r = int(255 * intensity)
            g = int(160 * intensity)
            b = int(20 * intensity)
            self._set_pixel(i, r, g, b)
        self._strip.show()

    # -- Pattern: Speaking (cyan wave) ---------------------------------------

    def _anim_speaking_wave(self, frame: int) -> None:
        n = self._strip.numPixels()
        t = frame / 60.0

        for i in range(n):
            wave = math.sin((i / n) * math.pi * 4 + t * 5.0)
            intensity = 0.3 + 0.7 * max(0.0, wave)
            r = int(10 * intensity)
            g = int(210 * intensity)
            b = int(235 * intensity)
            self._set_pixel(i, r, g, b)
        self._strip.show()

    # -- Pattern: Error (red flash) ------------------------------------------

    def _anim_error_flash(self, frame: int) -> None:
        t = frame / 60.0
        on = int(t * 3) % 2 == 0  # Flash at ~1.5 Hz
        if on:
            self._fill(255, 20, 20)
        else:
            self._fill(40, 0, 0)

    # -- Pattern: Alert (white flash) ----------------------------------------

    def _anim_alert_flash(self, frame: int) -> None:
        t = frame / 60.0
        on = int(t * 4) % 2 == 0  # Flash at ~2 Hz
        if on:
            self._fill(255, 255, 255)
        else:
            self._fill(30, 30, 30)


# ---------------------------------------------------------------------------
# HTTP API Server
# ---------------------------------------------------------------------------

# Global controller reference (set in main)
_controller: LedController | None = None


class LedRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for LED control endpoints."""

    def log_message(self, format, *args):
        """Suppress default stderr logging; use stdout instead."""
        print(f"[LED-HTTP] {args[0]}" if args else "")

    def _send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if _controller is None:
            self._send_json(503, {"error": "Controller not initialized"})
            return

        try:
            data = self._read_json()
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "Invalid JSON"})
            return

        path = self.path.rstrip("/")

        if path == "/led/state":
            state = data.get("state", "")
            try:
                _controller.set_state(state)
                self._send_json(200, {"ok": True, "state": state})
            except ValueError as e:
                self._send_json(400, {"error": str(e)})

        elif path == "/led/color":
            r = data.get("r", 0)
            g = data.get("g", 0)
            b = data.get("b", 0)
            _controller.set_color(int(r), int(g), int(b))
            self._send_json(200, {"ok": True, "color": {"r": r, "g": g, "b": b}})

        elif path == "/led/brightness":
            level = data.get("level", 0.5)
            _controller.set_brightness(float(level))
            self._send_json(200, {"ok": True, "brightness": level})

        else:
            self._send_json(404, {"error": f"Unknown endpoint: {path}"})

    def do_GET(self):
        """Health check endpoint."""
        if self.path.rstrip("/") == "/health":
            self._send_json(200, {
                "ok": True,
                "state": _controller._state if _controller else "unknown",
                "hardware": _REAL_HARDWARE,
            })
        else:
            self._send_json(404, {"error": "Use POST for LED control"})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _handle_signal(signum, frame):
    """Graceful shutdown on SIGTERM/SIGINT."""
    print(f"\n[LED] Received signal {signum}, shutting down...")
    if _controller:
        _controller.shutdown()
    sys.exit(0)


def main() -> None:
    global _controller

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    hw_label = "REAL HARDWARE" if _REAL_HARDWARE else "STUB MODE (no rpi_ws281x)"
    print(f"[LED] Starting LED controller ({hw_label})")
    print(f"[LED] {LED_COUNT} LEDs on GPIO {LED_PIN}, brightness {LED_BRIGHTNESS}/255")

    _controller = LedController()

    # Start HTTP server
    server = HTTPServer(("127.0.0.1", 8080), LedRequestHandler)
    print("[LED] HTTP API listening on http://127.0.0.1:8080")
    print("[LED] Endpoints: POST /led/state, POST /led/color, POST /led/brightness")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _controller.shutdown()
        server.server_close()
        print("[LED] Shut down cleanly.")


if __name__ == "__main__":
    main()
