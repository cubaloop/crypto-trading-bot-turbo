import time
import math
import logging
from typing import Dict, List, Tuple
import numpy as np

logger = logging.getLogger("MicrostructureTier1")

class VPINCalculator:
    """
    Volume-Synchronized Probability of Toxicity (Easley, López de Prado, O'Hara).
    Calcula la probabilidad de que el flujo de órdenes esté dominado por algoritmos informados (ballenas).
    """
    def __init__(self, bucket_size_usd: float = 25000.0, num_buckets: int = 20):
        self.bucket_size_usd = bucket_size_usd
        self.num_buckets = num_buckets
        self.current_buy_vol = 0.0
        self.current_sell_vol = 0.0
        self.buckets: List[float] = []  # Almacena |V_buy - V_sell| / V_total

    def update(self, price: float, volume_usd: float, is_buy: bool) -> float:
        if is_buy:
            self.current_buy_vol += volume_usd
        else:
            self.current_sell_vol += volume_usd

        bucket_total = self.current_buy_vol + self.current_sell_vol
        if bucket_total >= self.bucket_size_usd:
            imbalance = abs(self.current_buy_vol - self.current_sell_vol)
            self.buckets.append(imbalance / max(1.0, bucket_total))
            if len(self.buckets) > self.num_buckets:
                self.buckets.pop(0)
            self.current_buy_vol = 0.0
            self.current_sell_vol = 0.0

        vpin = float(np.mean(self.buckets)) if self.buckets else 0.20
        return vpin

class LiquidationTrapDetector:
    """
    Detector de Trampas de Liquidez y Cascadas de Liquidaciones.
    Detecta zonas de alta acumulación de Stop Loss de minoristas (Liquidity Pools).
    """
    def __init__(self, sweep_threshold_atr_mult: float = 1.8):
        self.sweep_threshold_atr_mult = sweep_threshold_atr_mult

    def detect_liquidity_sweep(self, current_price: float, recent_high: float, recent_low: float, atr: float, l2_imbalance: float) -> Tuple[bool, str]:
        """
        Retorna (is_sweep, direction_to_trade)
        Si el precio perforó el mínimo previo y el libro L2 absorbe agresivamente en compras -> Caza de Liquidaciones en LONG.
        """
        # Perforación bajista con absorción compradora inmediata
        if current_price < recent_low and l2_imbalance > +0.35:
            return True, "LONG_SWEEP"
        # Perforación alcista con absorción vendedora (bull trap)
        if current_price > recent_high and l2_imbalance < -0.35:
            return True, "SHORT_SWEEP"
        return False, "NONE"
