"""Configuration persistante de VLC Redesign."""
import json
import shutil
import uuid
from copy import deepcopy
from pathlib import Path

MAX_VOLUME = 125
CONFIG_PATH = Path.home() / ".vlc_redesign.json"
DEFAULTS = {
    "library": [], "recents": [], "favorites": [], "playlists": {}, "playlist_images": {}, "queue": [], "accent": "#ff6b35",
    "background": "#0e0e0f",
    "element_color": "#171718",
    "background_mode": "color", "background_image": "", "background_blurred_image": "",
    "volume": 80, "muted": False, "playback_rate": 1.0,
    "repeat_mode": "off", "autoplay_next": True, "show_lyrics": False,
    "crossfade_seconds": 0,
    "resume_positions": {}, "smart_playlists": {},
    "resume_playback": True,
    "equalizer_enabled": False, "equalizer_preset": "flat",
    "equalizer_bands": [0.0] * 10, "equalizer_preamp": 0.0,
    "normalize_audio": False,
    "lyrics_online": True, "sort_key": "name", "sort_reverse": False,
    "shortcuts": {}, "setup_done": False, "language": "fr", "meta": {},
    "sidebar_collapsed": False,
    "auto_update": True, "skipped_version": "",
}

class Config:
    def __init__(self, path=None):
        self.root_path = Path(path) if path else CONFIG_PATH
        self.profile_root = self.root_path.parent / ".vlc_redesign" / "profiles"
        self.profile_index_path = self.root_path.parent / ".vlc_redesign" / "profiles.json"
        self.profiles = [{"id": "principal", "name": "Principal"}]
        self.active_profile = "principal"
        self._load_profile_index()
        self.path = self._profile_path(self.active_profile)
        self.data = self._load_data(self.path)

    def _profile_path(self, profile_id):
        return self.root_path if profile_id == "principal" else self.profile_root / f"{profile_id}.json"

    def _load_profile_index(self):
        try:
            loaded = json.loads(self.profile_index_path.read_text(encoding="utf-8"))
            profiles = loaded.get("profiles") if isinstance(loaded, dict) else None
            if isinstance(profiles, list) and profiles:
                valid = [
                    p for p in profiles
                    if isinstance(p, dict)
                    and isinstance(p.get("id"), str)
                    and (p["id"] == "principal" or (p["id"].isalnum() and len(p["id"]) <= 32))
                    and isinstance(p.get("name"), str) and p["name"].strip()
                ]
                if valid:
                    self.profiles = valid
                    requested = loaded.get("active")
                    if any(p["id"] == requested for p in valid):
                        self.active_profile = requested
        except (OSError, ValueError, TypeError):
            pass

    def _save_profile_index(self):
        try:
            self.profile_index_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"active": self.active_profile, "profiles": self.profiles}
            temp = self.profile_index_path.with_suffix(".tmp")
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.profile_index_path)
            return True
        except (OSError, TypeError, ValueError):
            return False

    @staticmethod
    def _load_data(path):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = deepcopy(DEFAULTS)
                data.update(loaded)
            else:
                data = deepcopy(DEFAULTS)
        except (OSError, ValueError, TypeError):
            data = deepcopy(DEFAULTS)
        for key, value in DEFAULTS.items():
            if key not in data:
                data[key] = value
        if not isinstance(data.get("library"), list): data["library"] = []
        if not isinstance(data.get("recents"), list): data["recents"] = []
        if not isinstance(data.get("favorites"), list): data["favorites"] = []
        if not isinstance(data.get("playlists"), dict): data["playlists"] = {}
        if not isinstance(data.get("playlist_images"), dict): data["playlist_images"] = {}
        if not isinstance(data.get("queue"), list): data["queue"] = []
        if not isinstance(data.get("meta"), dict): data["meta"] = {}
        if not isinstance(data.get("resume_positions"), dict): data["resume_positions"] = {}
        if not isinstance(data.get("smart_playlists"), dict): data["smart_playlists"] = {}
        if not isinstance(data.get("equalizer_bands"), list) or len(data["equalizer_bands"]) != 10:
            data["equalizer_bands"] = [0.0] * 10
        return data

    def switch_profile(self, profile_id):
        if profile_id == self.active_profile:
            return True
        if not any(profile["id"] == profile_id for profile in self.profiles):
            return False
        if not self.save():
            return False
        self.active_profile = profile_id
        self.path = self._profile_path(profile_id)
        self.data = self._load_data(self.path)
        self._save_profile_index()
        return True

    def create_profile(self, name):
        name = str(name).strip()
        if not name or any(p["name"].casefold() == name.casefold() for p in self.profiles):
            return False
        profile_id = uuid.uuid4().hex
        self.profiles.append({"id": profile_id, "name": name})
        if not self._save_profile_index():
            self.profiles.pop()
            return False
        if not self.switch_profile(profile_id):
            self.profiles.pop()
            self._save_profile_index()
            return False
        return True

    def rename_profile(self, profile_id, name):
        name = str(name).strip()
        profile = next((p for p in self.profiles if p["id"] == profile_id), None)
        if not profile or not name or any(
            p["id"] != profile_id and p["name"].casefold() == name.casefold()
            for p in self.profiles
        ):
            return False
        previous = profile["name"]
        profile["name"] = name
        if not self._save_profile_index():
            profile["name"] = previous
            return False
        return True

    def set_profile_image(self, profile_id, source_path):
        profile = next((p for p in self.profiles if p["id"] == profile_id), None)
        source = Path(source_path)
        if not profile or not source.is_file():
            return False
        target_dir = self.profile_root / profile_id / "profile"
        target = target_dir / ("avatar" + source.suffix.lower())
        previous = profile.get("image")
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            if source.resolve() != target.resolve():
                shutil.copy2(source, target)
            profile["image"] = str(target)
            if not self._save_profile_index():
                if previous:
                    profile["image"] = previous
                else:
                    profile.pop("image", None)
                return False
            return True
        except OSError:
            return False

    def delete_profile(self, profile_id):
        """Supprime un espace secondaire et ses données locales."""
        if profile_id == "principal" or profile_id == self.active_profile:
            return False
        profile = next((p for p in self.profiles if p["id"] == profile_id), None)
        if profile is None or len(self.profiles) <= 1:
            return False
        data_path = self._profile_path(profile_id)
        assets_path = self.profile_root / profile_id
        try:
            data_path.unlink(missing_ok=True)
            shutil.rmtree(assets_path, ignore_errors=True)
        except OSError:
            return False
        self.profiles.remove(profile)
        return self._save_profile_index()

    def reset_application(self):
        """Restore default settings and remove all saved user spaces and app caches."""
        app_data_dir = self.profile_index_path.parent
        try:
            if app_data_dir.exists():
                shutil.rmtree(app_data_dir)
            self.profiles = [{"id": "principal", "name": "Principal"}]
            self.active_profile = "principal"
            self.path = self.root_path
            self.data = deepcopy(DEFAULTS)
            return self.save()
        except OSError:
            return False

    def get(self, key, default=None):
        return self.data.get(key, DEFAULTS.get(key, default))

    def set(self, key, value):
        self.data[key] = value

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.path)
            return self._save_profile_index()
        except (OSError, TypeError, ValueError):
            return False
