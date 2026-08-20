import os
import json
import time
import math
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger("EpisodicMemoryEngine")

@dataclass
class MarketVector:
    symbol: str
    action: str          # "BUY" o "SELL"
    trend_direction: float # +1.0 o -1.0
    volatility_atr_pct: float
    order_book_imbalance: float
    volume_delta: float
    entropy: float
    sentiment_score: float
    conviction: float

@dataclass
class TradeMemoryEpisode:
    id: str
    timestamp: float
    market_vector: Dict
    entry_price: float
    exit_price: float
    net_pnl: float
    pnl_pct: float
    outcome: str         # "WIN", "LOSS", "BREAK_EVEN"
    holding_time_seconds: float
    reflection: str

class EpisodicMemoryEngine:
    def __init__(self, memory_file: str = "data/episodic_memory.json"):
        self.memory_file = memory_file
        self.episodes: List[TradeMemoryEpisode] = []
        self._load_memory()

    def _load_memory(self):
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.episodes = [
                        TradeMemoryEpisode(
                            id=item['id'],
                            timestamp=item['timestamp'],
                            market_vector=item['market_vector'],
                            entry_price=item['entry_price'],
                            exit_price=item['exit_price'],
                            net_pnl=item['net_pnl'],
                            pnl_pct=item['pnl_pct'],
                            outcome=item['outcome'],
                            holding_time_seconds=item.get('holding_time_seconds', 0.0),
                            reflection=item.get('reflection', '')
                        )
                        for item in data
                    ]
                logger.info(f"🧠 [BANCO DE MEMORIA]: {len(self.episodes)} episodios cargados desde disco.")
            else:
                self.episodes = []
        except Exception as e:
            logger.error(f"Error cargando banco de memoria episódica: {e}")
            self.episodes = []

    def _save_memory(self):
        try:
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            data = [asdict(ep) for ep in self.episodes]
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando memoria episódica: {e}")

    def record_completed_trade(
        self,
        pos_id: str,
        vector: MarketVector,
        entry_price: float,
        exit_price: float,
        net_pnl: float,
        opened_at: float
    ):
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100.0 if vector.action == "BUY" else ((entry_price - exit_price) / entry_price) * 100.0
        outcome = "WIN" if net_pnl > 0 else ("LOSS" if net_pnl < 0 else "BREAK_EVEN")
        duration = time.time() - opened_at

        if outcome == "LOSS":
            reflection = f"⚠️ Falló {vector.action} en {vector.symbol}. Causa: Desbalance ({vector.order_book_imbalance:+.2f}) o contratendencia ({vector.trend_direction:+.1f})."
        elif outcome == "WIN":
            reflection = f"✅ Éxito en {vector.action} {vector.symbol}. Sincronía flujo ({vector.volume_delta:+.2f}) y convicción ({vector.conviction:+.2f})."
        else:
            reflection = f"⚖️ Operación en {vector.action} {vector.symbol} cerrada en Break-Even."

        episode = TradeMemoryEpisode(
            id=pos_id,
            timestamp=time.time(),
            market_vector=asdict(vector),
            entry_price=entry_price,
            exit_price=exit_price,
            net_pnl=net_pnl,
            pnl_pct=pnl_pct,
            outcome=outcome,
            holding_time_seconds=duration,
            reflection=reflection
        )

        self.episodes.append(episode)
        if len(self.episodes) > 300:
            self.episodes = self.episodes[-300:]
        self._save_memory()
        logger.info(f"🧠 [NUEVO RECUERDO CONSOLIDADO]: {reflection} (PnL: ${net_pnl:+.2f})")

    def query_past_experience(
        self,
        current_vector: MarketVector,
        top_k: int = 5,
        similarity_threshold: float = 0.70
    ) -> Tuple[float, float, str]:
        if not self.episodes:
            return 1.0, 0.50, "🧠 Sin memoria previa suficiente: Procediendo con análisis base."

        v_curr = [
            current_vector.trend_direction,
            current_vector.volatility_atr_pct * 100.0,
            current_vector.order_book_imbalance,
            current_vector.volume_delta,
            current_vector.entropy,
            current_vector.sentiment_score
        ]

        scored_memories = []
        for ep in self.episodes:
            mv = ep.market_vector
            if mv.get('symbol') != current_vector.symbol or mv.get('action') != current_vector.action:
                continue

            v_past = [
                mv.get('trend_direction', 0.0),
                mv.get('volatility_atr_pct', 0.0) * 100.0,
                mv.get('order_book_imbalance', 0.0),
                mv.get('volume_delta', 0.0),
                mv.get('entropy', 0.5),
                mv.get('sentiment_score', 0.0)
            ]

            sim = self._cosine_similarity(v_curr, v_past)
            if sim >= similarity_threshold:
                scored_memories.append((sim, ep))

        if not scored_memories:
            return 1.0, 0.50, "🧠 Memoria consultada: Patrón novedoso, sin precedentes negativos."

        scored_memories.sort(key=lambda x: x[0], reverse=True)
        top_memories = scored_memories[:top_k]

        wins = sum(1 for _, ep in top_memories if ep.outcome == "WIN")
        losses = sum(1 for _, ep in top_memories if ep.outcome == "LOSS")
        total = len(top_memories)
        win_rate = wins / total if total > 0 else 0.5

        if losses > wins and losses >= 2:
            multiplier = 0.20
            insight = f"🚫 [MEMORIA VETA OPERACIÓN]: En {losses}/{total} situaciones idénticas previas en {current_vector.symbol} el resultado fue de pérdida. Reduciendo convicción."
        elif wins > losses and wins >= 2:
            multiplier = 1.20
            insight = f"💎 [MEMORIA VALIDA PATRÓN]: En {wins}/{total} situaciones análogas previas en {current_vector.symbol} el resultado fue ganador (+{win_rate:.0%}). Impulsando convicción."
        else:
            multiplier = 1.0
            insight = f"⚖️ [MEMORIA NEUTRAL]: Balance histórico mixto ({wins}W / {losses}L) en setups similares."

        return multiplier, win_rate, insight

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)
