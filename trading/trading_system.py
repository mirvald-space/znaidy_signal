# trading/trading_system.py
import logging
from datetime import datetime
from string import Template

import numpy as np
import pandas as pd
import requests

from utils.analytics_logger import AnalyticsLogger

logger = logging.getLogger(__name__)


class LogTemplates:
    # Initialization & Basic Info
    INIT = Template("Trading system initialized for $symbol")
    FETCH_DATA = Template(
        "Fetching historical data for $symbol ($limit candles)")
    FETCH_SUCCESS = Template("Successfully fetched $count candles")
    FETCH_ERROR = Template("Failed to fetch historical data: $error")
    CALC_INDICATORS = Template("Calculating technical indicators for $symbol")
    CALC_ERROR = Template("Error calculating indicators: $error")

    # Analysis Messages
    START_ANALYSIS = Template(
        "\n$separator\nStarting analysis for $symbol\n$separator")
    MARKET_CONTEXT = Template("\nАнализ рыночного контекста для $symbol")

    # Trend Analysis
    TREND_INFO = Template("Анализ тренда:")
    TREND_EMA = Template("- EMA тренд: $direction")
    TREND_PRICE_VWAP = Template("- Цена/VWAP: $position")
    TREND_PRICE_SMA = Template("- Цена/SMA: $position")
    TREND_DETERMINED = Template(
        "Определен $direction тренд (2+ подтверждения)")
    TREND_UNDEFINED = Template("Тренд не определен (противоречивые сигналы)")

    # Trend Strength
    TREND_STRENGTH = Template("\nСила тренда: $strength")
    TREND_EMA_DIFF = Template("- Разница EMA: $diff")
    TREND_MOMENTUM = Template("- Моментум цены: $momentum%")
    TREND_VOLUME = Template("- Влияние объема: $impact")

    # Volume Analysis
    VOLUME_STATUS = Template("\nОбъем $status ($change% от среднего)")

    # Volatility & Momentum
    VOLATILITY = Template("Волатильность $status ($change сигм от среднего)")
    MOMENTUM = Template("Моментум $status ($value%)")

    # Risk Assessment
    RISK_HIGH = Template("\nРИСК ВЫСОКИЙ: $factors")
    RISK_MEDIUM = Template("\nРИСК СРЕДНИЙ: $factors")
    RISK_LOW = Template("\nРИСК НИЗКИЙ: нет тревожных факторов")

    # Trading Conditions
    TRADE_CONDITIONS = Template("\nПРОВЕРКА УСЛОВИЙ ДЛЯ ТОРГОВЛИ:")
    CONDITION_CHECK = Template("✓ $condition: $status")
    TRADE_SUITABLE = Template("ИТОГ: ✅ Подходит для торговли")
    TRADE_UNSUITABLE = Template(
        "ИТОГ: ❌ Не подходит для торговли (не выполнено: $reasons)")

    # Signal Analysis
    SIGNAL_SEARCH = Template(
        "Searching for entry points and pre-signals for $symbol")
    MARKET_UNSUITABLE = Template(
        "$symbol: Market context not suitable for trading")
    CHECK_BUY = Template("$symbol: Проверка условий для покупки")
    CHECK_SELL = Template("$symbol: Проверка условий для продажи")
    RSI_STATUS = Template("$symbol: RSI текущий: $current, предыдущий: $prev")
    RSI_BOUNCE = Template("$symbol: Найден отскок RSI от $condition")
    BB_DISTANCE = Template(
        "$symbol: BB расстояние до $border границы: $distance%")
    BB_BOUNCE = Template("$symbol: Найден отскок от $border полосы BB")

    # Pre-signals and Final Results
    PRESIGNAL_FOUND = Template(
        "$symbol: Найден пре-сигнал $type, вероятность: $prob")
    SIGNAL_BOOST = Template("$symbol: Сигнал усилен: $boost_info")
    FINAL_SIGNALS = Template("$symbol: Итоговые $type сигналы:")
    SIGNAL_DETAIL = Template("  - $type: $reason, сила: $strength")
    PRESIGNAL_DETAIL = Template("  - $type: $reason, вероятность: $prob")
    FILTERED_COUNT = Template("$symbol: Отфильтровано $count слабых $type")
    SIGNALS_FOUND = Template(
        "Found $signal_count signals and $presignal_count pre-signals")

    # Error & Maintenance
    CLEANUP_SUCCESS = Template(
        "Successfully cleaned up data older than $days days")
    CLEANUP_ERROR = Template("Error during data cleanup: $error")
    CONTEXT_ERROR = Template("Ошибка анализа рыночного контекста: $error")
    ENTRY_ERROR = Template("Error finding entry points: $error")
    ANALYSIS_ERROR = Template("Error in analysis: $error")
    ANALYTICS_ERROR = Template("Error getting analytics: $error")


class SignalThresholds:
    # RSI уровни
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    RSI_PRE_OVERSOLD = (32, 45)
    RSI_PRE_OVERBOUGHT = (55, 68)

    # Bollinger Bands
    BB_DISTANCE_SIGNAL = 0.5
    BB_DISTANCE_PRE = 3.0
    BB_VOLUME_RATIO = 1.1

    # Фильтры сигналов
    MIN_SIGNAL_STRENGTH = 0.65
    MIN_PRESIGNAL_PROBABILITY = 0.4

    # Множители для корректировки
    VOLUME_BOOST = 1.2
    MOMENTUM_BOOST = 1.15
    TREND_STRENGTH_BOOST = 1.1
    VOLATILITY_PENALTY = 0.9


class TradingSystem:
    def __init__(self, symbol, timeframe="1h", risk_percent=1, balance=1000):
        if isinstance(symbol, (list, tuple)):
            symbol = symbol[0]
        self.symbol = str(symbol).strip('[]"\' ').upper()
        self.timeframe = timeframe
        self.risk_percent = risk_percent
        self.balance = balance
        self.base_url = "https://api.binance.com/api/v3"

        self.rsi_period = 14
        self.short_sma = 5
        self.long_sma = 20
        self.min_volume = 1000
        self.min_volatility = 0.001
        self.max_volatility = 0.05

        self.analytics_logger = AnalyticsLogger()
        logger.info(LogTemplates.INIT.substitute(symbol=self.symbol))

    def get_historical_data(self, limit=100):
        logger.info(LogTemplates.FETCH_DATA.substitute(
            symbol=self.symbol,
            limit=limit
        ))
        try:
            params = {
                "symbol": self.symbol,
                "interval": self.timeframe,
                "limit": limit
            }

            response = requests.get(
                "/".join([self.base_url, "klines"]), params=params)
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

            logger.info(LogTemplates.FETCH_SUCCESS.substitute(count=len(data)))
            return df

        except Exception as e:
            logger.error(LogTemplates.FETCH_ERROR.substitute(
                error=str(e)), exc_info=True)
            return None

    def calculate_indicators(self, df):
        logger.info(LogTemplates.CALC_INDICATORS.substitute(
            symbol=self.symbol))
        try:
            # RSI calculation
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(
                window=self.rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)
                    ).rolling(window=self.rsi_period).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))

            # Moving averages
            df['sma_short'] = df['close'].rolling(window=self.short_sma).mean()
            df['sma_long'] = df['close'].rolling(window=self.long_sma).mean()
            df['ema_short'] = df['close'].ewm(
                span=self.short_sma, adjust=False).mean()
            df['ema_long'] = df['close'].ewm(
                span=self.long_sma, adjust=False).mean()

            # Bollinger Bands
            df['bb_middle'] = df['close'].rolling(window=20).mean()
            df['bb_std'] = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
            df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']

            # Volume indicators
            df['volume_sma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma']
            df['vwap'] = (df['volume'] * (df['high'] + df['low'] +
                          df['close']) / 3).cumsum() / df['volume'].cumsum()

            # ATR calculation
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            tr = pd.concat([high_low, high_close, low_close],
                           axis=1).max(axis=1)
            df['atr'] = tr.rolling(window=14).mean()

            # Additional indicators
            df['momentum'] = df['close'] - df['close'].shift(4)
            df['momentum_pct'] = df['momentum'] / df['close'].shift(4) * 100
            df['volatility'] = df['close'].rolling(
                window=20).std() / df['close'].rolling(window=20).mean() * 100
            df['price_roc'] = (
                (df['close'] - df['close'].shift(10)) / df['close'].shift(10)) * 100

            return df

        except Exception as e:
            logger.error(LogTemplates.CALC_ERROR.substitute(
                error=str(e)), exc_info=True)
            return None

    def analyze_market_context(self, df):
        logger.info(LogTemplates.MARKET_CONTEXT.substitute(symbol=self.symbol))
        try:
            latest = df.iloc[-1]
            context = {
                "trend": "undefined",
                "strength": 0,
                "volatility": "normal",
                "volume": "normal",
                "momentum": "neutral",
                "suitable_for_trading": False,
                "risk_level": "medium"
            }

            # Trend analysis
            ema_trend = latest['ema_short'] > latest['ema_long']
            price_above_vwap = latest['close'] > latest['vwap']
            price_above_sma = latest['close'] > latest['sma_long']

            trend_score = sum([ema_trend, price_above_vwap, price_above_sma])

            logger.info(LogTemplates.TREND_INFO.substitute())
            logger.info(LogTemplates.TREND_EMA.substitute(
                direction='восходящий' if ema_trend else 'нисходящий'))
            logger.info(LogTemplates.TREND_PRICE_VWAP.substitute(
                position='выше' if price_above_vwap else 'ниже'))
            logger.info(LogTemplates.TREND_PRICE_SMA.substitute(
                position='выше' if price_above_sma else 'ниже'))

            if trend_score >= 2:
                context['trend'] = "uptrend"
                logger.info(LogTemplates.TREND_DETERMINED.substitute(
                    direction="ВОСХОДЯЩИЙ"))
            elif trend_score <= 1:
                context['trend'] = "downtrend"
                logger.info(LogTemplates.TREND_DETERMINED.substitute(
                    direction="НИСХОДЯЩИЙ"))
            else:
                logger.info(LogTemplates.TREND_UNDEFINED.substitute())

            # Trend strength calculation
            ema_diff = abs(latest['ema_short'] -
                           latest['ema_long']) / latest['ema_long']
            price_momentum = abs(latest['momentum_pct'])
            volume_impact = latest['volume_ratio'] - 1

            trend_strength = (
                ema_diff * 0.4 + price_momentum * 0.4 + volume_impact * 0.2)
            context['strength'] = min(trend_strength, 1)

            logger.info(LogTemplates.TREND_STRENGTH.substitute(
                strength="{:.2f}".format(context['strength'])))
            logger.info(LogTemplates.TREND_EMA_DIFF.substitute(
                diff="{:.2f}".format(ema_diff)))
            logger.info(LogTemplates.TREND_MOMENTUM.substitute(
                momentum="{:.2f}".format(price_momentum)))
            logger.info(LogTemplates.TREND_VOLUME.substitute(
                impact="{:.2f}".format(volume_impact)))

            # Volume analysis
            volume_change = (
                latest['volume'] - df['volume'].mean()) / df['volume'].mean() * 100
            if latest['volume_ratio'] > 1.5:
                context['volume'] = "high"
                logger.info(LogTemplates.VOLUME_STATUS.substitute(
                    status="ПОВЫШЕННЫЙ",
                    change="{:.1f}".format(volume_change)
                ))
            elif latest['volume_ratio'] < 0.5:
                context['volume'] = "low"
                logger.info(LogTemplates.VOLUME_STATUS.substitute(
                    status="ПОНИЖЕННЫЙ",
                    change="{:.1f}".format(volume_change)
                ))
            else:
                logger.info
            # Volatility analysis
            volatility_change = (
                latest['volatility'] - df['volatility'].mean()) / df['volatility'].std()

            if latest['volatility'] > self.max_volatility * 100:
                context['volatility'] = "high"
                logger.info(LogTemplates.VOLATILITY.substitute(
                    status="ВЫСОКАЯ",
                    change="{:.1f}".format(volatility_change)
                ))
            elif latest['volatility'] < self.min_volatility * 100:
                context['volatility'] = "low"
                logger.info(LogTemplates.VOLATILITY.substitute(
                    status="НИЗКАЯ",
                    change="{:.1f}".format(volatility_change)
                ))
            else:
                logger.info(LogTemplates.VOLATILITY.substitute(
                    status="НОРМАЛЬНАЯ",
                    change="{:.1f}".format(volatility_change)
                ))

            # Momentum analysis
            if latest['momentum_pct'] > 1.5:
                context['momentum'] = "strong_positive"
                logger.info(LogTemplates.MOMENTUM.substitute(
                    status="СИЛЬНЫЙ ПОЛОЖИТЕЛЬНЫЙ",
                    value="{:.1f}".format(latest['momentum_pct'])
                ))
            elif latest['momentum_pct'] > 0.5:
                context['momentum'] = "positive"
                logger.info(LogTemplates.MOMENTUM.substitute(
                    status="ПОЛОЖИТЕЛЬНЫЙ",
                    value="{:.1f}".format(latest['momentum_pct'])
                ))
            elif latest['momentum_pct'] < -1.5:
                context['momentum'] = "strong_negative"
                logger.info(LogTemplates.MOMENTUM.substitute(
                    status="СИЛЬНЫЙ ОТРИЦАТЕЛЬНЫЙ",
                    value="{:.1f}".format(latest['momentum_pct'])
                ))
            elif latest['momentum_pct'] < -0.5:
                context['momentum'] = "negative"
                logger.info(LogTemplates.MOMENTUM.substitute(
                    status="ОТРИЦАТЕЛЬНЫЙ",
                    value="{:.1f}".format(latest['momentum_pct'])
                ))
            else:
                logger.info(LogTemplates.MOMENTUM.substitute(
                    status="НЕЙТРАЛЬНЫЙ",
                    value="{:.1f}".format(latest['momentum_pct'])
                ))

            # Risk assessment
            risk_factors = []
            if context['volatility'] == "high":
                risk_factors.append("высокая волатильность")
            if abs(latest['price_roc']) > 5:
                risk_factors.append(
                    "сильное движение цены (ROC: {:.1f}%)".format(latest['price_roc']))
            if latest['volume_ratio'] > 2:
                risk_factors.append(
                    "аномальный объем (x{:.1f})".format(latest['volume_ratio']))

            if len(risk_factors) >= 2:
                context['risk_level'] = "high"
                logger.info(LogTemplates.RISK_HIGH.substitute(
                    factors=", ".join(risk_factors)))
            elif not risk_factors:
                context['risk_level'] = "low"
                logger.info(LogTemplates.RISK_LOW.substitute())
            else:
                logger.info(LogTemplates.RISK_MEDIUM.substitute(
                    factors=", ".join(risk_factors)))

            # Trading suitability assessment
            requirements = {
                "trend_defined": context['trend'] != "undefined",
                "min_volume": latest['volume'] >= self.min_volume * 0.5,
                "normal_risk": context['risk_level'] != "high"
            }

            context['suitable_for_trading'] = all(requirements.values())

            logger.info(LogTemplates.TRADE_CONDITIONS.substitute())
            for condition, status in requirements.items():
                logger.info(LogTemplates.CONDITION_CHECK.substitute(
                    condition=condition,
                    status=status
                ))

            if context['suitable_for_trading']:
                logger.info(LogTemplates.TRADE_SUITABLE.substitute())
            else:
                failed = [k for k, v in requirements.items() if not v]
                logger.info(LogTemplates.TRADE_UNSUITABLE.substitute(
                    reasons=", ".join(failed)
                ))

            return context

        except Exception as e:
            logger.error(LogTemplates.CONTEXT_ERROR.substitute(
                error=str(e)), exc_info=True)
            return None

    def find_entry_points(self, df, context):
        logger.info(LogTemplates.SIGNAL_SEARCH.substitute(symbol=self.symbol))
        try:
            latest = df.iloc[-1]
            signals = []
            pre_signals = []

            if not context['suitable_for_trading']:
                logger.info(LogTemplates.MARKET_UNSUITABLE.substitute(
                    symbol=self.symbol))
                return {"signals": signals, "pre_signals": pre_signals}

            # Analysis for uptrend
            if context['trend'] == "uptrend":
                logger.info(LogTemplates.CHECK_BUY.substitute(
                    symbol=self.symbol))
                logger.info(LogTemplates.RSI_STATUS.substitute(
                    symbol=self.symbol,
                    current="{:.2f}".format(latest['rsi']),
                    prev="{:.2f}".format(df.iloc[-2]['rsi'])
                ))

                # RSI signals for uptrend
                if latest['rsi'] > 30 and df.iloc[-2]['rsi'] <= 30:
                    entry = latest['close']
                    stop_loss = min(df.tail(3)['low']) * 0.998
                    take_profit = entry + (entry - stop_loss) * 2

                    logger.info(LogTemplates.RSI_BOUNCE.substitute(
                        symbol=self.symbol,
                        condition="перепроданности"
                    ))

                    signals.append({
                        "type": "long",
                        "strength": 0.8,
                        "reason": "RSI отскок от перепроданности",
                        "entry": entry,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "position_size": self.calculate_position_size(entry, stop_loss),
                        "indicators": {
                            "rsi": latest['rsi'],
                            "rsi_prev": df.iloc[-2]['rsi'],
                            "volume_ratio": latest['volume_ratio']
                        }
                    })

                # Pre-signals for uptrend
                elif 32 < latest['rsi'] < 45:
                    probability = 0.4 + ((45 - latest['rsi']) / 13) * 0.3

                    if probability >= SignalThresholds.MIN_PRESIGNAL_PROBABILITY:
                        pre_signals.append({
                            "type": "potential_long",
                            "reason": "RSI в зоне предварительного сигнала на покупку",
                            "current_price": latest['close'],
                            "probability": probability,
                            "indicators": {
                                "rsi": latest['rsi'],
                                "volume_ratio": latest['volume_ratio']
                            }
                        })

                        logger.info(LogTemplates.PRESIGNAL_FOUND.substitute(
                            symbol=self.symbol,
                            type="RSI",
                            prob="{:.2f}".format(probability)
                        ))

            # Analysis for downtrend
            elif context['trend'] == "downtrend":
                logger.info(LogTemplates.CHECK_SELL.substitute(
                    symbol=self.symbol))

                # RSI signals for downtrend
                if latest['rsi'] < 70 and df.iloc[-2]['rsi'] >= 70:
                    entry = latest['close']
                    stop_loss = max(df.tail(3)['high']) * 1.002
                    take_profit = entry - (stop_loss - entry) * 2

                    logger.info(LogTemplates.RSI_BOUNCE.substitute(
                        symbol=self.symbol,
                        condition="перекупленности"
                    ))

                    signals.append({
                        "type": "short",
                        "strength": 0.8,
                        "reason": "RSI отскок от перекупленности",
                        "entry": entry,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "position_size": self.calculate_position_size(entry, stop_loss),
                        "indicators": {
                            "rsi": latest['rsi'],
                            "rsi_prev": df.iloc[-2]['rsi'],
                            "volume_ratio": latest['volume_ratio']
                        }
                    })

                # Pre-signals for downtrend
                elif 55 < latest['rsi'] < 68:
                    probability = 0.4 + ((latest['rsi'] - 55) / 13) * 0.3

                    if probability >= SignalThresholds.MIN_PRESIGNAL_PROBABILITY:
                        pre_signals.append({
                            "type": "potential_short",
                            "reason": "RSI в зоне предварительного сигнала на продажу",
                            "current_price": latest['close'],
                            "probability": probability,
                            "indicators": {
                                "rsi": latest['rsi'],
                                "volume_ratio": latest['volume_ratio']
                            }
                        })

                        logger.info(LogTemplates.PRESIGNAL_FOUND.substitute(
                            symbol=self.symbol,
                            type="RSI",
                            prob="{:.2f}".format(probability)
                        ))

            # Signal strength adjustments
            for signal in signals:
                if latest['volume_ratio'] > SignalThresholds.BB_VOLUME_RATIO:
                    signal['strength'] *= SignalThresholds.VOLUME_BOOST
                if context['momentum'] in ['strong_positive', 'strong_negative']:
                    signal['strength'] *= SignalThresholds.MOMENTUM_BOOST
                if context['strength'] > 0.3:
                    signal['strength'] *= SignalThresholds.TREND_STRENGTH_BOOST
                if context['volatility'] == 'high':
                    signal['strength'] *= SignalThresholds.VOLATILITY_PENALTY

            # Filter signals
            filtered_signals = [
                s for s in signals if s['strength'] >= SignalThresholds.MIN_SIGNAL_STRENGTH]
            filtered_pre_signals = [
                s for s in pre_signals if s['probability'] >= SignalThresholds.MIN_PRESIGNAL_PROBABILITY]

            # Log results
            for signal in filtered_signals:
                logger.info(LogTemplates.SIGNAL_DETAIL.substitute(
                    type=signal['type'].upper(),
                    reason=signal['reason'],
                    strength="{:.2f}".format(signal['strength'])
                ))

            for pre_signal in filtered_pre_signals:
                logger.info(LogTemplates.PRESIGNAL_DETAIL.substitute(
                    type=pre_signal['type'].upper(),
                    reason=pre_signal['reason'],
                    prob="{:.2f}".format(pre_signal['probability'])
                ))

            logger.info(LogTemplates.SIGNALS_FOUND.substitute(
                signal_count=len(filtered_signals),
                presignal_count=len(filtered_pre_signals)
            ))

            return {
                "signals": filtered_signals,
                "pre_signals": filtered_pre_signals
            }

        except Exception as e:
            logger.error(LogTemplates.ENTRY_ERROR.substitute(
                error=str(e)), exc_info=True)
            return {"signals": [], "pre_signals": []}

    def analyze(self):
        logger.info(LogTemplates.START_ANALYSIS.substitute(
            separator="="*50,
            symbol=self.symbol
        ))

        try:
            df = self.get_historical_data()
            if df is None or df.empty:
                return None

            df = self.calculate_indicators(df)
            if df is None:
                return None

            context = self.analyze_market_context(df)
            if context is None:
                return None

            entry_points = self.find_entry_points(df, context)

            result = {
                "timestamp": datetime.now(),
                "symbol": self.symbol,
                "context": context,
                "signals": entry_points["signals"],
                "pre_signals": entry_points["pre_signals"],
                "latest_price": df.iloc[-1]['close'],
                "latest_volume": df.iloc[-1]['volume'],
                "indicators": {
                    "rsi": df.iloc[-1]['rsi'],
                    "sma_short": df.iloc[-1]['sma_short'],
                    "sma_long": df.iloc[-1]['sma_long'],
                    "ema_short": df.iloc[-1]['ema_short'],
                    "ema_long": df.iloc[-1]['ema_long'],
                    "bb_upper": df.iloc[-1]['bb_upper'],
                    "bb_lower": df.iloc[-1]['bb_lower'],
                    "volume_ratio": df.iloc[-1]['volume_ratio'],
                    "atr": df.iloc[-1]['atr'],
                    "momentum": df.iloc[-1]['momentum'],
                    "price_roc": df.iloc[-1]['price_roc'],
                    "volatility": df.iloc[-1]['volatility'],
                    "vwap": df.iloc[-1]['vwap']
                }
            }

            self.analytics_logger.log_market_data(result)
            return result

        except Exception as e:
            logger.error(LogTemplates.ANALYSIS_ERROR.substitute(
                error=str(e)), exc_info=True)
            return None

    def cleanup_old_data(self, days_to_keep=30):
        try:
            self.analytics_logger.cleanup_old_data(days_to_keep)
            logger.info(LogTemplates.CLEANUP_SUCCESS.substitute(
                days=days_to_keep))
        except Exception as e:
            logger.error(LogTemplates.CLEANUP_ERROR.substitute(
                error=str(e)), exc_info=True)

    def get_analytics(self, days=7):
        try:
            return {
                "signal_stats": self.analytics_logger.get_signal_statistics(days),
                "market_stats": self.analytics_logger.get_market_statistics(days),
                "symbol": self.symbol,
                "timeframe": self.timeframe
            }
        except Exception as e:
            logger.error(LogTemplates.ANALYTICS_ERROR.substitute(
                error=str(e)), exc_info=True)
            return None
