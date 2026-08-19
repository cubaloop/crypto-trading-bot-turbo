import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from strategies.turbo_strategy import TradeSignal

logger = logging.getLogger("PaperExecutorTurbo")

@dataclass
class Position:
    id: str
    symbol: str
    side: str  # "LONG" o "SHORT"
    entry_price: float
    units: float
    stop_loss: float
    take_profit: float
    take_profit_2: float
    highest_price: float
    lowest_price: float
    opened_at: float
    notional_usd: float

class PaperExecutor:
    def __init__(
        self,
        initial_balance_usd: float = 10000.0,
        taker_fee_pct: float = 0.0004,
        slippage_bps: float = 2.0
    ):
        self.balance_usd = initial_balance_usd
        self.initial_balance = initial_balance_usd
        self.taker_fee_pct = taker_fee_pct
        self.slippage_bps = slippage_bps
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Dict] = []
        self._order_counter = 0

    def get_equity(self, current_prices: Dict[str, float]) -> float:
        unrealized_pnl = 0.0
        for symbol, pos in self.positions.items():
            curr_p = current_prices.get(symbol, pos.entry_price)
            if pos.side == "LONG":
                unrealized_pnl += (curr_p - pos.entry_price) * pos.units
            else:
                unrealized_pnl += (pos.entry_price - curr_p) * pos.units
        return self.balance_usd + unrealized_pnl

    def execute_signal(self, signal: TradeSignal, units: float) -> Optional[Position]:
        if signal.action not in ["BUY", "SELL"] or units <= 0:
            return None

        side = "LONG" if signal.action == "BUY" else "SHORT"
        slippage_mult = (1 + (self.slippage_bps / 10000.0)) if side == "LONG" else (1 - (self.slippage_bps / 10000.0))
        fill_price = signal.entry_price * slippage_mult
        notional = fill_price * units
        fee = notional * self.taker_fee_pct

        self.balance_usd -= fee
        self._order_counter += 1
        pos_id = f"turbo_{self._order_counter}_{int(time.time())}"

        pos = Position(
            id=pos_id,
            symbol=signal.symbol,
            side=side,
            entry_price=fill_price,
            units=units,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            take_profit_2=signal.take_profit_2,
            highest_price=fill_price,
            lowest_price=fill_price,
            opened_at=time.time(),
            notional_usd=notional
        )
        self.positions[signal.symbol] = pos
        logger.info(f"⚡ [TURBO EXECUTION] {side} {units:.4f} {signal.symbol} a ${fill_price:,.2f} | SL: ${pos.stop_loss:,.2f} | TP1: ${pos.take_profit:,.2f} | TP2: ${pos.take_profit_2:,.2f}")
        return pos

    def update_and_check_exits(self, current_prices: Dict[str, float]) -> List[Dict]:
        closed_trades = []
        symbols_to_close = []

        for symbol, pos in self.positions.items():
            curr_p = current_prices.get(symbol)
            if not curr_p:
                continue

            # Actualizar extremos de precio para Trailing Stop
            if curr_p > pos.highest_price:
                pos.highest_price = curr_p
            if curr_p < pos.lowest_price:
                pos.lowest_price = curr_p

            hit_tp = False
            hit_sl = False
            reason = "NONE"

            if pos.side == "LONG":
                # Trailing Stop Dinámico (Asegura ganancias si sube más del 0.6%)
                if (pos.highest_price - pos.entry_price) > (pos.entry_price * 0.006):
                    new_trailing_sl = pos.highest_price * 0.996
                    if new_trailing_sl > pos.stop_loss:
                        pos.stop_loss = new_trailing_sl

                if curr_p >= pos.take_profit_2 and pos.take_profit_2 > pos.entry_price:
                    hit_tp = True
                    reason = "TAKE_PROFIT_2 (MAX GAIN)"
                elif curr_p >= pos.take_profit and pos.take_profit > pos.entry_price:
                    hit_tp = True
                    reason = "TAKE_PROFIT_1 (SCALP)"
                elif curr_p <= pos.stop_loss:
                    hit_sl = True
                    reason = "TRAILING_STOP" if pos.stop_loss > pos.entry_price else "STOP_LOSS"

            elif pos.side == "SHORT":
                # Trailing Stop Dinámico para Short (Asegura ganancias si baja más del 0.6%)
                if (pos.entry_price - pos.lowest_price) > (pos.entry_price * 0.006):
                    new_trailing_sl = pos.lowest_price * 1.004
                    if new_trailing_sl < pos.stop_loss:
                        pos.stop_loss = new_trailing_sl

                if curr_p <= pos.take_profit_2 and pos.take_profit_2 < pos.entry_price:
                    hit_tp = True
                    reason = "TAKE_PROFIT_2 (MAX GAIN)"
                elif curr_p <= pos.take_profit and pos.take_profit < pos.entry_price:
                    hit_tp = True
                    reason = "TAKE_PROFIT_1 (SCALP)"
                elif curr_p >= pos.stop_loss:
                    hit_sl = True
                    reason = "TRAILING_STOP" if pos.stop_loss < pos.entry_price else "STOP_LOSS"

            if hit_tp or hit_sl:
                pnl = ((curr_p - pos.entry_price) * pos.units) if pos.side == "LONG" else ((pos.entry_price - curr_p) * pos.units)
                exit_fee = (curr_p * pos.units) * self.taker_fee_pct
                net_pnl = pnl - exit_fee

                # Corrección de etiqueta si el PnL neto es negativo
                if net_pnl < 0 and "TAKE_PROFIT" in reason:
                    reason = "STOP_LOSS"

                self.balance_usd += net_pnl
                closed_trade = {
                    "id": pos.id,
                    "symbol": symbol,
                    "side": pos.side,
                    "entry_price": pos.entry_price,
                    "exit_price": curr_p,
                    "units": pos.units,
                    "net_pnl": net_pnl,
                    "reason": reason,
                    "closed_at": time.time()
                }
                closed_trades.append(closed_trade)
                self.trade_history.append(closed_trade)
                symbols_to_close.append(symbol)
                
                emoji = "🎯 GANANCIA TURBO" if net_pnl > 0 else "🛑 PÉRDIDA TURBO"
                logger.info(f"{emoji} ({reason}): {symbol} PnL Neto: ${net_pnl:+.2f} | Saldo: ${self.balance_usd:,.2f}")

        for s in symbols_to_close:
            del self.positions[s]

        return closed_trades
