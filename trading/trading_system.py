# trading/trading_system.py
import logging
from datetime import datetime

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)


class TradingSystem:
    def __init__(self, symbol, timeframe="1h", risk_percent=1, balance=1000):
        self.symbol = symbol.upper()
        self.timeframe = timeframe
        self.risk_percent = risk_percent
        self.balance = balance
        self.base_url = "https://api.binance.com/api/v3"

        # Настройки индикаторов
        self.rsi_period = 14
        self.short_sma = 5
        self.long_sma = 20
        self.min_volume = 1000
        self.min_volatility = 0.001
        self.max_volatility = 0.05

        logger.info(f"""
        =============== Initializing Trading System ===============
        Symbol: {self.symbol}
        Timeframe: {self.timeframe}
        Risk: {self.risk_percent}%
        Balance: ${self.balance}
        Min Volume: ${self.min_volume}
        Volatility Range: {self.min_volatility*100}% - {self.max_volatility*100}%
        ========================================================
        """)

    def get_historical_data(self, limit=100):
        """Получение исторических данных"""
        logger.info(f"Fetching historical data for {
                    self.symbol} ({limit} candles)")
        try:
            params = {
                "symbol": self.symbol,
                "interval": self.timeframe,
                "limit": limit
            }

            response = requests.get(f"{self.base_url}/klines", params=params)
            response.raise_for_status()
            data = response.json()

            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'trades',
                'taker_buy_base', 'taker_buy_quote', 'ignored'
            ])

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            logger.info(f"Successfully fetched {len(data)} candles")
            return df

        except Exception as e:
            logger.error(f"Failed to fetch historical data: {
                         str(e)}", exc_info=True)
            return None

    def calculate_indicators(self, df):
        """Расчет технических индикаторов"""
        logger.info(f"Calculating technical indicators for {self.symbol}")
        try:
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(
                window=self.rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)
                    ).rolling(window=self.rsi_period).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))

            # SMA
            df['sma_short'] = df['close'].rolling(window=self.short_sma).mean()
            df['sma_long'] = df['close'].rolling(window=self.long_sma).mean()

            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            df['bb_std'] = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
            df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']

            # Объемы
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']

            # ATR
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            tr = pd.concat([high_low, high_close, low_close],
                           axis=1).max(axis=1)
            df['atr'] = tr.rolling(window=14).mean()

            # Волатильность
            df['volatility'] = (df['high'] - df['low']) / df['low']

            latest = df.iloc[-1]
            logger.info(f"""
            Latest Indicator Values for {self.symbol}:
            RSI: {latest['rsi']:.2f}
            Short SMA: {latest['sma_short']:.2f}
            Long SMA: {latest['sma_long']:.2f}
            Volume Ratio: {latest['volume_ratio']:.2f}
            ATR: {latest['atr']:.2f}
            Volatility: {latest['volatility']*100:.2f}%
            """)

            return df

        except Exception as e:
            logger.error(f"Error calculating indicators: {
                         str(e)}", exc_info=True)
            return None

    def analyze_market_context(self, df):
        """Анализ рыночного контекста"""
        logger.info(f"Analyzing market context for {self.symbol}")
        try:
            latest = df.iloc[-1]

            context = {
                "trend": "undefined",
                "strength": 0,
                "volatility": "normal",
                "volume": "normal",
                "suitable_for_trading": False
            }

            # Определение тренда
            if latest['sma_short'] > latest['sma_long']:
                context['trend'] = "uptrend"
            elif latest['sma_short'] < latest['sma_long']:
                context['trend'] = "downtrend"

            # Сила тренда
            if 30 <= latest['rsi'] <= 70:
                context['strength'] = abs(latest['rsi'] - 50) / 20

            # Волатильность
            if latest['volatility'] < self.min_volatility:
                context['volatility'] = "low"
            elif latest['volatility'] > self.max_volatility:
                context['volatility'] = "high"

            # Объем
            if latest['volume_ratio'] > 1.5:
                context['volume'] = "high"
            elif latest['volume_ratio'] < 0.5:
                context['volume'] = "low"

            # Оценка пригодности
            context['suitable_for_trading'] = (
                context['trend'] != "undefined" and
                context['volatility'] == "normal" and
                context['volume'] != "low" and
                latest['volume'] >= self.min_volume
            )

            logger.info(f"""
            Market Context Analysis for {self.symbol}:
            Trend: {context['trend']}
            Trend Strength: {context['strength']:.2f}
            Volatility: {context['volatility']}
            Volume Status: {context['volume']}
            Suitable for Trading: {context['suitable_for_trading']}
            """)

            return context

        except Exception as e:
            logger.error(f"Error analyzing market context: {
                         str(e)}", exc_info=True)
            return None

    def find_entry_points(self, df, context):
        """Поиск точек входа"""
        logger.info(f"Searching for entry points for {self.symbol}")
        try:
            latest = df.iloc[-1]
            signals = []

            if not context['suitable_for_trading']:
                logger.info(
                    "Market context not suitable for trading, skipping signal search")
                return signals

            if context['trend'] == "uptrend":
                # RSI отскок
                if latest['rsi'] > 30 and df.iloc[-2]['rsi'] <= 30:
                    signal = {
                        "type": "long",
                        "strength": 0.8,
                        "reason": "RSI bounce from oversold",
                        "entry": latest['close'],
                        "stop_loss": latest['low'],
                        "take_profit": latest['close'] + (latest['close'] - latest['low']) * 2
                    }
                    logger.info(f"Found long signal: {signal}")
                    signals.append(signal)

                # Bollinger отскок
                if latest['close'] > latest['bb_lower'] and df.iloc[-2]['close'] <= df.iloc[-2]['bb_lower']:
                    signal = {
                        "type": "long",
                        "strength": 0.7,
                        "reason": "Bounce from BB lower",
                        "entry": latest['close'],
                        "stop_loss": latest['bb_lower'] * 0.99,
                        "take_profit": latest['bb_middle']
                    }
                    logger.info(f"Found long signal: {signal}")
                    signals.append(signal)

            elif context['trend'] == "downtrend":
                # RSI отскок
                if latest['rsi'] < 70 and df.iloc[-2]['rsi'] >= 70:
                    signal = {
                        "type": "short",
                        "strength": 0.8,
                        "reason": "RSI bounce from overbought",
                        "entry": latest['close'],
                        "stop_loss": latest['high'],
                        "take_profit": latest['close'] - (latest['high'] - latest['close']) * 2
                    }
                    logger.info(f"Found short signal: {signal}")
                    signals.append(signal)

                # Bollinger отскок
                if latest['close'] < latest['bb_upper'] and df.iloc[-2]['close'] >= df.iloc[-2]['bb_upper']:
                    signal = {
                        "type": "short",
                        "strength": 0.7,
                        "reason": "Bounce from BB upper",
                        "entry": latest['close'],
                        "stop_loss": latest['bb_upper'] * 1.01,
                        "take_profit": latest['bb_middle']
                    }
                    logger.info(f"Found short signal: {signal}")
                    signals.append(signal)

            logger.info(f"Found {len(signals)} potential signals")
            return signals

        except Exception as e:
            logger.error(f"Error finding entry points: {
                         str(e)}", exc_info=True)
            return []

    def analyze(self):
        """Основной метод анализа"""
        logger.info(
            f"\n{'='*50}\nStarting analysis for {self.symbol}\n{'='*50}")

        try:
            # Получение данных
            logger.info("Step 1: Fetching historical data")
            df = self.get_historical_data()
            if df is None or df.empty:
                return None

            # Расчет индикаторов
            logger.info("Step 2: Calculating technical indicators")
            df = self.calculate_indicators(df)
            if df is None:
                return None

            # Анализ контекста
            logger.info("Step 3: Analyzing market context")
            context = self.analyze_market_context(df)
            if context is None:
                return None

            # Поиск сигналов
            logger.info("Step 4: Searching for trading signals")
            signals = self.find_entry_points(df, context)

            result = {
                "timestamp": datetime.now(),
                "symbol": self.symbol,
                "context": context,
                "signals": signals,
                "latest_price": df.iloc[-1]['close'],
                "latest_volume": df.iloc[-1]['volume'],
            }

            return result

        except Exception as e:
            logger.error(f"Error in analysis: {str(e)}", exc_info=True)
            return None
