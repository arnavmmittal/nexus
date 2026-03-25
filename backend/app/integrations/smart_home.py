"""Smart Home Integration Tools - Apple HomeKit Control.

Allows Jarvis/Ultron to:
- List all smart home devices
- Control lights, switches, thermostats
- Query device states
- Activate scenes
- Set thermostat temperatures
- Control room-specific lighting

This module provides a clean abstraction layer that works with mock data
initially but can be easily connected to real HomeKit devices via HAP-python
or the homekit library when available.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


# ============================================================================
# Device Types and States
# ============================================================================

class DeviceType(str, Enum):
    """Types of smart home devices."""
    LIGHT = "light"
    SWITCH = "switch"
    THERMOSTAT = "thermostat"
    LOCK = "lock"
    SENSOR = "sensor"
    FAN = "fan"
    OUTLET = "outlet"
    GARAGE_DOOR = "garage_door"
    BLIND = "blind"


class DeviceAction(str, Enum):
    """Actions that can be performed on devices."""
    ON = "on"
    OFF = "off"
    TOGGLE = "toggle"
    SET = "set"
    LOCK = "lock"
    UNLOCK = "unlock"
    OPEN = "open"
    CLOSE = "close"


@dataclass
class DeviceState:
    """Represents the current state of a device."""
    device_id: str
    name: str
    device_type: DeviceType
    room: str
    is_online: bool
    is_on: Optional[bool] = None
    brightness: Optional[int] = None  # 0-100 for lights
    color_temp: Optional[int] = None  # Kelvin for lights
    hue: Optional[int] = None  # 0-360 for color lights
    saturation: Optional[int] = None  # 0-100 for color lights
    temperature: Optional[float] = None  # Current temp for thermostats
    target_temperature: Optional[float] = None  # Target temp for thermostats
    mode: Optional[str] = None  # heat/cool/auto/off for thermostats
    humidity: Optional[int] = None  # Current humidity percentage
    is_locked: Optional[bool] = None  # For locks
    position: Optional[int] = None  # 0-100 for blinds/garage doors
    battery_level: Optional[int] = None  # For battery-powered devices
    last_updated: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, filtering out None values."""
        result = {}
        for key, value in asdict(self).items():
            if value is not None:
                if isinstance(value, Enum):
                    result[key] = value.value
                else:
                    result[key] = value
        return result


@dataclass
class Scene:
    """Represents a smart home scene."""
    scene_id: str
    name: str
    description: str
    devices: List[Dict[str, Any]]  # List of device states in this scene
    is_active: bool = False


# ============================================================================
# Mock Smart Home Data Store
# ============================================================================

class SmartHomeStore:
    """
    In-memory store for smart home device states.

    This simulates a real smart home system. When HomeKit libraries are
    available, this can be replaced with actual device communication.
    """

    def __init__(self):
        self._devices: Dict[str, DeviceState] = {}
        self._scenes: Dict[str, Scene] = {}
        self._initialize_mock_devices()
        self._initialize_mock_scenes()

    def _initialize_mock_devices(self):
        """Set up realistic mock devices for testing."""
        mock_devices = [
            # Living Room
            DeviceState(
                device_id="light_living_main",
                name="Living Room Main Light",
                device_type=DeviceType.LIGHT,
                room="Living Room",
                is_online=True,
                is_on=True,
                brightness=80,
                color_temp=4000,
                last_updated=datetime.now().isoformat(),
            ),
            DeviceState(
                device_id="light_living_accent",
                name="Living Room Accent Lights",
                device_type=DeviceType.LIGHT,
                room="Living Room",
                is_online=True,
                is_on=False,
                brightness=0,
                hue=240,
                saturation=50,
                last_updated=datetime.now().isoformat(),
            ),
            DeviceState(
                device_id="switch_living_tv",
                name="TV Power",
                device_type=DeviceType.SWITCH,
                room="Living Room",
                is_online=True,
                is_on=True,
                last_updated=datetime.now().isoformat(),
            ),
            DeviceState(
                device_id="fan_living",
                name="Living Room Fan",
                device_type=DeviceType.FAN,
                room="Living Room",
                is_online=True,
                is_on=False,
                brightness=0,  # Fan speed as percentage
                last_updated=datetime.now().isoformat(),
            ),

            # Bedroom
            DeviceState(
                device_id="light_bedroom_main",
                name="Bedroom Main Light",
                device_type=DeviceType.LIGHT,
                room="Bedroom",
                is_online=True,
                is_on=False,
                brightness=0,
                color_temp=2700,
                last_updated=datetime.now().isoformat(),
            ),
            DeviceState(
                device_id="light_bedroom_lamp",
                name="Bedside Lamp",
                device_type=DeviceType.LIGHT,
                room="Bedroom",
                is_online=True,
                is_on=True,
                brightness=30,
                color_temp=2200,
                last_updated=datetime.now().isoformat(),
            ),
            DeviceState(
                device_id="blind_bedroom",
                name="Bedroom Blinds",
                device_type=DeviceType.BLIND,
                room="Bedroom",
                is_online=True,
                position=100,  # Fully open
                last_updated=datetime.now().isoformat(),
            ),

            # Kitchen
            DeviceState(
                device_id="light_kitchen_main",
                name="Kitchen Light",
                device_type=DeviceType.LIGHT,
                room="Kitchen",
                is_online=True,
                is_on=True,
                brightness=100,
                color_temp=5000,
                last_updated=datetime.now().isoformat(),
            ),
            DeviceState(
                device_id="outlet_kitchen_coffee",
                name="Coffee Maker",
                device_type=DeviceType.OUTLET,
                room="Kitchen",
                is_online=True,
                is_on=False,
                last_updated=datetime.now().isoformat(),
            ),

            # Office
            DeviceState(
                device_id="light_office_main",
                name="Office Light",
                device_type=DeviceType.LIGHT,
                room="Office",
                is_online=True,
                is_on=True,
                brightness=90,
                color_temp=5500,
                last_updated=datetime.now().isoformat(),
            ),
            DeviceState(
                device_id="light_office_desk",
                name="Desk Lamp",
                device_type=DeviceType.LIGHT,
                room="Office",
                is_online=True,
                is_on=True,
                brightness=70,
                color_temp=4500,
                last_updated=datetime.now().isoformat(),
            ),

            # Whole House
            DeviceState(
                device_id="thermostat_main",
                name="Main Thermostat",
                device_type=DeviceType.THERMOSTAT,
                room="Hallway",
                is_online=True,
                is_on=True,
                temperature=72.0,
                target_temperature=70.0,
                mode="cool",
                humidity=45,
                last_updated=datetime.now().isoformat(),
            ),
            DeviceState(
                device_id="lock_front",
                name="Front Door Lock",
                device_type=DeviceType.LOCK,
                room="Entryway",
                is_online=True,
                is_locked=True,
                battery_level=85,
                last_updated=datetime.now().isoformat(),
            ),
            DeviceState(
                device_id="lock_back",
                name="Back Door Lock",
                device_type=DeviceType.LOCK,
                room="Kitchen",
                is_online=True,
                is_locked=True,
                battery_level=72,
                last_updated=datetime.now().isoformat(),
            ),
            DeviceState(
                device_id="garage_main",
                name="Garage Door",
                device_type=DeviceType.GARAGE_DOOR,
                room="Garage",
                is_online=True,
                position=0,  # Closed
                last_updated=datetime.now().isoformat(),
            ),

            # Sensors
            DeviceState(
                device_id="sensor_living_motion",
                name="Living Room Motion",
                device_type=DeviceType.SENSOR,
                room="Living Room",
                is_online=True,
                is_on=False,  # No motion detected
                battery_level=95,
                last_updated=datetime.now().isoformat(),
            ),
            DeviceState(
                device_id="sensor_front_contact",
                name="Front Door Sensor",
                device_type=DeviceType.SENSOR,
                room="Entryway",
                is_online=True,
                is_on=False,  # Door closed
                battery_level=88,
                last_updated=datetime.now().isoformat(),
            ),
        ]

        for device in mock_devices:
            self._devices[device.device_id] = device

    def _initialize_mock_scenes(self):
        """Set up realistic mock scenes."""
        mock_scenes = [
            Scene(
                scene_id="scene_good_morning",
                name="Good Morning",
                description="Gradually brighten lights, open blinds, start coffee",
                devices=[
                    {"device_id": "light_bedroom_main", "brightness": 50, "color_temp": 4000},
                    {"device_id": "blind_bedroom", "position": 100},
                    {"device_id": "light_kitchen_main", "is_on": True, "brightness": 100},
                    {"device_id": "outlet_kitchen_coffee", "is_on": True},
                ],
            ),
            Scene(
                scene_id="scene_good_night",
                name="Good Night",
                description="Turn off all lights, lock doors, lower thermostat",
                devices=[
                    {"device_id": "light_living_main", "is_on": False},
                    {"device_id": "light_living_accent", "is_on": False},
                    {"device_id": "light_kitchen_main", "is_on": False},
                    {"device_id": "light_office_main", "is_on": False},
                    {"device_id": "light_bedroom_lamp", "is_on": True, "brightness": 10},
                    {"device_id": "lock_front", "is_locked": True},
                    {"device_id": "lock_back", "is_locked": True},
                    {"device_id": "thermostat_main", "target_temperature": 68.0, "mode": "auto"},
                ],
            ),
            Scene(
                scene_id="scene_movie_time",
                name="Movie Time",
                description="Dim lights, turn on TV, set comfortable temperature",
                devices=[
                    {"device_id": "light_living_main", "is_on": True, "brightness": 10},
                    {"device_id": "light_living_accent", "is_on": True, "brightness": 20, "hue": 270},
                    {"device_id": "switch_living_tv", "is_on": True},
                ],
            ),
            Scene(
                scene_id="scene_away",
                name="Away",
                description="All lights off, doors locked, thermostat in eco mode",
                devices=[
                    {"device_id": "light_living_main", "is_on": False},
                    {"device_id": "light_living_accent", "is_on": False},
                    {"device_id": "light_bedroom_main", "is_on": False},
                    {"device_id": "light_bedroom_lamp", "is_on": False},
                    {"device_id": "light_kitchen_main", "is_on": False},
                    {"device_id": "light_office_main", "is_on": False},
                    {"device_id": "switch_living_tv", "is_on": False},
                    {"device_id": "lock_front", "is_locked": True},
                    {"device_id": "lock_back", "is_locked": True},
                    {"device_id": "thermostat_main", "target_temperature": 65.0, "mode": "auto"},
                ],
            ),
            Scene(
                scene_id="scene_focus",
                name="Focus Mode",
                description="Office lights bright, other rooms dimmed",
                devices=[
                    {"device_id": "light_office_main", "is_on": True, "brightness": 100, "color_temp": 5500},
                    {"device_id": "light_office_desk", "is_on": True, "brightness": 80},
                    {"device_id": "light_living_main", "is_on": False},
                ],
            ),
            Scene(
                scene_id="scene_romantic",
                name="Romantic Dinner",
                description="Warm dim lights throughout",
                devices=[
                    {"device_id": "light_living_main", "is_on": True, "brightness": 20, "color_temp": 2200},
                    {"device_id": "light_living_accent", "is_on": True, "brightness": 30, "hue": 15, "saturation": 80},
                    {"device_id": "light_kitchen_main", "is_on": True, "brightness": 25, "color_temp": 2200},
                ],
            ),
        ]

        for scene in mock_scenes:
            self._scenes[scene.scene_id] = scene

    def get_device(self, device_id: str) -> Optional[DeviceState]:
        """Get a device by ID."""
        return self._devices.get(device_id)

    def get_device_by_name(self, name: str) -> Optional[DeviceState]:
        """Get a device by name (case-insensitive partial match)."""
        name_lower = name.lower()
        for device in self._devices.values():
            if name_lower in device.name.lower():
                return device
        return None

    def get_all_devices(self) -> List[DeviceState]:
        """Get all devices."""
        return list(self._devices.values())

    def get_devices_by_room(self, room: str) -> List[DeviceState]:
        """Get all devices in a room."""
        room_lower = room.lower()
        return [d for d in self._devices.values() if room_lower in d.room.lower()]

    def get_devices_by_type(self, device_type: DeviceType) -> List[DeviceState]:
        """Get all devices of a specific type."""
        return [d for d in self._devices.values() if d.device_type == device_type]

    def update_device(self, device_id: str, **kwargs) -> Optional[DeviceState]:
        """Update device state."""
        device = self._devices.get(device_id)
        if not device:
            return None

        for key, value in kwargs.items():
            if hasattr(device, key):
                setattr(device, key, value)

        device.last_updated = datetime.now().isoformat()
        return device

    def get_scene(self, scene_id: str) -> Optional[Scene]:
        """Get a scene by ID."""
        return self._scenes.get(scene_id)

    def get_scene_by_name(self, name: str) -> Optional[Scene]:
        """Get a scene by name (case-insensitive partial match)."""
        name_lower = name.lower()
        for scene in self._scenes.values():
            if name_lower in scene.name.lower():
                return scene
        return None

    def get_all_scenes(self) -> List[Scene]:
        """Get all scenes."""
        return list(self._scenes.values())

    def activate_scene(self, scene_id: str) -> bool:
        """Activate a scene by applying its device states."""
        scene = self._scenes.get(scene_id)
        if not scene:
            return False

        for device_config in scene.devices:
            device_id = device_config.get("device_id")
            if device_id:
                updates = {k: v for k, v in device_config.items() if k != "device_id"}
                self.update_device(device_id, **updates)

        # Mark scene as active, deactivate others
        for s in self._scenes.values():
            s.is_active = (s.scene_id == scene_id)

        return True


# Global smart home store instance
_smart_home_store = SmartHomeStore()


# ============================================================================
# HomeKit Integration Layer (Abstraction)
# ============================================================================

class HomeKitBridge:
    """
    Abstraction layer for HomeKit communication.

    This class provides a unified interface that can work with:
    1. Mock data (default, for testing/development)
    2. HAP-python library (for HomeKit accessory simulation)
    3. homekit library (for controlling real HomeKit devices)

    To connect to real devices:
    1. Install homekit library: pip install homekit
    2. Pair with your HomeKit controller
    3. Update the _use_real_homekit flag and implement real methods
    """

    def __init__(self):
        self._use_real_homekit = False
        self._homekit_controller = None
        self._initialize_homekit()

    def _initialize_homekit(self):
        """Try to initialize real HomeKit connection."""
        try:
            # Attempt to import homekit library
            # import homekit
            # self._homekit_controller = homekit.Controller()
            # self._use_real_homekit = True
            # logger.info("HomeKit library available - real device control enabled")
            pass
        except ImportError:
            logger.info("HomeKit library not available - using mock data")
            self._use_real_homekit = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to real HomeKit devices."""
        return self._use_real_homekit

    async def list_devices(self) -> List[Dict[str, Any]]:
        """List all available devices."""
        if self._use_real_homekit:
            # Real HomeKit implementation would go here
            pass

        # Use mock data
        return [d.to_dict() for d in _smart_home_store.get_all_devices()]

    async def get_device_state(self, device_name: str) -> Optional[Dict[str, Any]]:
        """Get current state of a device."""
        if self._use_real_homekit:
            # Real HomeKit implementation would go here
            pass

        device = _smart_home_store.get_device_by_name(device_name)
        if device:
            return device.to_dict()
        return None

    async def control_device(
        self,
        device_name: str,
        action: str,
        value: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Control a device."""
        if self._use_real_homekit:
            # Real HomeKit implementation would go here
            pass

        device = _smart_home_store.get_device_by_name(device_name)
        if not device:
            return {"error": f"Device not found: {device_name}"}

        # Apply action
        action = action.lower()
        updates = {}

        if action == "on":
            updates["is_on"] = True
            if device.device_type == DeviceType.LIGHT and device.brightness == 0:
                updates["brightness"] = 100
        elif action == "off":
            updates["is_on"] = False
            if device.device_type == DeviceType.LIGHT:
                updates["brightness"] = 0
        elif action == "toggle":
            updates["is_on"] = not device.is_on
            if device.device_type == DeviceType.LIGHT:
                updates["brightness"] = 100 if not device.is_on else 0
        elif action == "set" and value is not None:
            if device.device_type == DeviceType.LIGHT:
                if isinstance(value, (int, float)):
                    updates["brightness"] = max(0, min(100, int(value)))
                    updates["is_on"] = updates["brightness"] > 0
            elif device.device_type == DeviceType.THERMOSTAT:
                if isinstance(value, (int, float)):
                    updates["target_temperature"] = float(value)
            elif device.device_type == DeviceType.BLIND:
                if isinstance(value, (int, float)):
                    updates["position"] = max(0, min(100, int(value)))
        elif action == "lock":
            updates["is_locked"] = True
        elif action == "unlock":
            updates["is_locked"] = False
        elif action == "open":
            if device.device_type == DeviceType.GARAGE_DOOR:
                updates["position"] = 100
            elif device.device_type == DeviceType.BLIND:
                updates["position"] = 100
        elif action == "close":
            if device.device_type == DeviceType.GARAGE_DOOR:
                updates["position"] = 0
            elif device.device_type == DeviceType.BLIND:
                updates["position"] = 0
        else:
            return {"error": f"Unknown action: {action}"}

        updated_device = _smart_home_store.update_device(device.device_id, **updates)
        if updated_device:
            return {
                "success": True,
                "device": updated_device.to_dict(),
                "action": action,
                "value": value,
            }
        return {"error": "Failed to update device"}

    async def list_scenes(self) -> List[Dict[str, Any]]:
        """List all available scenes."""
        scenes = _smart_home_store.get_all_scenes()
        return [
            {
                "scene_id": s.scene_id,
                "name": s.name,
                "description": s.description,
                "is_active": s.is_active,
                "device_count": len(s.devices),
            }
            for s in scenes
        ]

    async def activate_scene(self, scene_name: str) -> Dict[str, Any]:
        """Activate a scene."""
        scene = _smart_home_store.get_scene_by_name(scene_name)
        if not scene:
            return {"error": f"Scene not found: {scene_name}"}

        if _smart_home_store.activate_scene(scene.scene_id):
            return {
                "success": True,
                "scene": scene.name,
                "description": scene.description,
                "devices_affected": len(scene.devices),
            }
        return {"error": "Failed to activate scene"}


# Global HomeKit bridge instance
_homekit_bridge = HomeKitBridge()


# ============================================================================
# Tool Implementation Functions
# ============================================================================

async def list_smart_devices(
    room: Optional[str] = None,
    device_type: Optional[str] = None,
) -> str:
    """List all connected smart home devices.

    Args:
        room: Optional room filter (e.g., "Living Room", "Bedroom")
        device_type: Optional type filter (light, switch, thermostat, lock, etc.)

    Returns:
        JSON string with device list
    """
    logger.info(f"Listing smart devices (room={room}, type={device_type})")

    try:
        all_devices = await _homekit_bridge.list_devices()

        # Apply filters
        filtered = all_devices

        if room:
            room_lower = room.lower()
            filtered = [d for d in filtered if room_lower in d.get("room", "").lower()]

        if device_type:
            type_lower = device_type.lower()
            filtered = [d for d in filtered if d.get("device_type", "").lower() == type_lower]

        # Group by room for better readability
        by_room: Dict[str, List[Dict]] = {}
        for device in filtered:
            room_name = device.get("room", "Unknown")
            if room_name not in by_room:
                by_room[room_name] = []
            by_room[room_name].append(device)

        # Calculate summary
        online_count = sum(1 for d in filtered if d.get("is_online"))

        result = {
            "total_devices": len(filtered),
            "online_devices": online_count,
            "offline_devices": len(filtered) - online_count,
            "rooms": list(by_room.keys()),
            "devices_by_room": by_room,
            "homekit_connected": _homekit_bridge.is_connected,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error listing devices: {e}")
        return json.dumps({"error": str(e)})


async def control_device(
    device_name: str,
    action: str,
    value: Optional[Union[int, float, str]] = None,
) -> str:
    """Control a smart home device.

    Args:
        device_name: Name of the device to control
        action: Action to perform (on, off, toggle, set, lock, unlock, open, close)
        value: Optional value for 'set' action (brightness 0-100, temperature, etc.)

    Returns:
        JSON string with result
    """
    logger.info(f"Controlling device: {device_name}, action={action}, value={value}")

    try:
        result = await _homekit_bridge.control_device(device_name, action, value)
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error controlling device: {e}")
        return json.dumps({"error": str(e)})


async def get_device_state(device_name: str) -> str:
    """Get the current state of a device.

    Args:
        device_name: Name of the device

    Returns:
        JSON string with device state
    """
    logger.info(f"Getting state for device: {device_name}")

    try:
        state = await _homekit_bridge.get_device_state(device_name)

        if state:
            return json.dumps({
                "found": True,
                "device": state,
            }, indent=2)
        else:
            # Try to find similar devices
            all_devices = await _homekit_bridge.list_devices()
            suggestions = [
                d["name"] for d in all_devices
                if device_name.lower().split()[0] in d["name"].lower()
            ][:5]

            return json.dumps({
                "found": False,
                "error": f"Device not found: {device_name}",
                "suggestions": suggestions if suggestions else None,
            }, indent=2)

    except Exception as e:
        logger.error(f"Error getting device state: {e}")
        return json.dumps({"error": str(e)})


async def activate_scene(scene_name: str) -> str:
    """Activate a smart home scene.

    Args:
        scene_name: Name of the scene to activate

    Returns:
        JSON string with result
    """
    logger.info(f"Activating scene: {scene_name}")

    try:
        result = await _homekit_bridge.activate_scene(scene_name)
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error activating scene: {e}")
        return json.dumps({"error": str(e)})


async def list_scenes() -> str:
    """List all available smart home scenes.

    Returns:
        JSON string with scene list
    """
    logger.info("Listing smart home scenes")

    try:
        scenes = await _homekit_bridge.list_scenes()

        return json.dumps({
            "total_scenes": len(scenes),
            "scenes": scenes,
        }, indent=2)

    except Exception as e:
        logger.error(f"Error listing scenes: {e}")
        return json.dumps({"error": str(e)})


async def set_thermostat(
    temperature: float,
    mode: Optional[str] = None,
    device_name: str = "thermostat",
) -> str:
    """Set the thermostat temperature.

    Args:
        temperature: Target temperature in Fahrenheit
        mode: Optional mode (heat, cool, auto, off)
        device_name: Name of thermostat (default: "thermostat")

    Returns:
        JSON string with result
    """
    logger.info(f"Setting thermostat: temp={temperature}, mode={mode}")

    try:
        # Find thermostat
        device = _smart_home_store.get_device_by_name(device_name)
        if not device or device.device_type != DeviceType.THERMOSTAT:
            # Try to find any thermostat
            thermostats = _smart_home_store.get_devices_by_type(DeviceType.THERMOSTAT)
            if not thermostats:
                return json.dumps({"error": "No thermostat found"})
            device = thermostats[0]

        updates = {"target_temperature": float(temperature)}
        if mode:
            if mode.lower() in ["heat", "cool", "auto", "off"]:
                updates["mode"] = mode.lower()
                updates["is_on"] = mode.lower() != "off"
            else:
                return json.dumps({"error": f"Invalid mode: {mode}. Use heat, cool, auto, or off."})

        updated = _smart_home_store.update_device(device.device_id, **updates)

        if updated:
            return json.dumps({
                "success": True,
                "device": updated.to_dict(),
                "message": f"Thermostat set to {temperature}°F" + (f" in {mode} mode" if mode else ""),
            }, indent=2)

        return json.dumps({"error": "Failed to update thermostat"})

    except Exception as e:
        logger.error(f"Error setting thermostat: {e}")
        return json.dumps({"error": str(e)})


async def control_lights(
    room: str,
    action: str,
    brightness: Optional[int] = None,
    color_temp: Optional[int] = None,
) -> str:
    """Control lights in a specific room.

    Args:
        room: Room name (e.g., "Living Room", "Bedroom", "all")
        action: Action to perform (on, off, toggle, set)
        brightness: Optional brightness level (0-100)
        color_temp: Optional color temperature in Kelvin (2200-6500)

    Returns:
        JSON string with result
    """
    logger.info(f"Controlling lights: room={room}, action={action}, brightness={brightness}")

    try:
        # Get lights in room
        if room.lower() == "all":
            lights = _smart_home_store.get_devices_by_type(DeviceType.LIGHT)
        else:
            room_devices = _smart_home_store.get_devices_by_room(room)
            lights = [d for d in room_devices if d.device_type == DeviceType.LIGHT]

        if not lights:
            return json.dumps({"error": f"No lights found in {room}"})

        results = []
        for light in lights:
            updates = {}

            if action.lower() == "on":
                updates["is_on"] = True
                if brightness is not None:
                    updates["brightness"] = max(0, min(100, brightness))
                elif light.brightness == 0:
                    updates["brightness"] = 100
            elif action.lower() == "off":
                updates["is_on"] = False
                updates["brightness"] = 0
            elif action.lower() == "toggle":
                updates["is_on"] = not light.is_on
                updates["brightness"] = 100 if not light.is_on else 0
            elif action.lower() == "set":
                if brightness is not None:
                    updates["brightness"] = max(0, min(100, brightness))
                    updates["is_on"] = brightness > 0

            if color_temp is not None:
                updates["color_temp"] = max(2200, min(6500, color_temp))

            updated = _smart_home_store.update_device(light.device_id, **updates)
            if updated:
                results.append({
                    "name": updated.name,
                    "is_on": updated.is_on,
                    "brightness": updated.brightness,
                    "color_temp": updated.color_temp,
                })

        return json.dumps({
            "success": True,
            "room": room,
            "action": action,
            "lights_affected": len(results),
            "lights": results,
        }, indent=2)

    except Exception as e:
        logger.error(f"Error controlling lights: {e}")
        return json.dumps({"error": str(e)})


async def get_home_status() -> str:
    """Get overall smart home status summary.

    Returns:
        JSON string with home status
    """
    logger.info("Getting home status")

    try:
        all_devices = await _homekit_bridge.list_devices()
        scenes = await _homekit_bridge.list_scenes()

        # Find thermostat
        thermostat = None
        for d in all_devices:
            if d.get("device_type") == "thermostat":
                thermostat = d
                break

        # Count lights on
        lights = [d for d in all_devices if d.get("device_type") == "light"]
        lights_on = sum(1 for l in lights if l.get("is_on"))

        # Check locks
        locks = [d for d in all_devices if d.get("device_type") == "lock"]
        all_locked = all(l.get("is_locked", False) for l in locks)

        # Active scene
        active_scene = next((s for s in scenes if s.get("is_active")), None)

        return json.dumps({
            "timestamp": datetime.now().isoformat(),
            "climate": {
                "current_temp": thermostat.get("temperature") if thermostat else None,
                "target_temp": thermostat.get("target_temperature") if thermostat else None,
                "mode": thermostat.get("mode") if thermostat else None,
                "humidity": thermostat.get("humidity") if thermostat else None,
            },
            "lighting": {
                "lights_on": lights_on,
                "total_lights": len(lights),
            },
            "security": {
                "all_locked": all_locked,
                "locks": [{"name": l["name"], "locked": l.get("is_locked")} for l in locks],
            },
            "active_scene": active_scene.get("name") if active_scene else None,
            "total_devices": len(all_devices),
            "online_devices": sum(1 for d in all_devices if d.get("is_online")),
        }, indent=2)

    except Exception as e:
        logger.error(f"Error getting home status: {e}")
        return json.dumps({"error": str(e)})


# ============================================================================
# Tool Definitions for AI
# ============================================================================

SMART_HOME_TOOLS = [
    {
        "name": "list_smart_devices",
        "description": "List all connected smart home devices (lights, switches, thermostats, locks, sensors, etc.). Can filter by room or device type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "description": "Filter by room name (e.g., 'Living Room', 'Bedroom', 'Kitchen')",
                },
                "device_type": {
                    "type": "string",
                    "description": "Filter by device type (light, switch, thermostat, lock, sensor, fan, outlet, garage_door, blind)",
                    "enum": ["light", "switch", "thermostat", "lock", "sensor", "fan", "outlet", "garage_door", "blind"],
                },
            },
        },
    },
    {
        "name": "control_device",
        "description": "Control a smart home device. Supports turning on/off, toggling, setting values, locking/unlocking, and opening/closing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_name": {
                    "type": "string",
                    "description": "Name of the device to control (e.g., 'Living Room Main Light', 'Front Door Lock')",
                },
                "action": {
                    "type": "string",
                    "description": "Action to perform on the device",
                    "enum": ["on", "off", "toggle", "set", "lock", "unlock", "open", "close"],
                },
                "value": {
                    "type": "number",
                    "description": "Value for 'set' action (brightness 0-100 for lights, temperature for thermostat, position 0-100 for blinds)",
                },
            },
            "required": ["device_name", "action"],
        },
    },
    {
        "name": "get_device_state",
        "description": "Get the current state of a smart home device including power state, brightness, temperature, lock status, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_name": {
                    "type": "string",
                    "description": "Name of the device (partial name matching supported)",
                },
            },
            "required": ["device_name"],
        },
    },
    {
        "name": "activate_scene",
        "description": "Activate a smart home scene. Scenes control multiple devices at once (e.g., 'Good Night', 'Movie Time', 'Away').",
        "input_schema": {
            "type": "object",
            "properties": {
                "scene_name": {
                    "type": "string",
                    "description": "Name of the scene to activate (e.g., 'Good Morning', 'Good Night', 'Movie Time', 'Away', 'Focus Mode')",
                },
            },
            "required": ["scene_name"],
        },
    },
    {
        "name": "list_scenes",
        "description": "List all available smart home scenes with their descriptions.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "set_thermostat",
        "description": "Set the thermostat temperature and optionally the mode (heat, cool, auto, off).",
        "input_schema": {
            "type": "object",
            "properties": {
                "temperature": {
                    "type": "number",
                    "description": "Target temperature in Fahrenheit",
                },
                "mode": {
                    "type": "string",
                    "description": "Thermostat mode",
                    "enum": ["heat", "cool", "auto", "off"],
                },
                "device_name": {
                    "type": "string",
                    "description": "Name of specific thermostat (default: 'thermostat')",
                    "default": "thermostat",
                },
            },
            "required": ["temperature"],
        },
    },
    {
        "name": "control_lights",
        "description": "Control all lights in a specific room. Can turn on/off, set brightness, and adjust color temperature.",
        "input_schema": {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "description": "Room name (e.g., 'Living Room', 'Bedroom') or 'all' for all lights",
                },
                "action": {
                    "type": "string",
                    "description": "Action to perform",
                    "enum": ["on", "off", "toggle", "set"],
                },
                "brightness": {
                    "type": "integer",
                    "description": "Brightness level (0-100)",
                    "minimum": 0,
                    "maximum": 100,
                },
                "color_temp": {
                    "type": "integer",
                    "description": "Color temperature in Kelvin (2200=warm, 6500=cool)",
                    "minimum": 2200,
                    "maximum": 6500,
                },
            },
            "required": ["room", "action"],
        },
    },
    {
        "name": "get_home_status",
        "description": "Get overall smart home status including temperature, lighting summary, security status, and active scene.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]
