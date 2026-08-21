import logging
import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
import ccxt.async_support as ccxt_async

logger = logging.getLogger("BinanceTestnetExecutorTurbo")

@dataclass
class LiveTurboPosition:
    id: str
    symbol: str
    side: str
    entry_price: float
    units: float
    stop_loss: float
    take_profit: float
    highest_price: float
    lowest_price: float
    profit_lock_stage: int
    opened_at: float
    notional_usd: float

class BinanceTestnetExecutorTurbo:
    def __init__(self, api_key: str, secret: str, leverage: int = 2):
        self.api_key = api_key
        self.secret = secret
        self.leverage = leverage
        self.exchange = ccxt_async.binanceusdm({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'timeout': 10000
        })
        self.exchange.set_sandbox_mode(True)
        self.positions: Dict[str, LiveTurboPosition] = {}
        self.trade_history: List[Dict] = []
        self.balance_usd: float = 4923.84
        self.initial_balance: float = 4923.84
        self._order_counter = 0

    async def initialize(self):
        try:
            await self.exchange.load_markets()
            bal = await self.exchange.fetch_balance()
            self.balance_usd = float(bal['total'].get('USDT', 4923.84))
            self.initial_balance = self.balance_usd
            logger.info(f"⚡ [TURBO BINANCE TESTNET CONECTADO] Balance Oficial: ${self.balance_usd:,.2f} USDT")
        except Exception as e:
            logger.error(f"Error inicializando Binance Testnet en TURBO: {e}")

    async def execute_signal(self, signal, units: float):
        if signal.action not in ["BUY", "SELL"] or units <= 0:
            return None

        market_symbol = f"{signal.symbol.split('/')[0]}/USDT:USDT"
        side = "buy" if signal.action == "BUY" else "sell"

        try:
            try:
                await self.exchange.set_leverage(self.leverage, market_symbol)
            except Exception:
                pass

            # Control estricto de margen seguro (máx $600 notional)
            max_safe_notional = min(600.0, self.balance_usd * (self.leverage * 0.15))
            if (units * signal.entry_price) > max_safe_notional:
                units = max_safe_notional / signal.entry_price

            amount_formatted = round(units, 0)
            if amount_formatted <= 0:
                return None

            order = await self.exchange.create_order(
                symbol=market_symbol,
                type='market',
                side=side,
                amount=amount_formatted
            )

            raw_p = order.get('average') or order.get('price') or signal.entry_price
            fill_price = float(raw_p) if raw_p else float(signal.entry_price)
            actual_units = float(amount_formatted)
            notional = fill_price * actual_units
            pos_id = f"binance_turbo_{order.get('id', self._order_counter)}"
            self._order_counter += 1

            pos = LiveTurboPosition(
                id=pos_id,
                symbol=signal.symbol,
                side="LONG" if signal.action == "BUY" else "SHORT",
                entry_price=fill_price,
                units=actual_units,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                highest_price=fill_price,
                lowest_price=fill_price,
                profit_lock_stage=0,
                opened_at=time.time(),
                notional_usd=notional
            )
            self.positions[signal.symbol] = pos
            logger.info(
                f"⚡ [ORDEN REAL BINANCE TURBO] {signal.action} {actual_units} {signal.symbol} @ ${fill_price:,.4f} | ID: {pos_id}"
            )
            return pos
        except Exception as e:
            logger.error(f"Error ejecutando orden en Binance Testnet para TURBO: {e}")
            return None

    def get_equity(self, current_prices: Dict[str, float]) -> float:
        unrealized = 0.0
        for sym, pos in self.positions.items():
            curr_p = current_prices.get(sym, pos.entry_price)
            if pos.side == "LONG":
                unrealized += (curr_p - pos.entry_price) * pos.units
            else:
                unrealized += (pos.entry_price - curr_p) * pos.units
        return self.balance_usd + unrealized

    async def update_and_check_exits(self, current_prices: Dict[str, float]):
        for symbol, pos in list(self.positions.items()):
            curr_p = current_prices.get(symbol, pos.entry_price)
            if not curr_p:
                continue

            should_close = False
            reason = ""

            if pos.side == "LONG":
                if curr_p <= pos.stop_loss:
                    should_close = True
                    reason = "STOP_LOSS"
                elif curr_p >= pos.take_profit:
                    should_close = True
                    reason = "TAKE_PROFIT"
            elif pos.side == "SHORT":
                if curr_p >= pos.stop_loss:
                    should_close = True
                    reason = "STOP_LOSS"
                elif curr_p <= pos.take_profit:
                    should_close = True
                    reason = "TAKE_PROFIT"

            if should_close:
                await self.close_position(symbol, exit_price=curr_p, reason=reason)

    async def close_position(self, symbol: str, exit_price: float, reason: str):
        pos = self.positions.get(symbol)
        if not pos:
            return

        market_symbol = f"{symbol.split('/')[0]}/USDT:USDT"
        close_side = "sell" if pos.side == "LONG" else "buy"

        try:
            order = await self.exchange.create_order(
                symbol=market_symbol,
                type='market',
                side=close_side,
                amount=pos.units,
                params={'reduceOnly': True}
            )
            raw_p = order.get('average') or order.get('price') or exit_price
            real_exit = float(raw_p) if raw_p else exit_price
            pnl = ((real_exit - pos.entry_price) * pos.units) if pos.side == "LONG" else ((pos.entry_price - real_exit) * pos.units)

            self.balance_usd += pnl
            closed_trade = {
                "id": pos.id,
                "symbol": symbol,
                "side": pos.side,
                "entry_price": pos.entry_price,
                "exit_price": real_exit,
                "units": pos.units,
                "net_pnl": pnl * 0.9992,
                "reason": reason,
                "opened_at": pos.opened_at,
                "closed_at": time.time()
            }
            self.trade_history.append(closed_trade)
            del self.positions[symbol]
            logger.info(f"🏆 [POSICIÓN CERRADA BINANCE TURBO] {symbol} | PnL: ${pnl:+,.2f} | Motivo: {reason}")
        except Exception as e:
            logger.error(f"Error cerrando posición en Binance Testnet para TURBO: {e}")

    async def close(self):
        if self.exchange:
            await self.exchange.close()
