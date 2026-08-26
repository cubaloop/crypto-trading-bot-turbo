import asyncio
import logging
import os
import signal
import sys
import time
from typing import Dict, List, Optional
import ccxt.async_support as ccxt_async
import numpy as np

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("KuQuantTurboLeveraged")

class TurboLeveragedEngine:
    def __init__(self):
        # Credenciales directas de Binance Testnet
        self.api_key = os.getenv("BINANCE_TESTNET_API_KEY", "LyS7ZwuG771PRgZSD7T2AoidqJ8FIGnHUrOElsphYMTZg7BQtgkvt8PTEO95zFXX")
        self.api_secret = os.getenv("BINANCE_TESTNET_API_SECRET", "EVWlkCZIJAYRe8bgw7Xu7hRamRqjyWxgEms0zzKTPkHwKTU0ALJxUKSJwUhb7gy6")
        
        self.exchange = ccxt_async.binanceusdm({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        self.exchange.set_sandbox_mode(True)
        self.data_feed = ccxt_async.bybit({'enableRateLimit': True, 'timeout': 5000})
        
        self.symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT", "NEAR/USDT"]
        self.positions: Dict[str, Dict] = {}
        self.price_history: Dict[str, List[float]] = {s: [] for s in self.symbols}
        self.is_running = False
        self.iteration = 0
        
        # Apalancamiento 10x y Nocional Fuerte ($4,000 - $6,000 USD de poder de compra)
        self.leverage = 10
        self.base_notional = 4500.0  # $4,500 USD de exposición apalancada
        self.consecutive_wins = 0
        self.consecutive_losses = 0

    async def initialize(self):
        logger.info(f"🔥 Inicializando TURBO con Apalancamiento {self.leverage}x y Breakeven al 1.00%...")
        try:
            await self.data_feed.load_markets()
            # Configurar apalancamiento 10x en Binance Futures
            for s in self.symbols:
                market_sym = f"{s.split('/')[0]}/USDT:USDT"
                try:
                    await self.exchange.set_leverage(self.leverage, market_sym)
                except Exception:
                    pass
            balance = await self.exchange.fetch_balance()
            usdt_free = float(balance.get('USDT', {}).get('free', 5000.0) or 5000.0)
            logger.info(f"💰 Balance Libre en Binance Testnet: ${usdt_free:,.2f} USDT | Poder de Compra (10x): ${usdt_free*self.leverage:,.2f} USD")
        except Exception as e:
            logger.warning(f"Aviso en inicialización: {e}")

    def compute_dynamic_notional(self) -> float:
        if self.consecutive_wins >= 2:
            return min(6500.0, self.base_notional + (self.consecutive_wins * 600.0))
        elif self.consecutive_losses >= 2:
            return max(2500.0, self.base_notional - (self.consecutive_losses * 500.0))
        return self.base_notional

    def get_contract_amount(self, symbol: str, notional_usd: float, price: float) -> float:
        base = symbol.split('/')[0]
        raw_units = notional_usd / price
        if base in ["BTC", "ETH"]:
            return round(raw_units, 3)
        elif base in ["SOL", "NEAR", "AVAX", "LINK"]:
            return round(raw_units, 2)
        else:
            return round(raw_units, 0)

    async def execute_open(self, symbol: str, side: str, price: float, reason: str):
        market_symbol = f"{symbol.split('/')[0]}/USDT:USDT"
        notional_target = self.compute_dynamic_notional()
        amount = self.get_contract_amount(symbol, notional_target, price)
        
        if amount <= 0:
            return

        order_side = "buy" if side == "LONG" else "sell"
        logger.info(f"⚡ [TURBO APALANCADO 10x] {side} {amount} {symbol} (${notional_target:.0f} USD Nocional) @ ${price:,.4f} | Razón: {reason}")
        
        try:
            order = await self.exchange.create_order(
                symbol=market_symbol,
                type='market',
                side=order_side,
                amount=amount
            )
            fill_price = float(order.get('average') or order.get('price') or price)
            
            # Objetivos de Ganancia Fuerte ($50 - $180 USD con 10x):
            # TP Runner al +3.50% (+35% ROE) y SL al -1.20% (-12% ROE)
            tp_mult = 0.0350
            sl_mult = 0.0120

            if side == "LONG":
                sl = fill_price * (1.0 - sl_mult)
                tp = fill_price * (1.0 + tp_mult)
            else:
                sl = fill_price * (1.0 + sl_mult)
                tp = fill_price * (1.0 - tp_mult)

            self.positions[symbol] = {
                "id": order.get('id', str(time.time())),
                "symbol": symbol,
                "market_symbol": market_symbol,
                "side": side,
                "units": amount,
                "entry_price": fill_price,
                "stop_loss": sl,
                "take_profit": tp,
                "peak_price": fill_price,
                "opened_at": time.time()
            }
            logger.info(f"✅ [TURBO 10x CONFIRMADO] {side} {amount} {symbol} @ ${fill_price:,.4f} | TP Runner: ${tp:,.4f} | SL: ${sl:,.4f}")
        except Exception as e:
            logger.error(f"❌ Error ejecutando apertura en Binance: {e}")

    async def execute_close(self, symbol: str, current_price: float, reason: str):
        pos = self.positions.get(symbol)
        if not pos:
            return

        market_symbol = pos["market_symbol"]
        close_side = "sell" if pos["side"] == "LONG" else "buy"
        amount = pos["units"]

        logger.info(f"🎯 [TURBO CIERRE] Liquidando {pos['side']} {amount} {symbol} @ ${current_price:,.4f} | Razón: {reason}")
        try:
            await self.exchange.create_order(
                symbol=market_symbol,
                type='market',
                side=close_side,
                amount=amount,
                params={'reduceOnly': True}
            )
            pnl = (current_price - pos['entry_price']) * amount if pos['side'] == "LONG" else (pos['entry_price'] - current_price) * amount
            
            if pnl > 5.0:
                self.consecutive_wins += 1
                self.consecutive_losses = 0
                logger.info(f"🏆 [TURBO GANANCIA GRANDE] {symbol} PnL: ${pnl:+.2f} USDT | Racha Victorias: {self.consecutive_wins}")
            elif pnl < -5.0:
                self.consecutive_losses += 1
                self.consecutive_wins = 0
                logger.info(f"⚠️ [TURBO PÉRDIDA CONTROLADA] {symbol} PnL: ${pnl:+.2f} USDT | Racha Pérdidas: {self.consecutive_losses}")
            else:
                logger.info(f"⚖️ [TURBO BREAKEVEN] {symbol} PnL: ${pnl:+.2f} USDT")

            del self.positions[symbol]
        except Exception as e:
            logger.error(f"❌ Error cerrando posición en Binance: {e}")

    async def run(self):
        self.is_running = True
        await self.initialize()

        logger.info("🟢 Bucle TURBO 10x (Breakeven al 1.00% + Runner $50-$180 USD) Iniciado.")
        
        while self.is_running:
            self.iteration += 1
            
            for symbol in self.symbols:
                try:
                    ticker = await self.data_feed.fetch_ticker(symbol)
                    current_price = float(ticker.get('last') or ticker.get('close') or 0.0)
                    
                    if current_price <= 0:
                        continue

                    history = self.price_history[symbol]
                    history.append(current_price)
                    if len(history) > 30:
                        self.price_history[symbol] = history[-30:]

                    # Salidas en RAM: Breakeven a partir de 1.00% exacto
                    if symbol in self.positions:
                        pos = self.positions[symbol]
                        entry_p = pos["entry_price"]
                        side = pos["side"]
                        sl = pos["stop_loss"]
                        tp = pos["take_profit"]

                        if side == "LONG":
                            if current_price > pos["peak_price"]:
                                pos["peak_price"] = current_price
                            pnl_pct = (current_price - entry_p) / entry_p

                            # 1. BREAKEVEN AL 1.00% EXACTO A FAVOR (Asegura Entrada + 0.30% ganancia neta)
                            if pnl_pct >= 0.0100 and sl < entry_p * 1.0030:
                                pos["stop_loss"] = entry_p * 1.0030
                                logger.info(f"🛡️ [BREAKEVEN 1.0% ACTIVADO] {symbol} LONG asegurado a ${pos['stop_loss']:,.4f} (+0.30% neto)")

                            # 2. TRAILING STOP AMPLIO (a partir de 1.80% persigue a 0.60% del pico)
                            if pnl_pct >= 0.0180:
                                new_trailing = pos["peak_price"] * 0.9940
                                if new_trailing > pos["stop_loss"]:
                                    pos["stop_loss"] = new_trailing
                                    logger.info(f"📈 [TURBO TRAILING] {symbol} SL elevado a ${new_trailing:,.4f}")

                        else:  # SHORT
                            if current_price < pos["peak_price"]:
                                pos["peak_price"] = current_price
                            pnl_pct = (entry_p - current_price) / entry_p

                            # 1. BREAKEVEN AL 1.00% EXACTO A FAVOR
                            if pnl_pct >= 0.0100 and sl > entry_p * 0.9970:
                                pos["stop_loss"] = entry_p * 0.9970
                                logger.info(f"🛡️ [BREAKEVEN 1.0% ACTIVADO] {symbol} SHORT asegurado a ${pos['stop_loss']:,.4f} (+0.30% neto)")

                            # 2. TRAILING STOP AMPLIO
                            if pnl_pct >= 0.0180:
                                new_trailing = pos["peak_price"] * 1.0060
                                if new_trailing < pos["stop_loss"]:
                                    pos["stop_loss"] = new_trailing
                                    logger.info(f"📈 [TURBO TRAILING] {symbol} SL bajado a ${new_trailing:,.4f}")

                        # Cierre por TP Final Runner o Trailing Stop
                        if (side == "LONG" and current_price >= tp) or (side == "SHORT" and current_price <= tp):
                            await self.execute_close(symbol, current_price, "TAKE_PROFIT_RUNNER_ALCANZADO (+3.50%)")
                        elif (side == "LONG" and current_price <= pos["stop_loss"]) or (side == "SHORT" and current_price >= pos["stop_loss"]):
                            is_trailing = (pos["stop_loss"] > entry_p) if side == "LONG" else (pos["stop_loss"] < entry_p)
                            reason = "TRAILING_STOP_EJECUTADO" if is_trailing else "STOP_LOSS_ACTIVADO"
                            await self.execute_close(symbol, current_price, reason)

                    # Entrada: Momentum + OBI con confirmación de volumen
                    elif len(self.positions) < 2 and len(history) >= 4:
                        recent_change = (current_price - history[-4]) / history[-4]
                        bid_vol = float(ticker.get('bidVolume', 0.0) or 0.0)
                        ask_vol = float(ticker.get('askVolume', 0.0) or 0.0)
                        total_vol = bid_vol + ask_vol
                        obi = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0.0
                        
                        if recent_change > 0.0003 and obi >= -0.35:
                            await self.execute_open(symbol, "LONG", current_price, f"Impulso Alcista (+{recent_change:.3%} | OBI: {obi:+.2f})")
                        elif recent_change < -0.0003 and obi <= 0.35:
                            await self.execute_open(symbol, "SHORT", current_price, f"Impulso Bajista ({recent_change:.3%} | OBI: {obi:+.2f})")

                except Exception as e:
                    logger.debug(f"Error procesando {symbol}: {e}")

            if self.iteration % 15 == 0:
                logger.info(f"📊 [TURBO 10x EN VIVO #{self.iteration}] Posiciones Activas: {len(self.positions)}")

            await asyncio.sleep(1.0)

    async def close(self):
        self.is_running = False
        await self.exchange.close()
        await self.data_feed.close()

if __name__ == "__main__":
    bot = TurboLeveragedEngine()
    try:
        asyncio.run(bot.run())
    except (KeyboardInterrupt, SystemExit):
        pass
