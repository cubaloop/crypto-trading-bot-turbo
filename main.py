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
logger = logging.getLogger("KuQuantTurboInstitutional")

class TurboInstitutionalEngine:
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
        
        # Universo de pares activos
        self.symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT", "NEAR/USDT"]
        self.positions: Dict[str, Dict] = {}
        self.price_history: Dict[str, List[float]] = {s: [] for s in self.symbols}
        self.is_running = False
        self.iteration = 0
        
        # Asignación Fuerte y Escalado Kelly en RAM
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.base_notional = 2200.0  # Asignación base fuerte de $2,200 USD

    async def initialize(self):
        logger.info("🔥 Inicializando KuQuant TURBO (Margen Holgado Institucional: TP1 + Runner)...")
        try:
            await self.data_feed.load_markets()
            balance = await self.exchange.fetch_balance()
            usdt_free = float(balance.get('USDT', {}).get('free', 5000.0) or 5000.0)
            logger.info(f"💰 Balance Libre en Binance Testnet: ${usdt_free:,.2f} USDT")
        except Exception as e:
            logger.warning(f"Aviso en inicialización: {e}")

    def compute_dynamic_notional(self) -> float:
        if self.consecutive_wins >= 2:
            return min(3200.0, self.base_notional + (self.consecutive_wins * 350.0))
        elif self.consecutive_losses >= 2:
            return max(1200.0, self.base_notional - (self.consecutive_losses * 400.0))
        return self.base_notional

    def detect_volatility_regime(self, history: List[float]) -> str:
        if len(history) < 10:
            return "NORMAL"
        std_pct = float(np.std(history[-15:]) / np.mean(history[-15:]))
        if std_pct >= 0.0012:
            return "EXPLOSION"
        elif std_pct <= 0.0003:
            return "RANGO"
        return "NORMAL"

    def get_contract_amount(self, symbol: str, notional_usd: float, price: float) -> float:
        base = symbol.split('/')[0]
        raw_units = notional_usd / price
        if base in ["BTC", "ETH"]:
            return round(raw_units, 3)
        elif base in ["SOL", "NEAR", "AVAX", "LINK"]:
            return round(raw_units, 2)
        else:
            return round(raw_units, 0)

    async def execute_open(self, symbol: str, side: str, price: float, reason: str, regime: str = "NORMAL"):
        market_symbol = f"{symbol.split('/')[0]}/USDT:USDT"
        notional_target = self.compute_dynamic_notional()
        amount = self.get_contract_amount(symbol, notional_target, price)
        
        if amount <= 0:
            return

        order_side = "buy" if side == "LONG" else "sell"
        logger.info(f"⚡ [TURBO DISPARO] {side} {amount} {symbol} (${notional_target:.0f} USD | Régimen: {regime}) @ ${price:,.4f} | Razón: {reason}")
        
        try:
            order = await self.exchange.create_order(
                symbol=market_symbol,
                type='market',
                side=order_side,
                amount=amount
            )
            fill_price = float(order.get('average') or order.get('price') or price)
            
            # Margen Holgado: TP Final al +3.50% ($75 - $110 USD) y SL al -1.20%
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
                "regime": regime,
                "tp1_reached": False,
                "opened_at": time.time()
            }
            logger.info(f"✅ [TURBO CONFIRMADO] {side} {amount} {symbol} @ ${fill_price:,.4f} | TP1: +1.50% | Runner: ${tp:,.4f} | SL: ${sl:,.4f}")
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
            
            if pnl > 1.0:
                self.consecutive_wins += 1
                self.consecutive_losses = 0
                logger.info(f"🏆 [TURBO GANANCIA] {symbol} PnL: ${pnl:+.2f} USDT | Racha Victorias: {self.consecutive_wins}")
            elif pnl < -1.0:
                self.consecutive_losses += 1
                self.consecutive_wins = 0
                logger.info(f"⚠️ [TURBO PÉRDIDA] {symbol} PnL: ${pnl:+.2f} USDT | Racha Pérdidas: {self.consecutive_losses}")
            else:
                logger.info(f"⚖️ [TURBO BREAKEVEN] {symbol} PnL: ${pnl:+.2f} USDT")

            del self.positions[symbol]
        except Exception as e:
            logger.error(f"❌ Error cerrando posición en Binance: {e}")

    async def run(self):
        self.is_running = True
        await self.initialize()

        logger.info("🟢 Bucle Autónomo TURBO (Margen Holgado Institucional) Iniciado.")
        
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

                    # Salidas con Gestión Institucional Holgada en RAM
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

                            # 1. Breakeven al +0.80% a favor -> Asegura Entrada + 0.25% ganancia neta ($5 - $7 USD)
                            if pnl_pct >= 0.0080 and sl < entry_p * 1.0025:
                                pos["stop_loss"] = entry_p * 1.0025
                                logger.info(f"🛡️ [TURBO BREAKEVEN] {symbol} LONG asegurado a ${pos['stop_loss']:,.4f}")

                            # 2. TP1 Institucional (+1.50% -> Asegura +0.80% en Stop Loss)
                            if pnl_pct >= 0.0150 and not pos.get("tp1_reached", False):
                                pos["tp1_reached"] = True
                                pos["stop_loss"] = entry_p * 1.0080
                                logger.info(f"🎯 [TURBO TP1 ALCANZADO (+1.50%)] {symbol} Stop Loss elevado a ${pos['stop_loss']:,.4f}")

                            # 3. Trailing Runner (+2.00% en adelante -> persigue a 0.60% del pico)
                            if pnl_pct >= 0.0200:
                                new_trailing = pos["peak_price"] * 0.9940
                                if new_trailing > pos["stop_loss"]:
                                    pos["stop_loss"] = new_trailing
                                    logger.info(f"📈 [TURBO TRAILING RUNNER] {symbol} SL elevado a ${new_trailing:,.4f}")

                        else:  # SHORT
                            if current_price < pos["peak_price"]:
                                pos["peak_price"] = current_price
                            pnl_pct = (entry_p - current_price) / entry_p

                            # 1. Breakeven al +0.80% a favor -> Asegura Entrada - 0.25% ganancia neta
                            if pnl_pct >= 0.0080 and sl > entry_p * 0.9975:
                                pos["stop_loss"] = entry_p * 0.9975
                                logger.info(f"🛡️ [TURBO BREAKEVEN] {symbol} SHORT asegurado a ${pos['stop_loss']:,.4f}")

                            # 2. TP1 Institucional (+1.50% -> Asegura +0.80% en Stop Loss)
                            if pnl_pct >= 0.0150 and not pos.get("tp1_reached", False):
                                pos["tp1_reached"] = True
                                pos["stop_loss"] = entry_p * 0.9920
                                logger.info(f"🎯 [TURBO TP1 ALCANZADO (+1.50%)] {symbol} Stop Loss bajado a ${pos['stop_loss']:,.4f}")

                            # 3. Trailing Runner (+2.00% en adelante -> persigue a 0.60% del pico)
                            if pnl_pct >= 0.0200:
                                new_trailing = pos["peak_price"] * 1.0060
                                if new_trailing < pos["stop_loss"]:
                                    pos["stop_loss"] = new_trailing
                                    logger.info(f"📈 [TURBO TRAILING RUNNER] {symbol} SL bajado a ${new_trailing:,.4f}")

                        # Cierre por TP Final Runner o Trailing Stop
                        if (side == "LONG" and current_price >= tp) or (side == "SHORT" and current_price <= tp):
                            await self.execute_close(symbol, current_price, "TAKE_PROFIT_RUNNER_ALCANZADO (+3.50%)")
                        elif (side == "LONG" and current_price <= pos["stop_loss"]) or (side == "SHORT" and current_price >= pos["stop_loss"]):
                            is_trailing = (pos["stop_loss"] > entry_p) if side == "LONG" else (pos["stop_loss"] < entry_p)
                            reason = "TRAILING_STOP_EJECUTADO" if is_trailing else "STOP_LOSS_ACTIVADO"
                            await self.execute_close(symbol, current_price, reason)

                    # 3. Lógica de Disparo: Micro-Momentum + OBI en RAM
                    elif len(self.positions) < 2 and len(history) >= 4:
                        recent_change = (current_price - history[-4]) / history[-4]
                        regime = self.detect_volatility_regime(history)
                        
                        bid_vol = float(ticker.get('bidVolume', 0.0) or 0.0)
                        ask_vol = float(ticker.get('askVolume', 0.0) or 0.0)
                        total_vol = bid_vol + ask_vol
                        obi = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0.0
                        
                        if recent_change > 0.0003 and obi >= -0.40:
                            await self.execute_open(symbol, "LONG", current_price, f"Impulso Alcista (+{recent_change:.3%} | OBI: {obi:+.2f})", regime)
                        elif recent_change < -0.0003 and obi <= 0.40:
                            await self.execute_open(symbol, "SHORT", current_price, f"Impulso Bajista ({recent_change:.3%} | OBI: {obi:+.2f})", regime)

                except Exception as e:
                    logger.debug(f"Error procesando {symbol}: {e}")

            if self.iteration % 15 == 0:
                logger.info(f"📊 [TURBO EN VIVO #{self.iteration}] Posiciones Activas: {len(self.positions)}")

            await asyncio.sleep(1.0)

    async def close(self):
        self.is_running = False
        await self.exchange.close()
        await self.data_feed.close()

if __name__ == "__main__":
    bot = TurboInstitutionalEngine()
    try:
        asyncio.run(bot.run())
    except (KeyboardInterrupt, SystemExit):
        pass
