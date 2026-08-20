import asyncio
import logging
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

class TurboTradingEngine:
    def __init__(self):
        self.market_stream = MarketStream(exchange_id=config.exchange_id)
        self.news_streamer = NewsStreamer(api_key=config.cryptopanic_api_key)
        self.sentiment_analyzer = SentimentAnalyzer(half_life_minutes=config.sentiment_half_life_minutes)
        self.strategy = TurboStrategy()
        self.risk_manager = RiskManager(
            initial_balance=config.initial_virtual_balance,
            risk_per_trade_pct=config.risk_per_trade_pct,
            max_daily_drawdown_pct=config.max_daily_drawdown_pct
        )
        self.executor = PaperExecutor(initial_balance_usd=config.initial_virtual_balance)
        self.web_server = DashboardServer(
            host=config.host,
            port=config.port,
            on_reset_circuit_breaker=self.risk_manager.reset_circuit_breaker
        )
        self.keep_alive = KeepAliveMesh(interval_seconds=420)
        
        self.news_history = []
        self.iteration = 0
        self.is_running = False

    async def initialize(self):
        logger.info("=================================================================")
        logger.info("⚡ INICIANDO BOT AUTÓNOMO KUQUANT TURBO (ALPHA-X) • SCALPING 24/7")
        logger.info(f"Modo: [{config.mode.upper()}] (Capital Virtual: ${config.initial_virtual_balance:,.2f})")
        logger.info(f"Pares Monitoreados: {', '.join(config.symbols)}")
        logger.info(f"Riesgo Turbo: {config.risk_per_trade_pct:.1%} por trade | {config.max_daily_drawdown_pct:.1%} Max DD")
        logger.info("Estrategia: Volatility Squeeze Breakout + Order Book Depth Acceleration")
        logger.info("=================================================================")

        await self.market_stream.initialize()
        await self.web_server.start()
        self.keep_alive.start()

    async def run(self, max_iterations: int = None):
        self.is_running = True
        await self.initialize()

        try:
            while self.is_running:
                self.iteration += 1
                cycle_start = time.time()

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

                    trade_allowed, reason = self.risk_manager.check_auto_reactivation(
                        signal_conviction=signal.conviction
                    )
                    if trade_allowed and signal.action in ["BUY", "SELL"] and symbol not in self.executor.positions:
                        units = self.risk_manager.compute_position_size(
                            entry_price=signal.entry_price,
                            stop_loss_price=signal.stop_loss
                        )
                        if units > 0:
                            logger.info(f"⚡ [SEÑAL TURBO] en {symbol}: {signal.action} | {signal.reason}")
                            self.executor.execute_signal(signal, units)

                # 4. Trailing Stops y Cierre de Órdenes (TP1, TP2, Trailing SL)
                self.executor.update_and_check_exits(current_prices)

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
                        "take_profit": p.take_profit,
                        "take_profit_2": p.take_profit_2,
                        "highest_price": p.highest_price,
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
                    "initial_balance": config.initial_virtual_balance,
                    "decayed_sentiment": decayed_score,
                    "circuit_breaker_active": self.risk_manager.is_circuit_breaker_active,
                    "current_prices": current_prices,
                    "positions": positions_dict,
                    "trade_history": self.executor.trade_history[-100:],
                    "news_history": news_list
                })

                # 7. Telemetría en consola cada 5 ciclos
                if self.iteration % 5 == 0:
                    pnl_pct = ((current_equity - config.initial_virtual_balance) / config.initial_virtual_balance) * 100
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
