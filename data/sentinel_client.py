import aiohttp
import asyncio
import time
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("SentinelClient")

class SentinelClient:
    """
    Cliente asíncrono para consumir las alertas de microestructura y ondas de choque
    del KuQuant SPIDERWEB SENTINEL (Puerto 8005) en tiempo real.
    """
    def __init__(self, sentinel_url: str = "http://localhost:8005/api/vibrations", timeout_ms: int = 400):
        self.sentinel_url = sentinel_url
        self.timeout = aiohttp.ClientTimeout(total=timeout_ms / 1000.0)
        self.last_known_vibrations: List[Dict] = []
        self.last_fetch_time: float = 0.0

    async def fetch_active_vibrations(self) -> List[Dict]:
        """
        Consulta las vibraciones activas de la tela de araña.
        Retorna la lista de eventos con antigüedad menor a 60 segundos.
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.sentinel_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        vibrations = data.get("vibrations", [])
                        now = time.time()
                        # Filtrar eventos recientes (<60s)
                        recent = [v for v in vibrations if (now - v.get("timestamp", 0)) <= 60.0]
                        self.last_known_vibrations = recent
                        self.last_fetch_time = now
                        return recent
        except Exception:
            # Si el Sentinel no responde o tiene lag, no bloquear el ciclo del bot
            pass
        return self.last_known_vibrations

    def evaluate_shockwave_decision(self, symbol: str, current_position_side: Optional[str], new_signal_action: Optional[str]) -> Dict:
        """
        Árbol de decisiones de onda de choque:
        1. CIERRE DE EMERGENCIA: Si hay choque en contra de posición abierta.
        2. VETO PREVENTIVO: Si hay choque en contra de una nueva señal.
        3. ENTRADA POR IMPULSO (ANTICIPACIÓN): Si hay inyección de volumen masivo a favor.
        """
        now = time.time()
        relevant = [v for v in self.last_known_vibrations if (now - v.get("timestamp", 0)) <= 45.0]
        
        base_sym = symbol.split('/')[0] if '/' in symbol else symbol
        
        # Filtrar choques que afecten directamente al activo o al líder macro (BTC)
        shocks = [v for v in relevant if v.get("source_symbol", "").startswith(base_sym) or v.get("source_symbol", "").startswith("BTC")]
        
        decision = {
            "emergency_close": False,
            "veto_entry": False,
            "shockwave_entry": None,  # "BUY", "SELL" o None
            "reason": ""
        }
        
        for shock in shocks:
            v_type = shock.get("vibration_type", "")
            z_vol = shock.get("z_score_volume", 0.0)
            src = shock.get("source_symbol", "")
            
            # 1. EVALUAR CIERRE DE EMERGENCIA
            if current_position_side == "LONG" and v_type in ["SHOCKWAVE_DUMP", "ORDER_BOOK_COLLAPSE"]:
                decision["emergency_close"] = True
                decision["reason"] = f"🕷️ [ALERTA SENTINEL] Onda de caída masiva detectada en {src} (Z-Score: {z_vol:.1f}). Cierre preventivo."
                return decision
            elif current_position_side == "SHORT" and v_type in ["SHOCKWAVE_PUMP"]:
                decision["emergency_close"] = True
                decision["reason"] = f"🕷️ [ALERTA SENTINEL] Onda de subida explosiva en {src} (Z-Score: {z_vol:.1f}). Cierre preventivo."
                return decision
                
            # 2. EVALUAR VETO PREVENTIVO DE NUEVA ENTRADA
            if new_signal_action == "BUY" and v_type in ["SHOCKWAVE_DUMP", "ORDER_BOOK_COLLAPSE"]:
                decision["veto_entry"] = True
                decision["reason"] = f"🚫 [VETO SENTINEL] Señal de compra cancelada por onda de choque bajista en {src}."
                return decision
            elif new_signal_action == "SELL" and v_type in ["SHOCKWAVE_PUMP"]:
                decision["veto_entry"] = True
                decision["reason"] = f"🚫 [VETO SENTINEL] Señal de venta cancelada por inyección compradora en {src}."
                return decision
                
            # 3. EVALUAR ENTRADA POR ANTICIPACIÓN (SHOCKWAVE MOMENTUM)
            if not current_position_side and z_vol >= 3.5:
                if v_type == "SHOCKWAVE_PUMP" and shock.get("imbalance_ratio", 0) > 0.20:
                    decision["shockwave_entry"] = "BUY"
                    decision["reason"] = f"⚡ [ANTICIPACIÓN SENTINEL] Impulso institucional detectado en {src} (Z-Score: {z_vol:.1f}). Disparando Long."
                    return decision
                elif v_type == "SHOCKWAVE_DUMP" and shock.get("imbalance_ratio", 0) < -0.20:
                    decision["shockwave_entry"] = "SELL"
                    decision["reason"] = f"⚡ [ANTICIPACIÓN SENTINEL] Venta masiva institucional en {src} (Z-Score: {z_vol:.1f}). Disparando Short."
                    return decision

        return decision
