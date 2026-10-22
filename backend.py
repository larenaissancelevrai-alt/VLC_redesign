"""Moteur de lecture : une fine couche autour de python-vlc.

Aucune dépendance à Qt ici. Si libVLC est absent, `Backend.available` vaut
False et toutes les méthodes deviennent des no-op : l'interface reste utilisable
(on peut parcourir la bibliothèque) et affiche un message clair.
"""

import os
import sys
from pathlib import Path


def _prepare_vlc_environment():
    """Aide python-vlc à trouver VLC (installation standard Windows/macOS)."""
    try:
        import diagnose
        found = diagnose.vlc_environment()
    except Exception:
        return
    for key, value in found.items():
        os.environ.setdefault(key, value)
    lib = found.get("PYTHON_VLC_LIB_PATH")
    if lib and hasattr(os, "add_dll_directory") and sys.platform.startswith("win"):
        try:
            os.add_dll_directory(os.path.dirname(lib))
        except OSError:
            pass


_prepare_vlc_environment()

try:
    import vlc
    _IMPORT_ERROR = None
except Exception as exc:  # ImportError, mais aussi OSError si libvlc est introuvable
    vlc = None
    _IMPORT_ERROR = str(exc)

AUDIO_EXT = {".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".wma", ".opus"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".flv", ".m4v", ".mpg", ".mpeg", ".ts"}
MEDIA_EXT = AUDIO_EXT | VIDEO_EXT
AUDIO_TRACK_EXT = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".opus", ".wma", ".mka", ".ac3", ".dts"}
SUBTITLE_EXT = {".srt", ".ass", ".ssa", ".sub", ".vtt", ".idx", ".smi", ".txt"}
MAX_VOLUME = 125   # comme VLC : jusqu'à 125 %


def is_stream(mrl):
    return "://" in mrl


def kind_of(mrl):
    """'stream', 'audio' ou 'video'."""
    if is_stream(mrl):
        return "stream"
    return "audio" if Path(mrl).suffix.lower() in AUDIO_EXT else "video"


def display_name(mrl):
    return mrl if is_stream(mrl) else Path(mrl).name


class Backend:
    def __init__(self):
        self.instance = None
        self.player = None
        self.crossfade_player = None
        self.error = _IMPORT_ERROR
        self._volume = 80
        self._muted = False
        self._rate = 1.0
        self._sync_audio = False
        self._crossfade_running = False
        self._crossfade_progress = 0.0
        self._equalizer_enabled = False
        self._equalizer_bands = [0.0] * 10
        self._equalizer_preamp = 0.0
        self._normalize_audio = False

        if vlc is None:
            return
        try:
            self.instance = vlc.Instance("--no-video-title-show")
            self.player = self.instance.media_player_new()
            self.crossfade_player = self.instance.media_player_new()
        except Exception as exc:
            self.instance = None
            self.player = None
            self.error = str(exc)
        if self.player is None and self.error is None:
            self.error = "libVLC n'a pas pu être initialisé."

    # ------------------------------------------------------------------ état
    @property
    def available(self):
        return self.player is not None

    def error_message(self):
        try:
            import diagnose
            _level, message = diagnose.check_vlc(False, self.error or "")
        except Exception:
            message = ("libVLC est introuvable ou n'a pas pu démarrer. Installez VLC "
                       "(même architecture que Python) puis relancez l'application.")
        return f"{message}\n\nOutil de diagnostic : python diagnose.py"

    # ------------------------------------------------------------ lecture
    def attach(self, window_id):
        """Dessine la vidéo dans le widget natif `window_id`."""
        if not self.available:
            return
        if sys.platform.startswith("win"):
            self.player.set_hwnd(window_id)
        elif sys.platform == "darwin":
            self.player.set_nsobject(window_id)
        else:
            self.player.set_xwindow(window_id)
        # Laisse Qt recevoir clics et touches (menu contextuel, raccourcis…)
        try:
            self.player.video_set_mouse_input(False)
            self.player.video_set_key_input(False)
        except Exception:
            pass

    def play(self, mrl, window_id):
        if not self.available:
            return
        media = self.instance.media_new(mrl)  # accepte chemins locaux et URL
        self._apply_media_options(media)
        self.player.set_media(media)
        self.attach(window_id)
        self.player.play()
        self._sync_audio = True  # volume/mute/vitesse réappliqués dès que la lecture démarre

    def resume(self):
        if self.available:
            self.player.play()
            if self._crossfade_running:
                self.crossfade_player.play()

    def pause(self):
        if self.available:
            self.player.set_pause(1)
            if self._crossfade_running:
                self.crossfade_player.set_pause(1)

    def stop(self):
        if self.available:
            self.player.stop()
            if self.crossfade_player:
                self.crossfade_player.stop()
            self._crossfade_running = False
            self._crossfade_progress = 0.0

    def begin_crossfade(self, mrl):
        """Start an audio-only second player at zero volume."""
        if not self.available or self.crossfade_player is None:
            return False
        try:
            self.crossfade_player.stop()
            media = self.instance.media_new(mrl)
            self._apply_media_options(media)
            self.crossfade_player.set_media(media)
            try:
                self.crossfade_player.set_rate(self._rate)
            except Exception:
                pass
            self.crossfade_player.audio_set_mute(self._muted)
            self.crossfade_player.audio_set_volume(0)
            self.crossfade_player.play()
            self._crossfade_progress = 0.0
            self._crossfade_running = True
            return True
        except Exception:
            return False

    def set_crossfade_progress(self, progress):
        if not self.available or self.crossfade_player is None:
            return
        progress = max(0.0, min(1.0, float(progress)))
        self._crossfade_progress = progress
        # The two gains cross linearly: outgoing fades from full to silent,
        # incoming fades from silent to full over the same interval.
        outgoing_gain = 1.0 - progress
        incoming_gain = progress
        volume = 0 if self._muted else self._volume
        self.player.audio_set_volume(round(volume * outgoing_gain))
        self.crossfade_player.audio_set_volume(round(volume * incoming_gain))

    def crossfade_status(self):
        """Return whether the incoming player has started and its elapsed time."""
        if not self._crossfade_running or self.crossfade_player is None:
            return False, 0
        try:
            if self.crossfade_player.is_playing():
                try:
                    self.crossfade_player.set_rate(self._rate)
                except Exception:
                    pass
                return True, max(0, self.crossfade_player.get_time())
        except Exception:
            pass
        return False, 0

    def cancel_crossfade(self):
        if self.crossfade_player is not None and self._crossfade_running:
            self.crossfade_player.stop()
            self._crossfade_running = False
            if self.available:
                self.player.audio_set_volume(0 if self._muted else self._volume)
                self.crossfade_player.audio_set_volume(0 if self._muted else self._volume)
            self._crossfade_progress = 0.0

    def finish_crossfade(self):
        """Promote the incoming player and keep a second player ready for reuse."""
        if not self.available or self.crossfade_player is None:
            return False
        previous = self.player
        self.player = self.crossfade_player
        self.crossfade_player = previous
        self.crossfade_player.stop()
        self._crossfade_running = False
        self._crossfade_progress = 0.0
        self.player.audio_set_mute(self._muted)
        self.player.audio_set_volume(0 if self._muted else self._volume)
        self._sync_audio = False
        return True

    def active(self):
        """Compatibilité avec les appels de l’interface : vrai pendant la lecture."""
        return self.playing()

    def has_video(self):
        """Indique si le média courant expose une piste vidéo."""
        if not self.available:
            return False
        try:
            media = self.player.get_media()
            if media is None:
                return False
            media.parse()
            tracks = media.tracks_get() or []
            return any(getattr(track, "type", None) == vlc.TrackType.video for track in tracks)
        except Exception:
            # Certains médias/versions libVLC ne sont pas encore analysables.
            return False

    def playing(self):
        return self.available and bool(self.player.is_playing())

    def ended(self):
        return self.available and self.player.get_state() == vlc.State.Ended

    def tick(self):
        """À appeler régulièrement : applique volume/vitesse une fois la lecture démarrée."""
        if self._sync_audio and self.playing():
            self.player.audio_set_volume(self._volume)
            self.player.audio_set_mute(self._muted)
            try:
                self.player.set_rate(self._rate)
            except Exception:
                pass
            self._sync_audio = False

    # ------------------------------------------------------------- position
    def length(self):
        return max(0, self.player.get_length()) if self.available else 0

    def time(self):
        return max(0, self.player.get_time()) if self.available else 0

    def seek_fraction(self, fraction):
        if self.available and self.length() > 0:
            self.player.set_position(min(max(fraction, 0.0), 1.0))

    def seek_ms(self, ms):
        if self.available and self.length() > 0:
            self.player.set_time(int(min(max(ms, 0), self.length())))

    # ---------------------------------------------------------------- audio
    @property
    def volume(self):
        return self._volume

    @property
    def muted(self):
        return self._muted

    def set_volume(self, value):
        self._volume = max(0, min(MAX_VOLUME, int(value)))
        if self.available:
            if self._crossfade_running:
                self.set_crossfade_progress(self._crossfade_progress)
            else:
                self.player.audio_set_volume(self._volume)
                if self.crossfade_player:
                    self.crossfade_player.audio_set_volume(self._volume)

    def set_muted(self, muted):
        self._muted = bool(muted)
        if self.available:
            self.player.audio_set_mute(self._muted)
            if self.crossfade_player:
                self.crossfade_player.audio_set_mute(self._muted)

    @property
    def rate(self):
        return self._rate

    def set_rate(self, rate):
        self._rate = max(0.25, min(4.0, float(rate)))
        if self.available:
            try:
                self.player.set_rate(self._rate)
                if self._crossfade_running and self.crossfade_player:
                    self.crossfade_player.set_rate(self._rate)
            except Exception:
                pass

    def _apply_media_options(self, media):
        if self._normalize_audio:
            try:
                media.add_option(":audio-replay-gain-mode=track")
            except Exception:
                pass

    def set_normalize_audio(self, enabled):
        """Enable VLC ReplayGain normalization for media that contains ReplayGain tags."""
        self._normalize_audio = bool(enabled)

    def set_equalizer(self, enabled, bands=None, preamp=0.0):
        """Apply 10-band equalizer settings to both playback players."""
        self._equalizer_enabled = bool(enabled)
        if bands is not None:
            try:
                self._equalizer_bands = [max(-20.0, min(20.0, float(v))) for v in bands[:10]]
                self._equalizer_bands += [0.0] * (10 - len(self._equalizer_bands))
            except (TypeError, ValueError):
                self._equalizer_bands = [0.0] * 10
        try:
            self._equalizer_preamp = max(-20.0, min(20.0, float(preamp)))
        except (TypeError, ValueError):
            self._equalizer_preamp = 0.0
        if not self.available:
            return False
        players = [p for p in (self.player, self.crossfade_player) if p is not None]
        if not self._equalizer_enabled:
            try:
                for player in players:
                    player.set_equalizer(None)
                return True
            except Exception:
                return False
        equalizer = None
        try:
            equalizer = vlc.AudioEqualizer()
            equalizer.set_preamp(self._equalizer_preamp)
            for index, value in enumerate(self._equalizer_bands):
                equalizer.set_amp_at_index(value, index)
            for player in players:
                if player.set_equalizer(equalizer) < 0:
                    return False
            return True
        except Exception:
            return False
        finally:
            if equalizer is not None:
                try:
                    equalizer.release()
                except Exception:
                    pass

    # -------------------------------------------------------------- pistes
    @staticmethod
    def _decode(raw):
        out = []
        for track_id, name in raw or []:
            if isinstance(name, bytes):
                name = name.decode("utf-8", "replace")
            out.append((track_id, name))
        return out

    def audio_tracks(self):
        """(liste de (id, nom), id de la piste active)."""
        if not self.available:
            return [], -1
        try:
            return (self._decode(self.player.audio_get_track_description()),
                    self.player.audio_get_track())
        except Exception:
            return [], -1

    def set_audio_track(self, track_id):
        if self.available:
            self.player.audio_set_track(track_id)

    def subtitle_tracks(self):
        if not self.available:
            return [], -1
        try:
            return (self._decode(self.player.video_get_spu_description()),
                    self.player.video_get_spu())
        except Exception:
            return [], -1

    def set_subtitle_track(self, track_id):
        if self.available:
            self.player.video_set_spu(track_id)

    @staticmethod
    def _next_track(tracks, current):
        if not tracks:
            return None
        ids = [t[0] for t in tracks]
        pos = ids.index(current) if current in ids else -1
        return tracks[(pos + 1) % len(tracks)]

    def cycle_audio_track(self):
        """Passe à la piste audio suivante. Renvoie son nom, ou None."""
        tracks, current = self.audio_tracks()
        nxt = self._next_track(tracks, current)
        if nxt:
            self.set_audio_track(nxt[0])
            return nxt[1]
        return None

    def cycle_subtitle_track(self):
        tracks, current = self.subtitle_tracks()
        nxt = self._next_track(tracks, current)
        if nxt:
            self.set_subtitle_track(nxt[0])
            return nxt[1]
        return None

    # ---------------------------------------------- pistes / sous-titres externes
    def add_external_track(self, kind, path):
        """Ajoute un fichier audio ou de sous-titres au média en cours.

        `kind` : "audio" ou "subtitle". Renvoie (ok, message d'erreur).
        La lecture continue sans interruption et la nouvelle piste est sélectionnée.
        """
        if not self.available or self.player.get_media() is None:
            return False, "Lancez d'abord une vidéo."
        try:
            uri = Path(path).resolve().as_uri()      # VLC veut une URI file:// encodée
        except (OSError, ValueError):
            return False, "Chemin de fichier invalide."
        try:
            if hasattr(self.player, "add_slave"):
                slave = (vlc.MediaSlaveType.audio if kind == "audio"
                         else vlc.MediaSlaveType.subtitle)
                result = self.player.add_slave(slave, uri, True)
                if result == 0 or result is True:
                    return True, ""
            if kind == "subtitle":          # ancienne version de python-vlc / libVLC
                if self.player.video_set_subtitle_file(str(path)):
                    return True, ""
                return False, "VLC n'a pas pu charger ce fichier de sous-titres."
            return False, ("Cette version de VLC ne permet pas d'ajouter une piste audio "
                           "externe. Mettez à jour VLC et python-vlc.")
        except Exception as exc:
            return False, str(exc)

    # ------------------------------------------------------------- fermeture
    def close(self):
        if not self.available:
            return
        try:
            self.player.stop()
            self.player.release()
            if self.crossfade_player:
                self.crossfade_player.stop()
                self.crossfade_player.release()
            self.instance.release()
        finally:
            self.player = None
            self.crossfade_player = None
            self.instance = None
