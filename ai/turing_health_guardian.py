"""
TURING — Guardianes de salud en vivo (Arquitectura Claude)
=========================================================
"""
import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger("turing.health")

@dataclass
class HealthAlert:
    bot_id: str
    category: str      # "EVENT_LOOP_BLOCKED" | "FEED_MISMATCH" | "EXECUTION_GAP" | "SILENT_EXCEPTION"
    severity: str        # "WARNING" | "CRITICAL"
    message: str
    timestamp: float = field(default_factory=time.time)

class HeartbeatMonitor:
    def __init__(self, bot_id: str, expected_interval_s: float = 1.0,
                 warn_lag_s: float = 0.5, critical_lag_s: float = 3.0):
        self.bot_id = bot_id
        self.expected_interval_s = expected_interval_s
        self.warn_lag_s = warn_lag_s
        self.critical_lag_s = critical_lag_s
        self._running = False

    async def run(self, alert_sink: Callable[[HealthAlert], None]):
        self._running = True
        last_tick = time.monotonic()
        while self._running:
            await asyncio.sleep(self.expected_interval_s)
            now = time.monotonic()
            lag = (now - last_tick) - self.expected_interval_s
            last_tick = now
            if lag >= self.critical_lag_s:
                alert_sink(HealthAlert(
                    self.bot_id, "EVENT_LOOP_BLOCKED", "CRITICAL",
                    f"Event loop bloqueado {lag:.2f}s por encima de lo esperado — "
                    f"probable llamada síncrona bloqueante (ej. ccxt sin async_support).",
                ))
            elif lag >= self.warn_lag_s:
                alert_sink(HealthAlert(
                    self.bot_id, "EVENT_LOOP_BLOCKED", "WARNING",
                    f"Lag de {lag:.2f}s detectado en el event loop.",
                ))

    def stop(self):
        self._running = False

class FeedConsistencyChecker:
    def __init__(self, bot_id: str, feed_exchange: str, execution_exchange: str):
        self.bot_id = bot_id
        self.feed_exchange = feed_exchange
        self.execution_exchange = execution_exchange

    def check_static_config(self) -> Optional[HealthAlert]:
        if self.feed_exchange.lower() != self.execution_exchange.lower():
            return HealthAlert(
                self.bot_id, "FEED_MISMATCH", "CRITICAL",
                f"El feed de datos apunta a '{self.feed_exchange}' pero la ejecución "
                f"de órdenes está en '{self.execution_exchange}'.",
            )
        return None

    def check_price_divergence(self, feed_last_price: float, execution_ref_price: float,
                                 max_divergence_pct: float = 0.5) -> Optional[HealthAlert]:
        if execution_ref_price <= 0:
            return None
        divergence_pct = abs(feed_last_price - execution_ref_price) / execution_ref_price * 100
        if divergence_pct > max_divergence_pct:
            return HealthAlert(
                self.bot_id, "FEED_MISMATCH", "CRITICAL",
                f"Precio del feed ({feed_last_price}) diverge {divergence_pct:.2f}% del "
                f"precio real de {self.execution_exchange} ({execution_ref_price}).",
            )
        return None

class SignalExecutionTracker:
    def __init__(self, bot_id: str, window_size: int = 50,
                 min_execution_ratio: float = 0.5, min_signals_for_check: int = 5):
        self.bot_id = bot_id
        self.min_execution_ratio = min_execution_ratio
        self.min_signals_for_check = min_signals_for_check
        self._events: deque = deque(maxlen=window_size)

    def record_signal(self, executed: bool) -> None:
        self._events.append(executed)

    def check(self) -> Optional[HealthAlert]:
        n = len(self._events)
        if n < self.min_signals_for_check:
            return None
        executed = sum(1 for e in self._events if e)
        ratio = executed / n
        if ratio < self.min_execution_ratio:
            return HealthAlert(
                self.bot_id, "EXECUTION_GAP", "CRITICAL",
                f"Solo {executed}/{n} señales accionables se ejecutaron ({ratio*100:.0f}%) — "
                f"por debajo del {self.min_execution_ratio*100:.0f}% esperado.",
            )
        return None

class SilentFailureGuard:
    def __init__(self, bot_id: str, name: str, max_consecutive_failures: int = 3):
        self.bot_id = bot_id
        self.name = name
        self.max_consecutive_failures = max_consecutive_failures
        self._consecutive_failures = 0

    async def call(self, coro_fn: Callable[..., Awaitable[Any]],
                    alert_sink: Callable[[HealthAlert], None],
                    *args, default: Any = None, **kwargs) -> Any:
        try:
            result = await coro_fn(*args, **kwargs)
            self._consecutive_failures = 0
            return result
        except Exception as e:
            self._consecutive_failures += 1
            logger.warning(
                f"[{self.bot_id}] {self.name} falló ({self._consecutive_failures} "
                f"consecutivas): {type(e).__name__}: {e}"
            )
            if self._consecutive_failures >= self.max_consecutive_failures:
                alert_sink(HealthAlert(
                    self.bot_id, "SILENT_EXCEPTION", "CRITICAL",
                    f"'{self.name}' falló {self._consecutive_failures} veces consecutivas ({type(e).__name__}: {e}).",
                ))
            return default

class SystemHealthMonitor:
    def __init__(self):
        self.alerts: List[HealthAlert] = []
        self._on_critical: List[Callable[[HealthAlert], None]] = []

    def sink(self, alert: HealthAlert) -> None:
        self.alerts.append(alert)
        level = logging.ERROR if alert.severity == "CRITICAL" else logging.WARNING
        logger.log(level, f"[{alert.bot_id}] {alert.category}: {alert.message}")
        if alert.severity == "CRITICAL":
            for cb in self._on_critical:
                try:
                    cb(alert)
                except Exception:
                    pass

    def on_critical(self, callback: Callable[[HealthAlert], None]) -> None:
        self._on_critical.append(callback)

    def is_healthy(self, bot_id: str, lookback_s: float = 300.0) -> bool:
        now = time.time()
        recent_critical = [
            a for a in self.alerts
            if a.bot_id == bot_id and a.severity == "CRITICAL" and (now - a.timestamp) <= lookback_s
        ]
        return len(recent_critical) == 0
