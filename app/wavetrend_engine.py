import pandas as pd
import numpy as np


class WaveTrendEngine:

    def __init__(self):
        self.df = pd.DataFrame()
        self.bull_count = 0
        self.bear_count = 0

    # ==========================
    # LOAD HISTORY
    # ==========================
    def load_history(self, candles):
        self.df = pd.DataFrame(candles, columns=[
            "timestamp", "open", "high", "low", "close", "volume"
        ])
        self.calculate()

    # ==========================
    # WAVETREND CALCULATION
    # ==========================
    def calculate(self):
        df = self.df

        ap = (df["high"] + df["low"] + df["close"]) / 3
        esa = ap.ewm(span=10, adjust=False).mean()
        d = abs(ap - esa).ewm(span=10, adjust=False).mean()
        ci = (ap - esa) / (0.015 * d)
        tci = ci.ewm(span=21, adjust=False).mean()

        df["wt1"] = tci
        df["wt2"] = df["wt1"].rolling(4).mean()

    # ==========================
    # REAL-TIME UPDATE (UNCHANGED LOGIC)
    # ==========================
    def update(self, new_candle):
        self.df.loc[len(self.df)] = new_candle
        self.calculate()

        if len(self.df) < 2:
            return None

        last = self.df.iloc[-1]
        prev = self.df.iloc[-2]

        bull = last.wt1 > last.wt2 and prev.wt1 <= prev.wt2
        bear = last.wt1 < last.wt2 and prev.wt1 >= prev.wt2

        if bull:
            self.bull_count += 1
            return {
                "type": "bullish",
                "count": self.bull_count,
                "price": float(last.close),
                "timestamp": int(last.timestamp)
            }

        if bear:
            self.bear_count += 1
            return {
                "type": "bearish",
                "count": self.bear_count,
                "price": float(last.close),
                "timestamp": int(last.timestamp)
            }

        return None

    # ==========================
    # NEW: GENERATE HISTORICAL SIGNALS
    # ==========================
    def generate_historical_signals(self, symbol, save_callback):
        """
        Loops through entire history and generates
        WaveTrend cross signals for past candles.
        Does NOT modify existing logic.
        """

        if len(self.df) < 2:
            return

        df = self.df

        for i in range(1, len(df)):

            prev = df.iloc[i - 1]
            curr = df.iloc[i]

            bull = curr.wt1 > curr.wt2 and prev.wt1 <= prev.wt2
            bear = curr.wt1 < curr.wt2 and prev.wt1 >= prev.wt2

            if bull:
                self.bull_count += 1

                save_callback({
                    "symbol": symbol,
                    "type": "bullish",
                    "count": self.bull_count,
                    "price": float(curr.close),
                    "timestamp": int(curr.timestamp)
                })

            if bear:
                self.bear_count += 1

                save_callback({
                    "symbol": symbol,
                    "type": "bearish",
                    "count": self.bear_count,
                    "price": float(curr.close),
                    "timestamp": int(curr.timestamp)
                })

    # ==========================
    # OPTIONAL: RESET ENGINE
    # ==========================
    def reset(self):
        """
        Safely reset engine state.
        Does not affect other logic.
        """
        self.df = pd.DataFrame()
        self.bull_count = 0
        self.bear_count = 0