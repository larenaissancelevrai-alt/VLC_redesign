"""Exécution des tâches longues hors du thread graphique Qt."""
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal

class _Signals(QObject):
    finished = Signal(object, object, object, object)

class AsyncRunner:
    def __init__(self, parent=None, workers=3):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="vlc-redesign")
        self._signals = _Signals(parent)
        self._signals.finished.connect(self._deliver)
        self._closed = False
        self._keys = set()

    def run(self, work, done=None, failed=None, key=None):
        if self._closed or (key is not None and key in self._keys):
            return False
        if key is not None: self._keys.add(key)
        future = self._pool.submit(work)
        def completed(f):
            try: result, error = f.result(), None
            except Exception as exc: result, error = None, exc
            self._signals.finished.emit(key, result, error, (done, failed))
        future.add_done_callback(completed)
        return True

    def _deliver(self, key, result, error, callbacks):
        if key is not None: self._keys.discard(key)
        done, failed = callbacks
        if error is not None:
            if failed: failed(error)
        elif done:
            done(result)

    def wait(self, milliseconds=1000):
        self._closed = True
        self._pool.shutdown(wait=False, cancel_futures=False)
