import logging
import time
import numpy as np
from typing import List, Dict, Tuple

logger = logging.getLogger("TurboMetaLearner")

class TurboMetaCognitiveLearner:
    """
    Motor de Inteligencia Artificial Meta-Cognitiva y Auto-Corrección para TURBO (Ultra-Fast Scalper).
    
    Optimiza el ratio de scalping, previene sobre-operar (Overtrading Protection)
    y ajusta el filtro de momentum para acelerar en expansión y protegerse en choppiness.
    """
    def __init__(self):
        self.w_momentum: float = 0.40
        self.w_trend: float = 0.35
        self.w_volume: float = 0.25
        
        self.dynamic_threshold: float = 0.30
        self.consecutive_losses: int = 0
        self.last_reflection_message: str = "🧠 [IA TURBO]: Scalper meta-cognitivo activo."

    def evaluate_performance_and_adapt(self, trade_history: List[Dict], current_market_trend_bullish: bool = True) -> Tuple[Dict[str, float], float, str]:
        if not trade_history:
            return self._get_weights(), self.dynamic_threshold, self.last_reflection_message

        recent = trade_history[-6:]
        consec_losses = 0
        for t in reversed(trade_history):
            if t.get('net_pnl', 0.0) < 0:
                consec_losses += 1
            else:
                break
        self.consecutive_losses = consec_losses

        if consec_losses >= 2:
            self.dynamic_threshold = min(0.45, 0.30 + (0.05 * consec_losses))
            self.w_trend = 0.50
            self.w_momentum = 0.30
            self.w_volume = 0.20
            msg = f"🛡️ [IA TURBO SCALP DEFENSE]: Racha de {consec_losses} pérdidas. Elevando umbral a {self.dynamic_threshold:.2f}."
        else:
            self.dynamic_threshold = 0.30
            self.w_momentum = 0.40
            self.w_trend = 0.35
            self.w_volume = 0.25
            msg = "⚡ [IA TURBO FAST SCALP]: Agilidad óptima para micro-movimientos."

        self.last_reflection_message = msg
        return self._get_weights(), self.dynamic_threshold, msg

    def _get_weights(self) -> Dict[str, float]:
        total = self.w_momentum + self.w_trend + self.w_volume
        return {
            "w_momentum": self.w_momentum / total,
            "w_trend": self.w_trend / total,
            "w_volume": self.w_volume / total
        }
