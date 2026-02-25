import pandas as pd

class WaveTrendEngine:

    def __init__(self):
        self.df = pd.DataFrame(columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ])
        self.bull_count = 0
        self.bear_count = 0

    def load_history(self, candles):

        self.df = pd.DataFrame(
            candles,
            columns=["timestamp","open","high","low","close","volume"]
        )

        self.calculate()
        self.generate_historical()

    def calculate(self):

        df = self.df

        ap = (df.high + df.low + df.close) / 3
        esa = ap.ewm(span=10, adjust=False).mean()
        d = abs(ap - esa).ewm(span=10, adjust=False).mean()

        # ✅ ZERO DIVISION PROTECTION (no logic change)
        denominator = 0.015 * d
        denominator = denominator.replace(0, 1e-10)

        ci = (ap - esa) / denominator
        tci = ci.ewm(span=21, adjust=False).mean()

        df["wt1"] = tci
        df["wt2"] = df["wt1"].rolling(4).mean()

    def generate_historical(self):

        for i in range(1, len(self.df)):

            prev = self.df.iloc[i - 1]
            curr = self.df.iloc[i]

            bull = curr.wt1 > curr.wt2 and prev.wt1 <= prev.wt2
            bear = curr.wt1 < curr.wt2 and prev.wt1 >= prev.wt2

            if bull:
                self.bull_count += 1
            if bear:
                self.bear_count += 1

    def update(self, new_candle):

        # ✅ SAFE APPEND (fix for pandas __setitem__ crash)
        new_row = pd.DataFrame(
            [new_candle],
            columns=["timestamp","open","high","low","close","volume"]
        )

        self.df = pd.concat([self.df, new_row], ignore_index=True)

        # Recalculate (same as your original logic)
        self.calculate()

        if len(self.df) < 2:
            return None

        prev = self.df.iloc[-2]
        curr = self.df.iloc[-1]

        bull = curr.wt1 > curr.wt2 and prev.wt1 <= prev.wt2
        bear = curr.wt1 < curr.wt2 and prev.wt1 >= prev.wt2

        if bull:
            self.bull_count += 1
            return {
                "type": "bullish",
                "price": float(curr.close),
                "timestamp": int(curr.timestamp)
            }

        if bear:
            self.bear_count += 1
            return {
                "type": "bearish",
                "price": float(curr.close),
                "timestamp": int(curr.timestamp)
            }

        return None
