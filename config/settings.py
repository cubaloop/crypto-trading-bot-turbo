import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    app_name: str = "KuQuant AI Turbo - 24/7 High-Frequency Momentum Scalper"
    environment: str = os.getenv("ENVIRONMENT", "production")
    mode: str = os.getenv("TRADING_MODE", "paper")
    
    # Exchange configuration
    exchange_id: str = os.getenv("EXCHANGE_ID", "kucoin")
    api_key: str = os.getenv("API_KEY", "")
    api_secret: str = os.getenv("API_SECRET", "")
    api_passphrase: str = os.getenv("API_PASSPHRASE", "")
    use_testnet: bool = os.getenv("USE_TESTNET", "false").lower() == "true"
    
    # Web server
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8001"))
    
    # Turbo Trading Parameters (Universo Multi-Par de Memecoins & Micro-Scalping de Alta Velocidad)
    symbols: List[str] = ["DOGE/USDT", "PEPE/USDT", "SHIB/USDT", "FLOKI/USDT", "BONK/USDT", "WIF/USDT"]
    timeframe: str = "1m"
    risk_per_trade_pct: float = 0.20  # ACTIVADO: 20% DE CAPITAL ASIGNADO
    max_daily_drawdown_pct: float = 0.05  # 5.0% circuit breaker
    initial_virtual_balance: float = 10000.0
    price_poll_interval_seconds: float = 0.4  # Ultra-rápido (400ms)
    
    # News & NLP parameters
    cryptopanic_api_key: str = os.getenv("CRYPTOPANIC_API_KEY", "")
    news_poll_interval_seconds: int = 15
    sentiment_half_life_minutes: float = 20.0
    
    class Config:
        env_file = ".env"
        extra = "allow"

config = Settings()
