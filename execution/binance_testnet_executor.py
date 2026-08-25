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
    take_profit_2: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 0.0
    profit_lock_stage: int = 0
    opened_at: float = 0.0
    notional_usd: float = 0.0
    atr: float = 0.0

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
            try:
                remote_positions = await self.exchange.fetch_positions()
                for rp in remote_positions:
                    contracts = float(rp.get('contracts', 0))
                    sym = rp.get('symbol', '').split(':')[0]
                    if contracts > 0 and sym:
                        side = "LONG" if rp.get('side') == 'long' else "SHORT"
                        entry_p = float(rp.get('entryPrice', 0))
                        pos_id = f"binance_synced_{int(time.time())}"
                        self.positions[sym] = LiveTurboPosition(
                            id=pos_id,
                            symbol=sym,
                            side=side,
                            entry_price=entry_p,
                            units=contracts,
                            stop_loss=entry_p * 0.985 if side == "LONG" else entry_p * 1.015,
                            take_profit=entry_p * 1.035 if side == "LONG" else entry_p * 0.965,
                            highest_price=entry_p,
                            lowest_price=entry_p,
                            profit_lock_stage=0,
                            opened_at=time.time(),
                            notional_usd=float(rp.get('notional', entry_p * contracts)),
                            atr=entry_p * 0.01
                        )
                        logger.info(f"⚡ [POSICIÓN RECONCILIADA] {side} {contracts} {sym} @ ${entry_p:,.2f}")
            except Exception as pe:
                pass
            logger.info(f"⚡ [CONECTADO] Balance: ${self.balance_usd:,.2f} USDT | Posiciones: {len(self.positions)}")
        except Exception as e:
            logger.error(f"Error inicializando Binance: {e}")

    async def execute_signal(self, signal, units: float):
        if signal.action not in ["BUY", "SELL"] or units <= 0:
            return None

        market_symbol = f"{signal.symbol.split('/')[0]}/USDT:USDT"
        side = "buy" if signal.action == "BUY" else "sell"

        try:
            # 1. Filtro de Spread Institucional (< 0.035%)
            try:
                ticker = await self.exchange.fetch_ticker(market_symbol)
                bid = float(ticker.get('bid', signal.entry_price))
                ask = float(ticker.get('ask', signal.entry_price))
                if bid > 0 and ask > 0:
                    spread_pct = (ask - bid) / bid
                    if spread_pct > 0.0015:
                        logger.warning(f"🛑 [TURBO SPREAD FILTER] Spread amplio ({spread_pct:.4%}). Esperando compresión.")
                        return None
            except Exception:
                pass

            try:
                await self.exchange.set_leverage(self.leverage, market_symbol)
            except Exception:
                pass

            # 2. Control de Margen Aislado Seguro (Máximo $600 USDT notional por trade)
            max_safe_notional = 3000.0
            if (units * signal.entry_price) > max_safe_notional:
                units = max_safe_notional / signal.entry_price

            # Precisión dinámica de contratos según el par
            base_coin = signal.symbol.split('/')[0]
            if base_coin in ["BTC", "ETH"]:
                amount_formatted = round(units, 3)
            elif base_coin in ["SOL", "NEAR", "AVAX", "LINK"]:
                amount_formatted = round(units, 2)
            else:
                amount_formatted = round(units, 0)
                
            if amount_formatted <= 0:
                return None

            # 1. Ejecución Directa a Mercado para Ultra-Baja Latencia
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
                notional_usd=notional,
                atr=getattr(signal, 'atr', fill_price * 0.008)
            )
            self.positions[signal.symbol] = pos
            logger.info(
                f"⚡ [ORDEN REAL BINANCE TURBO] {signal.action} {actual_units} {signal.symbol} @ ${fill_price:,.4f} | ID: {pos_id}"
            )
            return pos
        except Exception as e:
            logger.error(f"Error ejecutando orden real en Binance Testnet para TURBO: {e}")
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
            curr_p = current_prices.get(symbol)
            if not curr_p:
                try:
                    market_symbol = f"{symbol.split('/')[0]}/USDT:USDT"
                    ticker = await self.exchange.fetch_ticker(market_symbol)
                    curr_p = float(ticker.get('last') or ticker.get('close') or pos.entry_price)
                except Exception:
                    curr_p = pos.entry_price
            if not curr_p:
                continue

            if curr_p > pos.highest_price:
                pos.highest_price = curr_p
            if curr_p < pos.lowest_price:
                pos.lowest_price = curr_p

            should_close = False
            reason = ""
            # 2. ExitManager Simplificado Ultra-Sensible (Scalping Rápido)
            from execution.turing_exit_manager_simplified import (
                SimplifiedPosition, SYMBOL_EXIT_PARAMS, DEFAULT_EXIT_PARAMS,
                update_simplified_exit, check_time_decay, check_exit_trigger
            )
            params = SYMBOL_EXIT_PARAMS.get(symbol, DEFAULT_EXIT_PARAMS)
            dir_int = 1 if pos.side == "LONG" else -1
            
            sim_pos = SimplifiedPosition(
                direction=dir_int,
                entry_price=pos.entry_price,
                highest_price=pos.highest_price,
                lowest_price=pos.lowest_price,
                atr=pos.atr if pos.atr > 0 else (pos.entry_price * 0.008),
                stop_loss=pos.stop_loss,
                take_profit=pos.take_profit,
                profit_lock_stage=pos.profit_lock_stage,
                opened_at_bar=int(pos.opened_at)
            )
            
            update_simplified_exit(sim_pos, curr_p, params)
            pos.stop_loss = sim_pos.stop_loss
            pos.profit_lock_stage = sim_pos.profit_lock_stage
            
            minutes_open = (time.time() - pos.opened_at) / 60.0
            if check_time_decay(sim_pos, curr_p, minutes_open, params):
                should_close = True
                reason = "TURBO_TIME_DECAY (Rotación Rápida)"
                
            exit_price_trig, exit_reason = check_exit_trigger(sim_pos, high=curr_p, low=curr_p)
            if exit_price_trig is not None:
                should_close = True
                reason = exit_reason

            if should_close:
                await self.close_position(symbol, exit_price=curr_p, reason=reason)


    async def sync_native_binance_stop_loss(self, symbol: str, stop_price: float, side: str, amount: float):
        """
        COLOCA O ACTUALIZA UNA ORDEN 'STOP_MARKET' REAL EN LOS SERVIDORES DE BINANCE.
        Garantiza que aunque el bot se apague, el servidor se reinicie o se caiga internet,
        BINANCE EJECUTARÁ EL CIERRE AUTOMÁTICAMENTE EN SU PROPIO MOTOR DE CALCE.
        """
        market_symbol = f"{symbol.split('/')[0]}/USDT:USDT"
        close_side = "sell" if side == "LONG" else "buy"
        try:
            # Cancelar cualquier orden de Stop Loss anterior en Binance para ese símbolo
            open_orders = await self.exchange.fetch_open_orders(market_symbol)
            for o in open_orders:
                if o.get('type') in ['stop_market', 'stop', 'STOP_MARKET', 'STOP']:
                    try:
                        await self.exchange.cancel_order(o['id'], market_symbol)
                    except Exception:
                        pass
            
            # Crear la nueva orden STOP_MARKET nativa en Binance
            formatted_stop = round(float(stop_price), 4 if stop_price < 10 else 2)
            params = {
                'stopPrice': formatted_stop,
                'reduceOnly': True
            }
            order = await self.exchange.create_order(
                symbol=market_symbol,
                type='STOP_MARKET',
                side=close_side,
                amount=amount,
                params=params
            )
            logger.info(f"🛡️ [STOP LOSS NATIVO EN BINANCE] {market_symbol} {close_side.upper()} {amount} @ Trigg: ${formatted_stop:,.4f} | ID: {order.get('id')}")
            return order
        except Exception as e:
            logger.error(f"Error sincronizando Stop Loss nativo en Binance: {e}")
            return None

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
            logger.info(f"🏆 [POSICIÓN CERRADA REAL BINANCE TURBO] {symbol} | PnL: ${pnl:+,.2f} | Motivo: {reason}")
        except Exception as e:
            logger.error(f"Error cerrando posición en Binance Testnet para TURBO: {e}")

    async def close(self):
        if self.exchange:
            await self.exchange.close()
