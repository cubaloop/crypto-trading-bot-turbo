import math
import time
from typing import List, Tuple
from data.news_streamer import NewsItem

class SentimentAnalyzer:
    def __init__(self, half_life_minutes: float = 20.0):
        self.half_life_seconds = half_life_minutes * 60.0
        self.decay_lambda = math.log(2) / self.half_life_seconds

    def calculate_decayed_sentiment(self, news_history: List[NewsItem]) -> Tuple[float, float, bool]:
        if not news_history:
            return 0.0, 0.5, False

        now = time.time()
        weighted_score_sum = 0.0
        weight_sum = 0.0
        total_conf = 0.0
        has_black_swan = False

        for item in news_history:
            delta_t = max(0.0, now - item.timestamp)
            decay_factor = math.exp(-self.decay_lambda * delta_t)
            multiplier = 1.5 if item.event_category in ["HACK", "REGULATORY"] else 1.0

            if item.event_category == "HACK" or (item.event_category == "REGULATORY" and item.sentiment_score < -0.6):
                if delta_t < 1800:
                    has_black_swan = True

            effective_score = item.sentiment_score * multiplier
            w = item.confidence * decay_factor

            weighted_score_sum += effective_score * w
            weight_sum += w
            total_conf += item.confidence

        if weight_sum > 0:
            aggregated_score = weighted_score_sum / weight_sum
        else:
            aggregated_score = 0.0

        avg_conf = total_conf / len(news_history)
        decayed_score = max(-1.0, min(1.0, aggregated_score))
        return decayed_score, avg_conf, has_black_swan
