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
logger = logging.getLogger("PureAutonomousScalper")

class SimpleAutonomousEngine:
    def __init__(self):
        # Credenciales directas de Binance Testnet
        self.api_key = os.getenv("BINANCE_TESTNET_API_KEY", "LyS7ZwuG771PRgZSD7T2AoidqJ8FIGnHUrOElsphYMTZg7BQtgkvt8PTEO95zFXX")
        self.api_secret = os.getenv("BINANCE_TESTNET_API_SECRET", "EVWlkCZIJAYRe8bgw7Xu7hRamRqjyWxgEms0zzKTPkHwKTU0ALJxUKSJwUhb7gy6")
        
        # Conexión directa con CCXT a Binance Futures Testnet
        self.exchange = ccxt_async.binanceusdm({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        self.exchange.set_sandbox_mode(True)
        
        # Conexión Bybit pública para lectura limpia de precios y libros
        self.data_feed = ccxt_async.bybit({'enableRateLimit': True, 'timeout': 5000})
        
        # Universo de pares activos
        self.symbols = ["DOGE/USDT", "SOL/USDT", "BTC/USDT", "ETH/USDT", "NEAR/USDT"]
        self.positions: Dict[str, Dict] = {}
        self.price_history: Dict[str, List[float]] = {s: [] for s in self.symbols}
        self.is_running = False
        self.iteration = 0
        
        # Inteligencia en RAM: Contador de Rachas (Kelly Dinámico con TODO EL FONDO)
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.base_notional = 1800.0  # Asignación de Capital Real Fuerte ($1,800 USDT por trade)

    async def initialize(self):
        logger.info("🚀 Inicializando Motor Puro Ultra-Básico en Binance Futures Testnet...")
        try:
            await self.data_feed.load_markets()
            balance = await self.exchange.fetch_balance()
            usdt_free = float(balance.get('USDT', {}).get('free', 5000.0) or 5000.0)
            logger.info(f"💰 Balance Libre en Binance Testnet: ${usdt_free:,.2f} USDT")
        except Exception as e:
            logger.warning(f"Aviso en inicialización: {e}")

    def compute_dynamic_notional(self) -> float:
        # Si viene en racha ganadora (>=2 wins) -> escala a $2,400 USDT
        if self.consecutive_wins >= 2:
            return min(2500.0, self.base_notional + (self.consecutive_wins * 250.0))
        # Si sufre racha perdedora (>=2 losses) -> reduce a $800 USDT para proteger
        elif self.consecutive_losses >= 2:
            return max(600.0, self.base_notional - (self.consecutive_losses * 400.0))
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

    def detect_volatility_regime(self, history: List[float]) -> str:
        if len(history) < 10:
            return "NORMAL"
        std_pct = float(np.std(history[-15:]) / np.mean(history[-15:]))
        if std_pct >= 0.0012: # Alta volatilidad / Expansión
            return "EXPLOSION"
        elif std_pct <= 0.0003: # Baja volatilidad / Rango estrecho
            return "RANGO"
        return "NORMAL"

    async def execute_open(self, symbol: str, side: str, price: float, reason: str, regime: str = "NORMAL"):
        market_symbol = f"{symbol.split('/')[0]}/USDT:USDT"
        notional_target = self.compute_dynamic_notional()
        amount = self.get_contract_amount(symbol, notional_target, price)
        
        if amount <= 0:
            return

        order_side = "buy" if side == "LONG" else "sell"
        logger.info(f"⚡ [DISPARO AUTÓNOMO] Abriendo {side} {amount} {symbol} (Notional: ${notional_target:.0f} | Régimen: {regime}) @ ${price:,.4f} | Razón: {reason}")
        
        try:
            order = await self.exchange.create_order(
                symbol=market_symbol,
                type='market',
                side=order_side,
                amount=amount
            )
            fill_price = float(order.get('average') or order.get('price') or price)
            
            # TP y SL Amplios para Captura Real de Beneficios (Superando Comisiones)
            if regime == "EXPLOSION":
                tp_mult = 0.0220  # +2.20% en expansión (Objetivo: $40 - $55 USD netos)
                sl_mult = 0.0120  # -1.20% de SL con holgura para volatilidad
            elif regime == "RANGO":
                tp_mult = 0.0100  # +1.00% en rango (Objetivo: $18 - $25 USD netos)
                sl_mult = 0.0070  # -0.70%
            else:
                tp_mult = 0.0150  # +1.50% estándar (Objetivo: $27 - $36 USD netos)
                sl_mult = 0.0090  # -0.90%

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
                "regime": regime,
                "opened_at": time.time()
            }
            logger.info(f"✅ [POSICIÓN CONFIRMADA EN BINANCE] {side} {amount} {symbol} @ ${fill_price:,.4f} | TP: ${tp:,.4f} | SL: ${sl:,.4f} | Régimen: {regime}")
        except Exception as e:
            logger.error(f"❌ Error ejecutando apertura en Binance: {e}")

    async def execute_close(self, symbol: str, current_price: float, reason: str):
        pos = self.positions.get(symbol)
        if not pos:
            return

        market_symbol = pos["market_symbol"]
        close_side = "sell" if pos["side"] == "LONG" else "buy"
        amount = pos["units"]

        logger.info(f"🎯 [CIERRE AUTÓNOMO] Liquidando {pos['side']} {amount} {symbol} @ ${current_price:,.4f} | Razón: {reason}")
        try:
            await self.exchange.create_order(
                symbol=market_symbol,
                type='market',
                side=close_side,
                amount=amount,
                params={'reduceOnly': True}
            )
            pnl = (current_price - pos['entry_price']) * amount if pos['side'] == "LONG" else (pos['entry_price'] - current_price) * amount
            
            # Actualizar racha en RAM
            if pnl > 0.05:
                self.consecutive_wins += 1
                self.consecutive_losses = 0
                logger.info(f"🏆 [GANANCIA] {symbol} PnL: ${pnl:+.2f} USDT | Racha Victorias: {self.consecutive_wins}")
            elif pnl < -0.05:
                self.consecutive_losses += 1
                self.consecutive_wins = 0
                logger.info(f"⚠️ [PÉRDIDA] {symbol} PnL: ${pnl:+.2f} USDT | Racha Pérdidas: {self.consecutive_losses}")
            else:
                logger.info(f"⚖️ [BREAKEVEN] {symbol} PnL: ${pnl:+.2f} USDT")

            del self.positions[symbol]
        except Exception as e:
            logger.error(f"❌ Error cerrando posición en Binance: {e}")

    async def run(self):
        self.is_running = True
        await self.initialize()

        logger.info("🟢 Bucle de Trading Autónomo Directo Iniciado.")
        
        while self.is_running:
            self.iteration += 1
            
            for symbol in self.symbols:
                try:
                    # 1. Obtener precio en vivo y micro-libro
                    ticker = await self.data_feed.fetch_ticker(symbol)
                    current_price = float(ticker.get('last') or ticker.get('close') or 0.0)
                    
                    if current_price <= 0:
                        continue

                    # Guardar historial de ticks
                    history = self.price_history[symbol]
                    history.append(current_price)
                    if len(history) > 30:
                        self.price_history[symbol] = history[-30:]

                    # 2. Gestionar salidas de posiciones abiertas (Breakeven / Trailing Stop / TP / SL / Time-Stop)
                    if symbol in self.positions:
                        pos = self.positions[symbol]
                        entry_p = pos["entry_price"]
                        side = pos["side"]
                        sl = pos["stop_loss"]
                        tp = pos["take_profit"]
                        age_seconds = time.time() - pos["opened_at"]

                        # Actualizar pico de precio alcanzado (Highest / Lowest)
                        if "peak_price" not in pos:
                            pos["peak_price"] = current_price
                        
                        if side == "LONG":
                            if current_price > pos["peak_price"]:
                                pos["peak_price"] = current_price
                            
                            pnl_pct = (current_price - entry_p) / entry_p

                            # A. Breakeven Dinámico (+0.50% de ganancia -> Asegura Entrada + 0.15% ganancia neta)
                            if pnl_pct >= 0.0050 and sl < entry_p * 1.0015:
                                pos["stop_loss"] = entry_p * 1.0015
                                logger.info(f"🛡️ [BREAKEVEN GANADOR] {symbol} LONG asegurado a ${pos['stop_loss']:,.4f} (+0.15% neto)")

                            # B. Trailing Stop Dinámico (Persigue el precio a 0.40% del pico si sube > +0.80%)
                            if pnl_pct >= 0.0080:
                                new_trailing_sl = pos["peak_price"] * 0.9960
                                if new_trailing_sl > pos["stop_loss"]:
                                    pos["stop_loss"] = new_trailing_sl
                                    logger.info(f"📈 [TRAILING STOP LONG] {symbol} SL elevado a ${new_trailing_sl:,.4f}")

                        else:  # SHORT
                            if current_price < pos["peak_price"]:
                                pos["peak_price"] = current_price
                            
                            pnl_pct = (entry_p - current_price) / entry_p

                            # A. Breakeven Dinámico (+0.50% de ganancia -> Asegura Entrada - 0.15% ganancia neta)
                            if pnl_pct >= 0.0050 and sl > entry_p * 0.9985:
                                pos["stop_loss"] = entry_p * 0.9985
                                logger.info(f"🛡️ [BREAKEVEN GANADOR] {symbol} SHORT asegurado a ${pos['stop_loss']:,.4f} (+0.15% neto)")

                            # B. Trailing Stop Dinámico
                            if pnl_pct >= 0.0080:
                                new_trailing_sl = pos["peak_price"] * 1.0040
                                if new_trailing_sl < pos["stop_loss"]:
                                    pos["stop_loss"] = new_trailing_sl
                                    logger.info(f"📈 [TRAILING STOP SHORT] {symbol} SL bajado a ${new_trailing_sl:,.4f}")

                        # C. Evaluaciones de Salida
                        # Take Profit Extendido
                        if (side == "LONG" and current_price >= tp) or (side == "SHORT" and current_price <= tp):
                            await self.execute_close(symbol, current_price, "TAKE_PROFIT_ALCANZADO")
                        # Stop Loss / Trailing Stop Trigger
                        elif (side == "LONG" and current_price <= pos["stop_loss"]) or (side == "SHORT" and current_price >= pos["stop_loss"]):
                            is_trailing = (pos["stop_loss"] > entry_p) if side == "LONG" else (pos["stop_loss"] < entry_p)
                            reason = "TRAILING_STOP_EJECUTADO" if is_trailing else "STOP_LOSS_ACTIVADO"
                            await self.execute_close(symbol, current_price, reason)
                        # Time-Stop Maduro (180 segundos para dar tiempo a que se desarrolle la corrida)
                        elif age_seconds >= 180.0:
                            await self.execute_close(symbol, current_price, f"ROTACION_MADURA_{int(age_seconds)}s")

                    # 3. Lógica de Disparo: Micro-Momentum + Filtro OBI en RAM (Hasta 3 trades simultáneos)
                    elif len(self.positions) < 3 and len(history) >= 5:
                        recent_change = (current_price - history[-5]) / history[-5]
                        regime = self.detect_volatility_regime(history)
                        
                        # Lectura instantánea de Asimetría del Libro L2 (OBI)
                        bid_vol = float(ticker.get('bidVolume', 0.0) or 0.0)
                        ask_vol = float(ticker.get('askVolume', 0.0) or 0.0)
                        total_vol = bid_vol + ask_vol
                        obi = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0.0
                        
                        # Si hay un micro-impulso alcista (+0.04%) y el libro NO está dominado por vendedores (OBI > -0.40)
                        if recent_change > 0.0004 and obi >= -0.40:
                            await self.execute_open(symbol, "LONG", current_price, f"Impulso Alcista (+{recent_change:.3%} | OBI: {obi:+.2f})", regime)
                        # Si hay un micro-impulso bajista (-0.04%) y el libro NO está dominado por compradores (OBI < +0.40)
                        elif recent_change < -0.0004 and obi <= 0.40:
                            await self.execute_open(symbol, "SHORT", current_price, f"Impulso Bajista ({recent_change:.3%} | OBI: {obi:+.2f})", regime)

                except Exception as e:
                    logger.debug(f"Error procesando {symbol}: {e}")

            if self.iteration % 15 == 0:
                logger.info(f"📊 [MONITOR EN VIVO #{self.iteration}] Posiciones Activas: {len(self.positions)}")

            await asyncio.sleep(1.0)

    async def close(self):
        self.is_running = False
        await self.exchange.close()
        await self.data_feed.close()

if __name__ == "__main__":
    bot = SimpleAutonomousEngine()
    try:
        asyncio.run(bot.run())
    except (KeyboardInterrupt, SystemExit):
        pass
