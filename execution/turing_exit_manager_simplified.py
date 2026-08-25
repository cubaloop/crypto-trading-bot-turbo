"""
turing_exit_manager_simplified.py — Exit Manager ultra-sensible para TURBO
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

@dataclass
class SimplifiedExitParams:
    stage1_atr_mult: float = 0.8
    stage2_atr_mult: float = 1.4
    stage2_lock_pct: float = 0.80
    tp_atr_mult: float = 1.80
    fee_buffer_pct: float = 0.0008
    time_decay_window_minutes: float = 20.0  # Ultra rápido (20 min)

SYMBOL_EXIT_PARAMS: Dict[str, SimplifiedExitParams] = {
    "DOGE/USDT": SimplifiedExitParams(time_decay_window_minutes=20.0),
    "DOGEUSDT": SimplifiedExitParams(time_decay_window_minutes=20.0),
}
DEFAULT_EXIT_PARAMS = SimplifiedExitParams()

@dataclass
class SimplifiedPosition:
    direction: int
    entry_price: float
    highest_price: float
    lowest_price: float
    atr: float
    stop_loss: float
    take_profit: float
    profit_lock_stage: int = 0
    opened_at_bar: int = 0
    force_close: bool = False
    force_close_reason: str = ""

def init_simplified_position(direction: int, entry_price: float, atr: float,
                               params: SimplifiedExitParams) -> SimplifiedPosition:
    tp = entry_price + direction * (params.tp_atr_mult * atr)
    sl_initial = entry_price - direction * (params.stage2_atr_mult * atr)
    return SimplifiedPosition(direction=direction, entry_price=entry_price,
                                highest_price=entry_price, lowest_price=entry_price,
                                atr=atr, stop_loss=sl_initial, take_profit=tp)

_FLOAT_EPS = 1e-9

def update_simplified_exit(pos: SimplifiedPosition, market_price: float,
                             params: SimplifiedExitParams) -> SimplifiedPosition:
    if pos.direction == 1:
        pos.highest_price = max(pos.highest_price, market_price)
        peak_gain_atr = (pos.highest_price - pos.entry_price) / pos.atr if pos.atr > 0 else 0.0
    else:
        pos.lowest_price = min(pos.lowest_price, market_price)
        peak_gain_atr = (pos.entry_price - pos.lowest_price) / pos.atr if pos.atr > 0 else 0.0

    def tighten(new_sl: float) -> bool:
        if pos.direction == 1:
            if new_sl > pos.stop_loss:
                pos.stop_loss = new_sl
                return True
        else:
            if new_sl < pos.stop_loss:
                pos.stop_loss = new_sl
                return True
        return False

    if peak_gain_atr >= params.stage1_atr_mult - _FLOAT_EPS and pos.profit_lock_stage < 1:
        be_price = pos.entry_price + pos.direction * (pos.entry_price * params.fee_buffer_pct)
        if tighten(be_price):
            pos.profit_lock_stage = 1

    if peak_gain_atr >= params.stage2_atr_mult - _FLOAT_EPS and pos.profit_lock_stage < 2:
        if pos.direction == 1:
            lock_price = pos.entry_price + params.stage2_lock_pct * (pos.highest_price - pos.entry_price)
        else:
            lock_price = pos.entry_price - params.stage2_lock_pct * (pos.entry_price - pos.lowest_price)
        if tighten(lock_price):
            pos.profit_lock_stage = 2

    return pos

def check_time_decay(pos: SimplifiedPosition, current_price: float, minutes_since_open: float,
                       params: SimplifiedExitParams) -> bool:
    if minutes_since_open < params.time_decay_window_minutes:
        return False
    pnl = (current_price - pos.entry_price) * pos.direction
    return pnl <= 0

def check_exit_trigger(pos: SimplifiedPosition, high: float, low: float) -> Tuple[Optional[float], str]:
    if pos.direction == 1:
        if low <= pos.stop_loss:
            return pos.stop_loss, "STOP_LOSS" if pos.profit_lock_stage == 0 else "PROFIT_LOCK_STOP"
        if high >= pos.take_profit:
            return pos.take_profit, "TAKE_PROFIT"
    else:
        if high >= pos.stop_loss:
            return pos.stop_loss, "STOP_LOSS" if pos.profit_lock_stage == 0 else "PROFIT_LOCK_STOP"
        if low <= pos.take_profit:
            return pos.take_profit, "TAKE_PROFIT"
    return None, ""
