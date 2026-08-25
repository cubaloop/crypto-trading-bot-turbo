import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from data.ws_market_stream import MarketSnapshot

logger = logging.getLogger("TurboStrategy")

@dataclass
class TradeSignal:
    symbol: str
    action: str  # "BUY", "SELL", "HOLD"
    conviction: float  # -1.0 to +1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    take_profit_2: float
    atr: float
    reason: str

class TurboStrategy:
    def __init__(
        self,
        bb_window: int = 20,
        bb_std: float = 2.0,
        atr_window: int = 14,
        signal_threshold: float = 0.15  # Umbral ágil para capturar rupturas en memecoins
    ):
        self.bb_window = bb_window
        self.bb_std = bb_std
        self.atr_window = atr_window
        self.signal_threshold = signal_threshold

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if len(df) < self.bb_window:
            return df

        # 1. Bollinger Bands & %B
        df['sma_20'] = df['close'].rolling(window=self.bb_window).mean()
        df['std_20'] = df['close'].rolling(window=self.bb_window).std()
        df['upper_bb'] = df['sma_20'] + (df['std_20'] * self.bb_std)
        df['lower_bb'] = df['sma_20'] - (df['std_20'] * self.bb_std)
        
        bb_width = df['upper_bb'] - df['lower_bb']
        df['percent_b'] = (df['close'] - df['lower_bb']) / bb_width.replace(0, 0.0001)

        # 2. ATR Robusto (14 períodos para absorber volatilidad real)
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift(1)).abs()
        low_close = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr_14'] = tr.rolling(window=self.atr_window).mean()

        # 3. Fast MACD (3, 10, 16)
        ema_3 = df['close'].ewm(span=3, adjust=False).mean()
        ema_10 = df['close'].ewm(span=10, adjust=False).mean()
        df['macd_fast'] = ema_3 - ema_10

        # 4. Fast Stochastic K
        lowest_low = df['low'].rolling(window=14).min()
        highest_high = df['high'].rolling(window=14).max()
        df['stoch_k'] = ((df['close'] - lowest_low) / (highest_high - lowest_low).replace(0, 0.0001)) * 100

        # 5. EMA 50 Trend Filter
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

        return df

    def generate_signal(
        self,
        snapshot: MarketSnapshot,
        ohlcv_df: Optional[pd.DataFrame],
        decayed_sentiment: float,
        has_black_swan: bool = False
    ) -> TradeSignal:
        if has_black_swan:
            return TradeSignal(
                symbol=snapshot.symbol,
                action="SELL" if decayed_sentiment < 0 else "HOLD",
                conviction=-1.0,
                entry_price=snapshot.last_price,
                stop_loss=snapshot.last_price * 1.015,
                take_profit=snapshot.last_price * 0.97,
                take_profit_2=snapshot.last_price * 0.95,
                atr=snapshot.last_price * 0.01,
                reason="🚨 Freno de Emergencia Turbo: Cisne Negro detectado"
            )

        if ohlcv_df is None or len(ohlcv_df) < self.bb_window:
            atr_approx = snapshot.last_price * 0.008
            return TradeSignal(
                symbol=snapshot.symbol,
                action="HOLD",
                conviction=0.0,
                entry_price=snapshot.last_price,
                stop_loss=snapshot.last_price - (1.8 * atr_approx),
                take_profit=snapshot.last_price + (2.0 * atr_approx),
                take_profit_2=snapshot.last_price + (3.5 * atr_approx),
                atr=atr_approx,
                reason="Inicializando buffer de velas de alta resolución"
            )

        df = self.compute_indicators(ohlcv_df)
        latest = df.iloc[-1]

        pct_b = latest.get('percent_b', 0.5)
        atr = latest.get('atr_14', snapshot.last_price * 0.008)
        # Garantizar que el ATR mínimo sea del 0.4% del precio para evitar stops microscópicos
        atr = max(atr, snapshot.last_price * 0.004)
        macd_fast = latest.get('macd_fast', 0.0)
        stoch_k = latest.get('stoch_k', 50.0)
        ema_50 = latest.get('ema_50', snapshot.last_price)
        trend_bullish = snapshot.last_price >= ema_50

        # 1. Señal de Ruptura de Squeeze (%B)
        s_squeeze = float(np.clip((pct_b - 0.50) * 2.0, -1.0, 1.0))

        # 2. Señal de Aceleración de Libro L2
        s_obi_accel = float(np.clip(snapshot.order_book_imbalance + (0.5 * snapshot.obi_acceleration), -1.0, 1.0))

        # 3. Señal de Momentum Rápido
        s_momentum = 0.0
        if macd_fast > 0 and stoch_k > 50:
            s_momentum = 0.85
        elif macd_fast < 0 and stoch_k < 50:
            s_momentum = -0.85

        # 4. Fusión Alfa Turbo
        alpha_turbo = (0.35 * s_squeeze) + (0.35 * s_obi_accel) + (0.20 * s_momentum) + (0.10 * decayed_sentiment)
        conviction = float(np.clip(alpha_turbo, -1.0, 1.0))

        # Disparadores de Micro-Scalping Ágiles (Ruptura Squeeze + Momentum)
        if conviction >= self.signal_threshold:
            action = "BUY"
            sl = snapshot.last_price - (1.4 * atr)
            tp1 = snapshot.last_price + (2.0 * atr)
            tp2 = snapshot.last_price + (3.5 * atr)
            reason = f"🚀 TURBO LONG | Squeeze %B: {pct_b:.2f} | Conv: {conviction:+.2f}"
        elif conviction <= -self.signal_threshold:
            action = "SELL"
            sl = snapshot.last_price + (1.4 * atr)
            tp1 = snapshot.last_price - (2.0 * atr)
            tp2 = snapshot.last_price - (3.5 * atr)
            reason = f"🔻 TURBO SHORT | Squeeze %B: {pct_b:.2f} | Conv: {conviction:+.2f}"
        else:
            action = "HOLD"
            sl = snapshot.last_price - (1.8 * atr)
            tp1 = snapshot.last_price + (2.0 * atr)
            tp2 = snapshot.last_price + (3.5 * atr)
            reason = f"⏸️ Filtrado por Tendencia/Ruido (Convicción: {conviction:+.2f} | Tendencia: {'ALCISTA' if trend_bullish else 'BAJISTA'})"

        return TradeSignal(
            symbol=snapshot.symbol,
            action=action,
            conviction=conviction,
            entry_price=snapshot.last_price,
            stop_loss=sl,
            take_profit=tp1,
            take_profit_2=tp2,
            atr=atr,
            reason=reason
        )
