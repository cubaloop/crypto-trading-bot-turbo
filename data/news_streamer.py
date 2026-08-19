import asyncio
import logging
import time
import random
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger("NewsStreamerTurbo")

@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    timestamp: float
    symbol: Optional[str] = None
    sentiment_score: float = 0.0
    confidence: float = 0.5
    event_category: str = "GENERAL"

class NewsStreamer:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.mock_events = [
            ("Bitcoin institutional inflows reach new all-time high this quarter", "BTC", 0.75, 0.80, "GENERAL"),
            ("SEC approves new Ethereum staking framework and ETF listings", "ETH", 0.75, 0.85, "LISTING"),
            ("Solana network daily active addresses surge 45% following DeFi expansion", "SOL", 0.62, 0.70, "GENERAL"),
            ("Whale wallet accumulates 10,000 BTC from major exchange", "BTC", 0.65, 0.75, "GENERAL"),
            ("Major exchange halts SOL withdrawals temporarily due to node maintenance", "SOL", -0.45, 0.75, "EXCHANGE"),
            ("Federal Reserve announces rate cuts amid cooling inflation data", "BTC", 0.85, 0.90, "MACRO"),
            ("Minor vulnerability patched on secondary testnet cross-bridge", "ETH", 0.00, 0.40, "NEUTRAL"),
            ("US Treasury releases comprehensive digital assets regulatory clarification", None, 0.00, 0.40, "NEUTRAL"),
            ("Macro liquidity index expands globally across major central banks", "BTC", -0.85, 0.90, "REGULATORY"),
        ]
        self.cursor_idx = 0

    async def fetch_latest_news(self) -> List[NewsItem]:
        news = []
        now = time.time()
        title, sym, score, conf, cat = self.mock_events[self.cursor_idx % len(self.mock_events)]
        self.cursor_idx += 1
        
        item = NewsItem(
            title=title,
            source="CryptoPanic / Bloomberg Terminal",
            url="https://cryptopanic.com",
            timestamp=now,
            symbol=sym,
            sentiment_score=score,
            confidence=conf,
            event_category=cat
        )
        news.append(item)
        return news
