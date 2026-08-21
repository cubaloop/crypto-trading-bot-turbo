import logging
import time
from typing import Dict, Tuple

logger = logging.getLogger("RiskManagerTurbo")

class RiskManager:
    def __init__(
        self,
        initial_balance: float = 10000.0,
        risk_per_trade_pct: float = 0.02,  # 2% de riesgo por operación
        max_daily_drawdown_pct: float = 0.05,  # 5% circuit breaker
        max_open_positions: int = 3
    ):
        self.initial_balance = initial_balance
        self.current_equity = initial_balance
        self.risk_per_trade_pct = 0.08
        self.max_daily_drawdown_pct = max_daily_drawdown_pct
        self.max_open_positions = max_open_positions

        self.daily_high_equity = initial_balance
        self.last_day_reset = time.time()
        self.circuit_breaker_triggered_at = 0.0
        self.min_cooldown_seconds = 450.0  # 7.5 minutos de enfriamiento mínimo para Turbo Scalper
        self.is_circuit_breaker_active = False

    def update_equity(self, equity: float):
        self.current_equity = equity
        now = time.time()
        # Reset diario cada 24h
        if now - self.last_day_reset >= 86400:
            self.daily_high_equity = equity
            self.last_day_reset = now
            self.is_circuit_breaker_active = False
        else:
            if equity > self.daily_high_equity:
                self.daily_high_equity = equity

        # Verificar Circuit Breaker (5% max drawdown)
        if self.daily_high_equity > 0:
            current_drawdown = (self.daily_high_equity - equity) / self.daily_high_equity
            if current_drawdown >= self.max_daily_drawdown_pct:
                if not self.is_circuit_breaker_active:
                    logger.critical(f"🚨 CIRCUIT BREAKER TURBO DISPARADO: Drawdown diario {current_drawdown:.2%} superó el límite {self.max_daily_drawdown_pct:.2%}.")
                    self.is_circuit_breaker_active = True
                    self.circuit_breaker_triggered_at = now

    def reset_circuit_breaker(self):
        self.daily_high_equity = self.current_equity
        self.last_day_reset = time.time()
        self.is_circuit_breaker_active = False
        self.circuit_breaker_triggered_at = 0.0
        logger.info(f"⚡ CIRCUIT BREAKER TURBO REINICIADO | Base de Equity: ${self.current_equity:,.2f}")

    def check_auto_reactivation(self, signal_conviction: float = 0.0) -> Tuple[bool, str]:
        if not self.is_circuit_breaker_active:
            return True, "OK"

        now = time.time()
        elapsed = now - self.circuit_breaker_triggered_at

        # Cooldown de relajación
        if elapsed < self.min_cooldown_seconds:
            remaining_mins = max(1, int((self.min_cooldown_seconds - elapsed) / 60))
            return False, f"VIGILANCIA ADAPTATIVA (Enfriamiento: {remaining_mins}m restantes)"

        # Criterio Autónomo de Despertar Turbo: Alta convicción de ruptura (|conv| >= 0.60)
        if abs(signal_conviction) >= 0.60:
            self.reset_circuit_breaker()
            logger.info(f"⚡ [DESPERTAR AUTÓNOMO TURBO] Ruptura Squeeze de alta convicción detectada ({signal_conviction:+.2f}). Reanudando scalping.")
            return True, "AUTO_REACTIVADO_POR_MERCADO"

        return False, "VIGILANCIA INTELIGENTE (Escaneando ruptura Squeeze óptima)"

    def check_trade_allowed(self) -> Tuple[bool, str]:
        if self.is_circuit_breaker_active:
            return False, "Circuit Breaker Diario Turbo Activo (5% Max Drawdown)"
        return True, "OK"

    def compute_position_size(
        self,
        entry_price: float,
        stop_loss_price: float
    ) -> float:
        risk_amount_usd = self.current_equity * self.risk_per_trade_pct
        price_risk_per_unit = abs(entry_price - stop_loss_price)

        if price_risk_per_unit <= 0 or entry_price <= 0:
            return 0.0

        units = risk_amount_usd / price_risk_per_unit
        max_notional = self.current_equity * 2.0  # Apalancamiento máximo 2x
        if (units * entry_price) > max_notional:
            units = max_notional / entry_price

        return float(units)
