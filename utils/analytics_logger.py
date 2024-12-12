# utils/analytics_logger.py
import csv
import json
import os
from datetime import datetime
from typing import Any, Dict

import pandas as pd


class AnalyticsLogger:
    def __init__(self, base_dir: str = "analytics"):
        self.base_dir = base_dir
        self.signals_file = f"{base_dir}/signals.csv"
        self.market_data_file = f"{base_dir}/market_data.csv"

        # Создаем директорию если её нет
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

        # Инициализируем файлы с заголовками если их нет
        self._init_files()

    def _init_files(self):
        """Инициализация файлов с заголовками"""
        # Заголовки для сигналов
        signals_headers = [
            'timestamp', 'symbol', 'signal_type', 'entry_price',
            'stop_loss', 'take_profit', 'signal_strength', 'reason',
            'rsi', 'volume_ratio', 'trend', 'trend_strength'
        ]

        # Заголовки для рыночных данных
        market_headers = [
            'timestamp', 'symbol', 'price', 'volume',
            'rsi', 'sma_short', 'sma_long', 'volume_ratio',
            'volatility', 'trend', 'trend_strength', 'suitable_for_trading'
        ]

        # Создаем файлы если их нет
        if not os.path.exists(self.signals_file):
            with open(self.signals_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(signals_headers)

        if not os.path.exists(self.market_data_file):
            with open(self.market_data_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(market_headers)

    def log_signal(self, signal_data: Dict[str, Any], market_context: Dict[str, Any]):
        """Логирование торгового сигнала"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        signal_row = {
            'timestamp': timestamp,
            'symbol': market_context['symbol'],
            'signal_type': signal_data['type'],
            'entry_price': signal_data['entry'],
            'stop_loss': signal_data['stop_loss'],
            'take_profit': signal_data['take_profit'],
            'signal_strength': signal_data['strength'],
            'reason': signal_data['reason'],
            'rsi': market_context.get('rsi', 0),
            'volume_ratio': market_context.get('volume_ratio', 0),
            'trend': market_context['context']['trend'],
            'trend_strength': market_context['context']['strength']
        }

        with open(self.signals_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=signal_row.keys())
            writer.writerow(signal_row)

    def log_market_data(self, analysis_result: Dict[str, Any]):
        """Логирование рыночных данных"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        market_row = {
            'timestamp': timestamp,
            'symbol': analysis_result['symbol'],
            'price': analysis_result['latest_price'],
            'volume': analysis_result['latest_volume'],
            'rsi': analysis_result.get('rsi', 0),
            'sma_short': analysis_result.get('sma_short', 0),
            'sma_long': analysis_result.get('sma_long', 0),
            'volume_ratio': analysis_result.get('volume_ratio', 0),
            'volatility': analysis_result['context'].get('volatility', 'normal'),
            'trend': analysis_result['context']['trend'],
            'trend_strength': analysis_result['context']['strength'],
            'suitable_for_trading': analysis_result['context']['suitable_for_trading']
        }

        with open(self.market_data_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=market_row.keys())
            writer.writerow(market_row)

    def get_signal_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Получение статистики по сигналам за период"""
        try:
            df = pd.read_csv(self.signals_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            # Фильтруем по последним дням
            recent_df = df[df['timestamp'] >
                           pd.Timestamp.now() - pd.Timedelta(days=days)]

            stats = {
                'total_signals': len(recent_df),
                'by_symbol': recent_df['symbol'].value_counts().to_dict(),
                'by_type': recent_df['signal_type'].value_counts().to_dict(),
                'avg_strength': recent_df['signal_strength'].mean(),
                'trends': recent_df['trend'].value_counts().to_dict()
            }

            return stats
        except Exception as e:
            return {'error': str(e)}

    def get_market_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Получение статистики по рыночным данным за период"""
        try:
            df = pd.read_csv(self.market_data_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            # Фильтруем по последним дням
            recent_df = df[df['timestamp'] >
                           pd.Timestamp.now() - pd.Timedelta(days=days)]

            stats = {
                'records_analyzed': len(recent_df),
                'trading_opportunities': recent_df['suitable_for_trading'].sum(),
                'avg_trend_strength': recent_df['trend_strength'].mean(),
                'trend_distribution': recent_df['trend'].value_counts().to_dict(),
                'volatility_distribution': recent_df['volatility'].value_counts().to_dict()
            }

            # Группировка по символам
            by_symbol = recent_df.groupby('symbol').agg({
                'price': ['mean', 'std'],
                'volume': 'mean',
                'suitable_for_trading': 'sum'
            }).to_dict()

            stats['by_symbol'] = by_symbol

            return stats
        except Exception as e:
            return {'error': str(e)}

    def cleanup_old_data(self, days_to_keep: int = 30):
        """Очистка старых данных"""
        try:
            for file in [self.signals_file, self.market_data_file]:
                df = pd.read_csv(file)
                df['timestamp'] = pd.to_datetime(df['timestamp'])

                # Оставляем только последние N дней
                df = df[df['timestamp'] > pd.Timestamp.now(
                ) - pd.Timedelta(days=days_to_keep)]

                # Перезаписываем файл
                df.to_csv(file, index=False)

        except Exception as e:
            print(f"Error during cleanup: {e}")
