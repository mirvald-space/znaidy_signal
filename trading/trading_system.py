# trading/trading_system.py
import logging
from datetime import datetime

import numpy as np
import pandas as pd
import requests

from utils.analytics_logger import AnalyticsLogger

logger = logging.getLogger(__name__)

# Обновляем константы для поиска сигналов


class SignalThresholds:
    # RSI уровни
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    # Расширенный диапазон для пре-сигналов на покупку
    RSI_PRE_OVERSOLD = (32, 45)
    # Расширенный диапазон для пре-сигналов на продажу
    RSI_PRE_OVERBOUGHT = (55, 68)

    # Bollinger Bands
    BB_DISTANCE_SIGNAL = 0.5  # % расстояния для основного сигнала
    BB_DISTANCE_PRE = 3.0  # % расстояния для пре-сигнала
    BB_VOLUME_RATIO = 1.1  # Минимальный коэффициент объёма

    # Фильтры сигналов
    MIN_SIGNAL_STRENGTH = 0.65  # Минимальная сила основного сигнала
    MIN_PRESIGNAL_PROBABILITY = 0.4  # Минимальная вероятность пре-сигнала

    # Множители для корректировки
    VOLUME_BOOST = 1.2  # Усиление при высоком объеме
    MOMENTUM_BOOST = 1.15  # Усиление при подтверждении моментумом
    TREND_STRENGTH_BOOST = 1.1  # Усиление при сильном тренде
    VOLATILITY_PENALTY = 0.9  # Штраф за высокую волатильность


class TradingSystem:
    def __init__(self, symbol, timeframe="1h", risk_percent=1, balance=1000):
        """
        Инициализация торговой системы
        Args:
            symbol: Торговый символ (пара)
            timeframe: Таймфрейм для анализа
            risk_percent: Процент риска на сделку
            balance: Баланс счета
        """
        # Проверяем и очищаем символ от лишних символов
        if isinstance(symbol, (list, tuple)):
            symbol = symbol[0]
        self.symbol = str(symbol).strip('[]"\' ').upper()
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

        # Инициализация логгера аналитики
        self.analytics_logger = AnalyticsLogger()

        logger.info(f"Trading system initialized for {self.symbol}")

    def get_historical_data(self, limit=100):
        """
        Получение исторических данных с биржи
        Args:
            limit: Количество свечей
        Returns:
            pd.DataFrame: Датафрейм с историческими данными
        """
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

            # Преобразуем типы данных
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
        """
        Расчет технических индикаторов
        Args:
            df: DataFrame с историческими данными
        Returns:
            pd.DataFrame: DataFrame с добавленными индикаторами
        """
        logger.info(f"Calculating indicators for {self.symbol}")
        try:
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(
                window=self.rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)
                    ).rolling(window=self.rsi_period).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))

            # Moving Averages
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

            # Volume Weighted Average Price (VWAP)
            df['vwap'] = (df['volume'] * (df['high'] + df['low'] +
                          df['close']) / 3).cumsum() / df['volume'].cumsum()

            # Average True Range (ATR)
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            tr = pd.concat([high_low, high_close, low_close],
                           axis=1).max(axis=1)
            df['atr'] = tr.rolling(window=14).mean()

            # Momentum
            df['momentum'] = df['close'] - df['close'].shift(4)
            df['momentum_pct'] = df['momentum'] / df['close'].shift(4) * 100

            # Volatility
            df['volatility'] = df['close'].rolling(
                window=20).std() / df['close'].rolling(window=20).mean() * 100

            # Price Rate of Change (ROC)
            df['price_roc'] = (
                (df['close'] - df['close'].shift(10)) / df['close'].shift(10)) * 100

            return df

        except Exception as e:
            logger.error(f"Error calculating indicators: {
                         str(e)}", exc_info=True)
            return None

    def analyze_market_context(self, df):
        """
        Анализ рыночного контекста
        Args:
            df: DataFrame с индикаторами
        Returns:
            dict: Словарь с результатами анализа контекста
        """
        logger.info(f"\nАнализ рыночного контекста для {self.symbol}")
        try:
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            context = {
                "trend": "undefined",
                "strength": 0,
                "volatility": "normal",
                "volume": "normal",
                "momentum": "neutral",
                "suitable_for_trading": False,
                "risk_level": "medium"
            }

            # 1. Определение тренда
            ema_trend = latest['ema_short'] > latest['ema_long']
            price_above_vwap = latest['close'] > latest['vwap']
            price_above_sma = latest['close'] > latest['sma_long']

            trend_score = 0
            if ema_trend:
                trend_score += 1
            if price_above_vwap:
                trend_score += 1
            if price_above_sma:
                trend_score += 1

            logger.info(f"Анализ тренда:")
            logger.info(
                f"- EMA тренд: {'восходящий' if ema_trend else 'нисходящий'}")
            logger.info(
                f"- Цена/VWAP: {'выше' if price_above_vwap else 'ниже'}")
            logger.info(f"- Цена/SMA: {'выше' if price_above_sma else 'ниже'}")

            if trend_score >= 2:
                context['trend'] = "uptrend"
                logger.info("Определен ВОСХОДЯЩИЙ тренд (2+ подтверждения)")
            elif trend_score <= 1:
                context['trend'] = "downtrend"
                logger.info("Определен НИСХОДЯЩИЙ тренд (2+ подтверждения)")
            else:
                logger.info("Тренд не определен (противоречивые сигналы)")

            # 2. Сила тренда
            ema_diff = abs(latest['ema_short'] -
                           latest['ema_long']) / latest['ema_long']
            price_momentum = abs(latest['momentum_pct'])
            volume_impact = latest['volume_ratio'] - 1

            trend_strength = (
                ema_diff * 0.4 + price_momentum * 0.4 + volume_impact * 0.2)
            context['strength'] = min(trend_strength, 1)

            logger.info(f"\nСила тренда: {context['strength']:.2f}")
            logger.info(f"- Разница EMA: {ema_diff:.2f}")
            logger.info(f"- Моментум цены: {price_momentum:.2f}%")
            logger.info(f"- Влияние объема: {volume_impact:.2f}")

            # 3. Анализ объема
            avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
            volume_change = (latest['volume'] - avg_volume) / avg_volume * 100

            if latest['volume_ratio'] > 1.5:
                context['volume'] = "high"
                logger.info(
                    f"\nОбъем ПОВЫШЕННЫЙ (+{volume_change:.1f}% от среднего)")
            elif latest['volume_ratio'] < 0.5:
                context['volume'] = "low"
                logger.info(
                    f"\nОбъем ПОНИЖЕННЫЙ ({volume_change:.1f}% от среднего)")
            else:
                logger.info(
                    f"\nОбъем НОРМАЛЬНЫЙ ({volume_change:.1f}% от среднего)")

            # 4. Анализ волатильности
            volatility_change = (
                latest['volatility'] - df['volatility'].mean()) / df['volatility'].std()

            if latest['volatility'] > self.max_volatility * 100:
                context['volatility'] = "high"
                logger.info(f"Волатильность ВЫСОКАЯ ({
                            volatility_change:.1f} сигм от среднего)")
            elif latest['volatility'] < self.min_volatility * 100:
                context['volatility'] = "low"
                logger.info(f"Волатильность НИЗКАЯ ({
                            volatility_change:.1f} сигм от среднего)")
            else:
                logger.info(f"Волатильность НОРМАЛЬНАЯ ({
                            volatility_change:.1f} сигм от среднего)")

            # 5. Анализ моментума
            mom_threshold_strong = 1.5
            mom_threshold_weak = 0.5

            if latest['momentum_pct'] > mom_threshold_strong:
                context['momentum'] = "strong_positive"
                logger.info(f"Моментум СИЛЬНЫЙ ПОЛОЖИТЕЛЬНЫЙ ({
                            latest['momentum_pct']:.1f}%)")
            elif latest['momentum_pct'] > mom_threshold_weak:
                context['momentum'] = "positive"
                logger.info(f"Моментум ПОЛОЖИТЕЛЬНЫЙ ({
                            latest['momentum_pct']:.1f}%)")
            elif latest['momentum_pct'] < -mom_threshold_strong:
                context['momentum'] = "strong_negative"
                logger.info(f"Моментум СИЛЬНЫЙ ОТРИЦАТЕЛЬНЫЙ ({
                            latest['momentum_pct']:.1f}%)")
            elif latest['momentum_pct'] < -mom_threshold_weak:
                context['momentum'] = "negative"
                logger.info(f"Моментум ОТРИЦАТЕЛЬНЫЙ ({
                            latest['momentum_pct']:.1f}%)")
            else:
                logger.info(f"Моментум НЕЙТРАЛЬНЫЙ ({
                            latest['momentum_pct']:.1f}%)")

            # 6. Оценка риска
            risk_factors = []

            if context['volatility'] == "high":
                risk_factors.append("высокая волатильность")
            if abs(latest['price_roc']) > 5:
                risk_factors.append(
                    f"сильное движение цены (ROC: {latest['price_roc']:.1f}%)")
            if latest['volume_ratio'] > 2:
                risk_factors.append(
                    f"аномальный объем (x{latest['volume_ratio']:.1f})")

            if len(risk_factors) >= 2:
                context['risk_level'] = "high"
                logger.info(f"\nРИСК ВЫСОКИЙ: {', '.join(risk_factors)}")
            elif not risk_factors:
                context['risk_level'] = "low"
                logger.info("\nРИСК НИЗКИЙ: нет тревожных факторов")
            else:
                logger.info(f"\nРИСК СРЕДНИЙ: {', '.join(risk_factors)}")

            # 7. Оценка пригодности для торговли
            requirements = {
                "trend_defined": context['trend'] != "undefined",
                "min_volume": latest['volume'] >= self.min_volume * 0.5,
                "normal_risk": context['risk_level'] != "high"
            }

            context['suitable_for_trading'] = all(requirements.values())

            logger.info("\nПРОВЕРКА УСЛОВИЙ ДЛЯ ТОРГОВЛИ:")
            logger.info(f"✓ Тренд определен: {requirements['trend_defined']}")
            logger.info(f"✓ Достаточный объем: {requirements['min_volume']}")
            logger.info(f"✓ Приемлемый риск: {requirements['normal_risk']}")

            if context['suitable_for_trading']:
                logger.info("ИТОГ: ✅ Подходит для торговли")
            else:
                failed = [k for k, v in requirements.items() if not v]
                logger.info(
                    f"ИТОГ: ❌ Не подходит для торговли (не выполнено: {', '.join(failed)})")

            return context

        except Exception as e:
            logger.error(f"Ошибка анализа рыночного контекста: {
                         str(e)}", exc_info=True)
            return None

    def calculate_position_size(self, entry_price, stop_loss):
        """
        Расчет размера позиции на основе риска
        Args:
            entry_price: Цена входа
            stop_loss: Уровень стоп-лосса
        Returns:
            float: Размер позиции
        """
        risk_amount = self.balance * (self.risk_percent / 100)
        price_risk = abs(entry_price - stop_loss)
        position_size = risk_amount / price_risk
        return position_size

    # Обновленные настройки для более чувствительного поиска сигналов

    def find_entry_points(self, df, context):
        """
        Поиск точек входа и предварительных сигналов
        Args:
            df: DataFrame с данными и индикаторами
            context: Словарь с рыночным контекстом
        Returns:
            dict: Словарь с сигналами и пре-сигналами
        """
        logger.info(
            f"Searching for entry points and pre-signals for {self.symbol}")
        try:
            latest = df.iloc[-1]
            signals = []
            pre_signals = []

            if not context['suitable_for_trading']:
                logger.info(
                    f"{self.symbol}: Market context not suitable for trading")
                return {"signals": signals, "pre_signals": pre_signals}

            # СИГНАЛЫ НА ПОКУПКУ
            if context['trend'] == "uptrend":
                logger.info(f"{self.symbol}: Проверка условий для покупки")

                # RSI сигналы
                logger.info(f"{self.symbol}: RSI текущий: {
                            latest['rsi']:.2f}, предыдущий: {df.iloc[-2]['rsi']:.2f}")

                # Основной сигнал RSI
                if latest['rsi'] > 30 and df.iloc[-2]['rsi'] <= 30:
                    logger.info(
                        f"{self.symbol}: Найден отскок RSI от перепроданности")
                    entry = latest['close']
                    stop_loss = min(df.tail(3)['low']) * 0.998
                    take_profit = entry + (entry - stop_loss) * 2

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

                # Пре-сигнал RSI
                elif 32 < latest['rsi'] < 45:  # Расширенный диапазон для пре-сигналов
                    probability = 0.4 + ((45 - latest['rsi']) / 13) * 0.3
                    logger.info(
                        f"{self.symbol}: Найден пре-сигнал RSI, вероятность: {probability:.2f}")
                    pre_signals.append({
                        "type": "potential_long",
                        "reason": "RSI в зоне предварительного сигнала на покупку",
                        "current_rsi": latest['rsi'],
                        "current_price": latest['close'],
                        "probability": probability,
                        "indicators": {
                            "rsi": latest['rsi'],
                            "rsi_prev": df.iloc[-2]['rsi'],
                            "volume_ratio": latest['volume_ratio']
                        }
                    })

                # Bollinger Bands сигналы
                bb_distance = (
                    latest['close'] - latest['bb_lower']) / latest['bb_lower'] * 100
                logger.info(f"{self.symbol}: BB расстояние до нижней границы: {
                            bb_distance:.2f}%")

                # Основной сигнал BB
                if (latest['close'] > latest['bb_lower'] and
                    df.iloc[-2]['close'] <= df.iloc[-2]['bb_lower'] and
                        latest['volume_ratio'] > 1.1):

                    logger.info(
                        f"{self.symbol}: Найден отскок от нижней полосы BB")
                    entry = latest['close']
                    stop_loss = latest['bb_lower'] * 0.99
                    take_profit = latest['bb_middle']

                    signals.append({
                        "type": "long",
                        "strength": 0.75,
                        "reason": "Отскок от нижней полосы Боллинджера с повышенным объемом",
                        "entry": entry,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "position_size": self.calculate_position_size(entry, stop_loss),
                        "indicators": {
                            "bb_distance": bb_distance,
                            "volume_ratio": latest['volume_ratio']
                        }
                    })

                # Пре-сигнал BB
                elif bb_distance < 3.0:  # Расстояние до нижней границы менее 3%
                    probability = 0.4 + (1 - bb_distance / 3.0) * 0.3

                    volume_note = ""
                    if latest['volume_ratio'] > 1.1:
                        probability *= 1.2
                        volume_note = " с повышенным объемом"

                    logger.info(
                        f"{self.symbol}: Найден пре-сигнал BB, вероятность: {probability:.2f}")
                    pre_signals.append({
                        "type": "potential_long",
                        "reason": f"Цена приближается к нижней границе Боллинджера{volume_note}",
                        "current_price": latest['close'],
                        "bb_lower": latest['bb_lower'],
                        "probability": probability,
                        "indicators": {
                            "bb_distance": bb_distance,
                            "volume_ratio": latest['volume_ratio']
                        }
                    })

            # СИГНАЛЫ НА ПРОДАЖУ
            elif context['trend'] == "downtrend":
                logger.info(f"{self.symbol}: Проверка условий для продажи")

                # RSI сигналы
                logger.info(f"{self.symbol}: RSI текущий: {
                            latest['rsi']:.2f}, предыдущий: {df.iloc[-2]['rsi']:.2f}")

                # Основной сигнал RSI
                if latest['rsi'] < 70 and df.iloc[-2]['rsi'] >= 70:
                    logger.info(
                        f"{self.symbol}: Найден отскок RSI от перекупленности")
                    entry = latest['close']
                    stop_loss = max(df.tail(3)['high']) * 1.002
                    take_profit = entry - (stop_loss - entry) * 2

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

                # Пре-сигнал RSI
                elif 55 < latest['rsi'] < 68:  # Расширенный диапазон для пре-сигналов
                    probability = 0.4 + ((latest['rsi'] - 55) / 13) * 0.3
                    logger.info(
                        f"{self.symbol}: Найден пре-сигнал RSI, вероятность: {probability:.2f}")
                    pre_signals.append({
                        "type": "potential_short",
                        "reason": "RSI в зоне предварительного сигнала на продажу",
                        "current_rsi": latest['rsi'],
                        "current_price": latest['close'],
                        "probability": probability,
                        "indicators": {
                            "rsi": latest['rsi'],
                            "rsi_prev": df.iloc[-2]['rsi'],
                            "volume_ratio": latest['volume_ratio']
                        }
                    })

                # Bollinger Bands сигналы
                bb_distance = (latest['bb_upper'] -
                               latest['close']) / latest['close'] * 100
                logger.info(f"{self.symbol}: BB расстояние до верхней границы: {
                            bb_distance:.2f}%")

                # Основной сигнал BB
                if (latest['close'] < latest['bb_upper'] and
                    df.iloc[-2]['close'] >= df.iloc[-2]['bb_upper'] and
                        latest['volume_ratio'] > 1.1):

                    logger.info(
                        f"{self.symbol}: Найден отскок от верхней полосы BB")
                    entry = latest['close']
                    stop_loss = latest['bb_upper'] * 1.01
                    take_profit = latest['bb_middle']

                    signals.append({
                        "type": "short",
                        "strength": 0.75,
                        "reason": "Отскок от верхней полосы Боллинджера с повышенным объемом",
                        "entry": entry,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "position_size": self.calculate_position_size(entry, stop_loss),
                        "indicators": {
                            "bb_distance": bb_distance,
                            "volume_ratio": latest['volume_ratio']
                        }
                    })

                # Пре-сигнал BB
                elif bb_distance < 3.0:
                    probability = 0.4 + (1 - bb_distance / 3.0) * 0.3

                    volume_note = ""
                    if latest['volume_ratio'] > 1.1:
                        probability *= 1.2
                        volume_note = " с повышенным объемом"

                    logger.info(
                        f"{self.symbol}: Найден пре-сигнал BB, вероятность: {probability:.2f}")
                    pre_signals.append({
                        "type": "potential_short",
                        "reason": f"Цена приближается к верхней границе Боллинджера{volume_note}",
                        "current_price": latest['close'],
                        "bb_upper": latest['bb_upper'],
                        "probability": probability,
                        "indicators": {
                            "bb_distance": bb_distance,
                            "volume_ratio": latest['volume_ratio']
                        }
                    })

            # Дополнительные факторы усиления сигналов
            for pre in pre_signals:
                boost_reasons = []
                base_probability = pre['probability']

                # Объем
                if latest['volume_ratio'] > 1.1:
                    pre['probability'] *= 1.2
                    boost_reasons.append(
                        f"объем x{latest['volume_ratio']:.1f}")

                # Моментум
                if ('long' in pre['type'] and context['momentum'] in ['positive', 'strong_positive']) or \
                   ('short' in pre['type'] and context['momentum'] in ['negative', 'strong_negative']):
                    pre['probability'] *= 1.15
                    boost_reasons.append(f"моментум {context['momentum']}")

                # Сила тренда
                if context['strength'] > 0.3:
                    pre['probability'] *= 1.1
                    boost_reasons.append(
                        f"сила тренда {context['strength']:.2f}")

                # Высокая волатильность снижает вероятность
                if context['volatility'] == 'high':
                    pre['probability'] *= 0.9
                    boost_reasons.append("высокая волатильность")

                # Обновляем причину сигнала
                if boost_reasons:
                    boost_info = f" [усилен: {', '.join(boost_reasons)}, вер. {
                        base_probability:.2f}->{pre['probability']:.2f}]"
                    pre['reason'] += boost_info
                    logger.info(f"{self.symbol}: Сигнал усилен: {boost_info}")

            # Фильтрация сигналов
            filtered_pre_signals = [
                s for s in pre_signals if s['probability'] >= 0.4]
            filtered_signals = [s for s in signals if s['strength'] >= 0.65]

            # Логируем результаты
            if filtered_signals:
                logger.info(f"{self.symbol}: Итоговые торговые сигналы:")
                for signal in filtered_signals:
                    logger.info(
                        f"  - {signal['type'].upper()}: {signal['reason']}, сила: {signal['strength']:.2f}")

                    # Логируем сигналы в аналитику
                    self.analytics_logger.log_signal(signal, {
                        "symbol": self.symbol,
                        "rsi": latest['rsi'],
                        "volume_ratio": latest['volume_ratio'],
                        "context": context
                    })

            if filtered_pre_signals:
                logger.info(f"{self.symbol}: Итоговые пре-сигналы:")
                for pre in filtered_pre_signals:
                    logger.info(
                        f"  - {pre['type'].upper()}: {pre['reason']}, вероятность: {pre['probability']:.2f}")

            # Отчет о фильтрации
            if len(pre_signals) > len(filtered_pre_signals):
                logger.info(f"{self.symbol}: Отфильтровано {
                            len(pre_signals) - len(filtered_pre_signals)} слабых пре-сигналов")
            if len(signals) > len(filtered_signals):
                logger.info(f"{self.symbol}: Отфильтровано {
                            len(signals) - len(filtered_signals)} слабых сигналов")

            logger.info(f"Found {len(filtered_signals)} signals and {
                        len(filtered_pre_signals)} pre-signals")
            return {"signals": filtered_signals, "pre_signals": filtered_pre_signals}

        except Exception as e:
            logger.error(f"Error finding entry points: {
                         str(e)}", exc_info=True)
            return {"signals": [], "pre_signals": []}

    def analyze(self):
        """
        Основной метод анализа
        Returns:
            dict: Результаты анализа
        """
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
            entry_points = self.find_entry_points(df, context)

            # Формируем результат
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

            # Логируем рыночные данные
            self.analytics_logger.log_market_data(result)

            return result

        except Exception as e:
            logger.error(f"Error in analysis: {str(e)}", exc_info=True)
            return None

    def cleanup_old_data(self, days_to_keep=30):
        """Очистка старых данных"""
        try:
            self.analytics_logger.cleanup_old_data(days_to_keep)
            logger.info(f"Successfully cleaned up data older than {
                        days_to_keep} days")
        except Exception as e:
            logger.error(f"Error during data cleanup: {str(e)}", exc_info=True)

    def get_analytics(self, days=7):
        """Получение аналитики по торговой паре"""
        try:
            return {
                "signal_stats": self.analytics_logger.get_signal_statistics(days),
                "market_stats": self.analytics_logger.get_market_statistics(days),
                "symbol": self.symbol,
                "timeframe": self.timeframe
            }
        except Exception as e:
            logger.error(f"Error getting analytics: {str(e)}", exc_info=True)
            return None
