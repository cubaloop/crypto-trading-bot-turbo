import json
import logging
import os
from typing import Dict, List, Any, Optional

logger = logging.getLogger("StatePersistenceTurbo")

STATE_FILE_PATH = os.path.join(os.path.dirname(__file__), "bot_state.json")

class StatePersistence:
    @staticmethod
    def save_state(balance_usd: float, initial_balance: float, positions: Dict[str, Any], trade_history: List[Dict], order_counter: int):
        try:
            positions_data = {}
            for sym, pos in positions.items():
                positions_data[sym] = {
                    "id": getattr(pos, "id", str(pos.get("id")) if isinstance(pos, dict) else ""),
                    "symbol": getattr(pos, "symbol", pos.get("symbol") if isinstance(pos, dict) else sym),
                    "side": getattr(pos, "side", pos.get("side") if isinstance(pos, dict) else "LONG"),
                    "entry_price": float(getattr(pos, "entry_price", pos.get("entry_price", 0.0) if isinstance(pos, dict) else 0.0)),
                    "units": float(getattr(pos, "units", pos.get("units", 0.0) if isinstance(pos, dict) else 0.0)),
                    "stop_loss": float(getattr(pos, "stop_loss", pos.get("stop_loss", 0.0) if isinstance(pos, dict) else 0.0)),
                    "take_profit": float(getattr(pos, "take_profit", pos.get("take_profit", 0.0) if isinstance(pos, dict) else 0.0)),
                    "take_profit_2": float(getattr(pos, "take_profit_2", pos.get("take_profit_2", 0.0) if isinstance(pos, dict) else 0.0)),
                    "highest_price": float(getattr(pos, "highest_price", pos.get("highest_price", 0.0) if isinstance(pos, dict) else 0.0)),
                    "lowest_price": float(getattr(pos, "lowest_price", pos.get("lowest_price", 0.0) if isinstance(pos, dict) else 0.0)),
                    "profit_lock_stage": int(getattr(pos, "profit_lock_stage", pos.get("profit_lock_stage", 0) if isinstance(pos, dict) else 0)),
                    "opened_at": float(getattr(pos, "opened_at", pos.get("opened_at", 0.0) if isinstance(pos, dict) else 0.0)),
                    "notional_usd": float(getattr(pos, "notional_usd", pos.get("notional_usd", 0.0) if isinstance(pos, dict) else 0.0))
                }

            state = {
                "balance_usd": balance_usd,
                "initial_balance": initial_balance,
                "order_counter": order_counter,
                "positions": positions_data,
                "trade_history": trade_history[-100:]
            }

            temp_path = STATE_FILE_PATH + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            os.replace(temp_path, STATE_FILE_PATH)
        except Exception as e:
            logger.error(f"Error guardando persistencia en disco: {e}")

    @staticmethod
    def load_state() -> Optional[Dict]:
        if not os.path.exists(STATE_FILE_PATH):
            return None
        try:
            with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"💾 Estado previo Turbo recuperado desde disco: Saldo ${data.get('balance_usd', 10000.0):,.2f} | {len(data.get('positions', {}))} posiciones.")
                return data
        except Exception as e:
            logger.error(f"Error leyendo persistencia en disco: {e}")
            return None
