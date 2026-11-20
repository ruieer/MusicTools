"""Фоновый запуск функций движка.

- print() из движка уходит в лог окна (sys.stdout подменён на поток, который шлёт в очередь).
- input() из рабочего потока: сначала берутся заготовленные ответы (из форм на страницах),
  а если их нет - вопрос показывается в строке ответа окна, и поток ждёт.
- Остановка: если поток ждёт ответа, ему посылается сигнал; иначе в поток асинхронно
  бросается JobStopped. Он наследует BaseException, чтобы `except Exception`
  внутри скриптов его не проглатывал.
"""
import builtins
import ctypes
import queue
import sys
import threading
import traceback


class JobStopped(BaseException):
    pass


_STOP = object()


class _Stream:
    encoding = "utf-8"
    errors = "replace"

    def __init__(self, runner):
        self._runner = runner

    def write(self, text):
        if text:
            self._runner.events.put(("log", str(text)))
        return len(text or "")

    def flush(self):
        pass

    def isatty(self):
        return False


class Runner:
    def __init__(self):
        self.events = queue.Queue()     # в UI: (вид, данные); вид: log | ask | finish
        self._replies = queue.Queue()   # ответы пользователя из окна
        self._answers = []              # заготовленные ответы для input()
        self._thread = None
        self._waiting = False
        self._lock = threading.Lock()
        self._real_input = builtins.input
        builtins.input = self._input
        sys.stdout = _Stream(self)
        sys.stderr = _Stream(self)

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def waiting(self) -> bool:
        with self._lock:
            return self._waiting

    def start(self, fn, answers=()) -> bool:
        if self.busy:
            return False
        self._answers = list(answers)
        self._thread = threading.Thread(target=self._work, args=(fn,), daemon=True)
        self._thread.start()
        return True

    def answer(self, text: str) -> None:
        self._replies.put(text)

    def stop(self) -> None:
        if not self.busy:
            return
        with self._lock:
            if self._waiting:
                self._replies.put(_STOP)
                return
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(self._thread.ident), ctypes.py_object(JobStopped))

    # --- внутреннее ---------------------------------------------------------

    def _work(self, fn):
        status = "done"
        try:
            fn()
        except JobStopped:
            status = "stopped"
        except BaseException:
            self.events.put(("log", traceback.format_exc()))
            status = "error"
        finally:
            self._answers = []
            self.events.put(("finish", status))

    def _input(self, prompt=""):
        if threading.current_thread() is not self._thread:
            return self._real_input(prompt)
        if self._answers:
            return self._answers.pop(0)
        if prompt:
            self.events.put(("log", prompt))
        with self._lock:
            self._waiting = True
        self.events.put(("ask", prompt))
        value = self._replies.get()
        with self._lock:
            self._waiting = False
        if value is _STOP:
            raise JobStopped()
        self.events.put(("log", value + "\n"))
        return value
