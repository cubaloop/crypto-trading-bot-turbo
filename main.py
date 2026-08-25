from data.sentinel_client import SentinelClient
import asyncio
import logging
import os
import signal
import sys
import time

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from config.settings import config
from data.ws_market_stream import MarketStream
from data.news_streamer import NewsStreamer
from sentiment.sentiment_analyzer import SentimentAnalyzer
from strategies.turbo_strategy import TurboStrategy
from risk.risk_manager import RiskManager
from execution.executor import PaperExecutor
from web.server import DashboardServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("KuQuantTurboMain")

from data.keep_alive import KeepAliveMesh

from ai.meta_learner import TurboMetaCognitiveLearner
from ai.episodic_memory import EpisodicMemoryEngine, MarketVector

class TurboTradingEngine:
    def __init__(self):
        self.market_stream = MarketStream(exchange_id=config.exchange_id)
        self.news_streamer = NewsStreamer(api_key=config.cryptopanic_api_key)
        self.sentiment_analyzer = SentimentAnalyzer(half_life_minutes=config.sentiment_half_life_minutes)
        self.strategy = TurboStrategy()
        self.meta_learner = TurboMetaCognitiveLearner()
        self.memory_engine = EpisodicMemoryEngine()
        binance_key = os.getenv("BINANCE_TESTNET_API_KEY", "LyS7ZwuG771PRgZSD7T2AoidqJ8FIGnHUrOElsphYMTZg7BQtgkvt8PTEO95zFXX")
        binance_secret = os.getenv("BINANCE_TESTNET_API_SECRET", "EVWlkCZIJAYRe8bgw7Xu7hRamRqjyWxgEms0zzKTPkHwKTU0ALJxUKSJwUhb7gy6")
        from execution.binance_testnet_executor import BinanceTestnetExecutorTurbo
        logger.info("⚡ Conectando KuQuant TURBO a Binance Futures Testnet Oficial (testnet.binancefuture.com)")
        self.executor = BinanceTestnetExecutorTurbo(api_key=binance_key, secret=binance_secret, leverage=2)
        self.risk_manager = RiskManager(
            initial_balance=getattr(self.executor, 'initial_balance', 4923.84),
            risk_per_trade_pct=config.risk_per_trade_pct,
            max_daily_drawdown_pct=config.max_daily_drawdown_pct
        )
        self.web_server = DashboardServer(
            host=config.host,
            port=config.port,
            on_reset_circuit_breaker=self.risk_manager.reset_circuit_breaker
        )
        self.keep_alive = KeepAliveMesh(interval_seconds=420)
        
        self.news_history = []
        self.iteration = 0
        self.sentinel_client = SentinelClient()
        self.web_server.on_sentinel_push = self.on_sentinel_push_received
        self.is_running = False
        self._last_known_trade_count = 0

    async def on_sentinel_push_received(self, alert: dict):
        """
        Receptor instantáneo (<5ms) de alertas Webhook del SPIDERWEB SENTINEL.
        Ejecuta cierre de emergencia inmediato si el choque impacta una posición activa.
        """
        sym = alert.get("source_symbol", "")
        v_type = alert.get("vibration_type", "")
        z_vol = alert.get("z_score_volume", 0.0)
        
        for pos_sym, pos in list(self.executor.positions.items()):
            if (pos_sym.startswith(sym.split('/')[0]) or sym.startswith("BTC")):
                if pos.side == "LONG" and v_type in ["SHOCKWAVE_DUMP", "ORDER_BOOK_COLLAPSE"]:
                    logger.warning(f"🚨 [PUSH WEBHOOK SENTINEL RECIBIDO EN <5MS] Cierre inmediato de {pos_sym} por choque bajista masivo en {sym} (Z-Score: {z_vol:.1f})")
                    current_p = self.market_stream.last_prices.get(pos_sym, pos.entry_price)
                    await self.executor.close_position(pos_sym, exit_price=current_p, reason=f"SENTINEL_PUSH_EMERGENCY ({sym} {v_type})")

    async def initialize(self):
        logger.info("=================================================================")
        logger.info("⚡ INICIANDO BOT AUTÓNOMO KUQUANT TURBO SCALPER • IA META-COGNITIVA & MEMORIA EPISÓDICA 24/7")
        logger.info(f"Modo: [{config.mode.upper()}] (Capital Virtual: ${getattr(self.executor, 'initial_balance', 4923.84):,.2f})")
        logger.info(f"Pares Monitoreados: {', '.join(config.symbols)}")
        logger.info(f"Riesgo Turbo: {config.risk_per_trade_pct:.1%} por trade | {config.max_daily_drawdown_pct:.1%} Max DD")
        logger.info("Estrategia: Banco de Memoria + Meta-Learning + Multi-Timeframe EMA + Volatility Squeeze")
        logger.info("=================================================================")

        await self.market_stream.initialize()
        if hasattr(self.executor, 'initialize'):
            await self.executor.initialize()
            if hasattr(self.executor, 'initial_balance') and self.executor.initial_balance > 0:
                self.risk_manager.initial_balance = self.executor.initial_balance
                self.risk_manager.daily_high_equity = self.executor.initial_balance
        await self.web_server.start()
        self.keep_alive.start()

    async def run(self, max_iterations: int = None):
        self.is_running = True
        await self.initialize()

        try:
            while self.is_running:
                self.iteration += 1
                cycle_start = time.time()

                current_prices = dict(self.market_stream.last_prices)
                
                # 0. Consulta en Tiempo Real al SPIDERWEB SENTINEL (Tela de Araña)
                active_vibrations = await self.sentinel_client.fetch_active_vibrations()
                
                # Evaluación de Cierre de Emergencia por Onda de Choque para posiciones abiertas
                for sym, pos in list(self.executor.positions.items()):
                    sentinel_dec = self.sentinel_client.evaluate_shockwave_decision(
                        symbol=sym,
                        current_position_side=pos.side,
                        new_signal_action=None
                    )
                    if sentinel_dec["emergency_close"]:
                        logger.warning(f"🚨 {sentinel_dec['reason']}")
                        await self.executor.close_position(sym, exit_price=current_prices.get(sym, pos.entry_price), reason=sentinel_dec["reason"])

                # 1. Ingesta de Noticias y NLP
                if self.iteration % 10 == 1:
                    new_articles = await self.news_streamer.fetch_latest_news()
                    if new_articles:
                        self.news_history.extend(new_articles)
                        for a in new_articles:
                            logger.info(f"📰 [TURBO NLP]: '{a.title[:55]}...' (Score: {a.sentiment_score:+.2f})")

                decayed_score, avg_conf, has_black_swan = self.sentiment_analyzer.calculate_decayed_sentiment(self.news_history)

                # 2. Ingesta de Mercado & Señales Turbo para cada par
                current_prices = dict(self.market_stream.last_prices)
                
                # Auto-Reflexión Meta-Cognitiva
                dynamic_weights, dynamic_threshold, reflection_msg = self.meta_learner.evaluate_performance_and_adapt(
                    trade_history=self.executor.trade_history,
                    current_market_trend_bullish=True
                )
                if self.iteration % 20 == 1:
                    logger.info(reflection_msg)

                self.strategy.signal_threshold = dynamic_threshold
                for symbol in config.symbols:
                    snapshot = await self.market_stream.fetch_snapshot(symbol)
                    if snapshot:
                        current_prices[symbol] = snapshot.last_price
                    ohlcv_df = await self.market_stream.fetch_ohlcv(symbol, timeframe=config.timeframe, limit=50)

                    # Generar Señal Turbo
                    signal = self.strategy.generate_signal(
                        snapshot=snapshot,
                        ohlcv_df=ohlcv_df,
                        decayed_sentiment=decayed_score,
                        has_black_swan=has_black_swan
                    )

                                        # Consulta de Veto o Anticipación de Onda de Choque del Sentinel
                    sentinel_eval = self.sentinel_client.evaluate_shockwave_decision(
                        symbol=symbol,
                        current_position_side=None,
                        new_signal_action=signal.action
                    )
                    if sentinel_eval["veto_entry"]:
                        logger.warning(sentinel_eval["reason"])
                        trade_allowed = False
                    elif sentinel_eval["shockwave_entry"] and symbol not in self.executor.positions:
                        logger.info(sentinel_eval["reason"])
                        signal.action = sentinel_eval["shockwave_entry"]
                        trade_allowed = True

                    trade_allowed, reason = self.risk_manager.check_auto_reactivation(
                        signal_conviction=signal.conviction
                    )

                    # CONSULTA AL BANCO DE MEMORIA
                    if trade_allowed and signal.action in ["BUY", "SELL"] and symbol not in self.executor.positions:
                        m_vec = MarketVector(
                            symbol=symbol,
                            action=signal.action,
                            trend_direction=1.0 if signal.action == "BUY" else -1.0,
                            volatility_atr_pct=signal.atr / max(1.0, signal.entry_price),
                            order_book_imbalance=getattr(snapshot, 'order_book_imbalance', 0.0) if snapshot else 0.0,
                            volume_delta=getattr(snapshot, 'volume_delta', 0.0) if snapshot else 0.0,
                            entropy=0.30,
                            sentiment_score=decayed_score,
                            conviction=signal.conviction
                        )
                        mem_mult, win_rate, mem_insight = self.memory_engine.query_past_experience(m_vec)
                        if mem_mult < 0.50:
                            logger.warning(f"🛑 [MEMORIA TURBO VETÓ ORDEN] en {symbol}: {mem_insight}")
                            trade_allowed = False

                        if trade_allowed:
                            units = self.risk_manager.compute_position_size(
                                entry_price=signal.entry_price,
                                stop_loss_price=signal.stop_loss
                            )
                            if units > 0:
                                if asyncio.iscoroutinefunction(self.executor.execute_signal):
                                    await self.executor.execute_signal(signal, units)
                                else:
                                    self.executor.execute_signal(signal, units)

                # 4. Trailing Stops y Cierre de Órdenes (TP1, TP2, Trailing SL)
                if asyncio.iscoroutinefunction(self.executor.update_and_check_exits):
                    await self.executor.update_and_check_exits(current_prices)
                else:
                    self.executor.update_and_check_exits(current_prices)

                # Consolidar experiencia en memoria episódica
                if len(self.executor.trade_history) > self._last_known_trade_count:
                    new_trades = self.executor.trade_history[self._last_known_trade_count:]
                    for t in new_trades:
                        t_vec = MarketVector(
                            symbol=t.get('symbol', 'BTC/USDT'),
                            action="BUY" if t.get('side') == "LONG" else "SELL",
                            trend_direction=1.0 if t.get('side') == "LONG" else -1.0,
                            volatility_atr_pct=0.01,
                            order_book_imbalance=0.0,
                            volume_delta=0.0,
                            entropy=0.30,
                            sentiment_score=0.0,
                            conviction=0.5
                        )
                        self.memory_engine.record_completed_trade(
                            pos_id=t.get('id', 'trade'),
                            vector=t_vec,
                            entry_price=t.get('entry_price', 0.0),
                            exit_price=t.get('exit_price', 0.0),
                            net_pnl=t.get('net_pnl', 0.0),
                            opened_at=t.get('closed_at', time.time()) - 300.0
                        )
                    self._last_known_trade_count = len(self.executor.trade_history)

                # 5. Actualizar Balance y Equity
                current_equity = self.executor.get_equity(current_prices)
                self.risk_manager.update_equity(current_equity)

                # 6. Transmitir estado al Dashboard
                positions_dict = {
                    s: {
                        "id": p.id,
                        "symbol": p.symbol,
                        "side": p.side,
                        "entry_price": p.entry_price,
                        "units": p.units,
                        "stop_loss": p.stop_loss,
                        "take_profit": getattr(p, "take_profit", 0.0),
                        "take_profit_2": getattr(p, "take_profit_2", getattr(p, "take_profit", 0.0)),
                        "highest_price": getattr(p, "highest_price", p.entry_price),
                        "lowest_price": p.lowest_price,
                        "opened_at": p.opened_at,
                        "notional_usd": p.notional_usd
                    } for s, p in self.executor.positions.items()
                }
                news_list = [
                    {
                        "title": n.title,
                        "symbol": n.symbol,
                        "sentiment_score": n.sentiment_score,
                        "confidence": n.confidence,
                        "event_category": n.event_category,
                        "timestamp": n.timestamp
                    } for n in self.news_history[-10:]
                ]
                await self.web_server.broadcast_state({
                    "iteration": self.iteration,
                    "equity": current_equity,
                    "initial_balance": getattr(self.executor, 'initial_balance', 4923.84),
                    "balance": getattr(self.executor, 'balance_usd', 4923.84),
                    "decayed_sentiment": decayed_score,
                    "circuit_breaker_active": self.risk_manager.is_circuit_breaker_active,
                    "current_prices": current_prices,
                    "positions": positions_dict,
                    "trade_history": self.executor.trade_history[-100:],
                    "news_history": news_list
                })

                # 7. Telemetría en consola cada 5 ciclos
                if self.iteration % 5 == 0:
                    pnl_pct = ((current_equity - getattr(self.executor, 'initial_balance', 4923.84)) / getattr(self.executor, 'initial_balance', 4923.84)) * 100
                    logger.info(f"⚡ [ESTADO TURBO #{self.iteration}] Equity: ${current_equity:,.2f} ({pnl_pct:+.2f}%) | Posiciones: {len(self.executor.positions)}")

                if max_iterations and self.iteration >= max_iterations:
                    break

                elapsed = time.time() - cycle_start
                sleep_time = max(0.2, config.price_poll_interval_seconds - elapsed)
                await asyncio.sleep(sleep_time)

        except (asyncio.CancelledError, KeyboardInterrupt):
            logger.info("Cerrando motor Turbo...")
        finally:
            await self.shutdown()

    async def shutdown(self):
        self.sentinel_client = SentinelClient()
        self.web_server.on_sentinel_push = self.on_sentinel_push_received
        self.is_running = False
        await self.market_stream.close()
        await self.web_server.stop()
        logger.info("Bot Turbo finalizado correctamente.")

async def main():
    bot = TurboTradingEngine()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
