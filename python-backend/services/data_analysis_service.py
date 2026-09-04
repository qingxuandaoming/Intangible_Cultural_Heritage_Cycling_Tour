# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
import json
from collections import defaultdict, Counter
import re

class DataAnalysisService:
    """数据分析服务类"""
    
    def __init__(self, db=None, equipment_model=None, price_model=None):
        self.db = db
        self.Equipment = equipment_model
        self.EquipmentPrice = price_model
        self.analysis_cache = {}  # 分析结果缓存
        self.cache_timeout = 3600  # 缓存超时时间（秒）
    
    def analyze_equipment_trends(self, days: int = 30) -> Dict:
        """分析装备价格趋势"""
        try:
            db = self.db
            Equipment = self.Equipment
            EquipmentPrice = self.EquipmentPrice
            
            # 获取指定天数内的价格数据
            start_date = datetime.now() - timedelta(days=days)
            
            from app import EquipmentCategory
            price_data = db.session.query(
                EquipmentPrice.equipment_id,
                Equipment.name,
                EquipmentCategory.name.label('category'),
                EquipmentPrice.platform,
                EquipmentPrice.price,
                EquipmentPrice.created_at
            ).join(
                Equipment, EquipmentPrice.equipment_id == Equipment.id
            ).outerjoin(
                EquipmentCategory, Equipment.category_id == EquipmentCategory.id
            ).filter(
                EquipmentPrice.created_at >= start_date,
                EquipmentPrice.is_available == True
            ).all()
            
            if not price_data:
                return {'error': '没有找到价格数据'}
            
            # 转换为DataFrame
            df = pd.DataFrame([
                {
                    'equipment_id': row.equipment_id,
                    'name': row.name,
                    'category': row.category,
                    'platform': row.platform,
                    'price': float(row.price),
                    'date': str(row.created_at)[:10]
                }
                for row in price_data
            ])
            
            # 分析结果
            analysis = {
                'period': f'{days}天',
                'total_records': len(df),
                'categories': self._analyze_category_trends(df),
                'platforms': self._analyze_platform_trends(df),
                'price_ranges': self._analyze_price_ranges(df),
                'top_equipment': self._analyze_top_equipment(df),
                'daily_trends': self._analyze_daily_trends(df),
                'summary': self._generate_trend_summary(df)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"分析装备趋势失败: {str(e)}")
            return {'error': str(e)}
    
    def _analyze_category_trends(self, df: pd.DataFrame) -> Dict:
        """分析分类趋势"""
        category_stats = df.groupby('category').agg({
            'price': ['count', 'mean', 'min', 'max', 'std'],
            'equipment_id': 'nunique'
        }).round(2)
        
        category_trends = {}
        for category in category_stats.index:
            category_trends[category] = {
                'total_records': int(category_stats.loc[category, ('price', 'count')]),
                'unique_equipment': int(category_stats.loc[category, ('equipment_id', 'nunique')]),
                'avg_price': float(category_stats.loc[category, ('price', 'mean')]),
                'min_price': float(category_stats.loc[category, ('price', 'min')]),
                'max_price': float(category_stats.loc[category, ('price', 'max')]),
                'price_std': float(category_stats.loc[category, ('price', 'std')]) if not pd.isna(category_stats.loc[category, ('price', 'std')]) else 0
            }
        
        return category_trends
    
    def _analyze_platform_trends(self, df: pd.DataFrame) -> Dict:
        """分析平台趋势"""
        platform_stats = df.groupby('platform').agg({
            'price': ['count', 'mean', 'min', 'max'],
            'equipment_id': 'nunique'
        }).round(2)
        
        platform_trends = {}
        for platform in platform_stats.index:
            platform_trends[platform] = {
                'total_records': int(platform_stats.loc[platform, ('price', 'count')]),
                'unique_equipment': int(platform_stats.loc[platform, ('equipment_id', 'nunique')]),
                'avg_price': float(platform_stats.loc[platform, ('price', 'mean')]),
                'min_price': float(platform_stats.loc[platform, ('price', 'min')]),
                'max_price': float(platform_stats.loc[platform, ('price', 'max')])
            }
        
        return platform_trends
    
    def _analyze_price_ranges(self, df: pd.DataFrame) -> Dict:
        """分析价格区间分布"""
        price_ranges = {
            '0-100': (0, 100),
            '100-500': (100, 500),
            '500-1000': (500, 1000),
            '1000-2000': (1000, 2000),
            '2000-5000': (2000, 5000),
            '5000+': (5000, float('inf'))
        }
        
        range_stats = {}
        for range_name, (min_price, max_price) in price_ranges.items():
            if max_price == float('inf'):
                count = len(df[df['price'] >= min_price])
            else:
                count = len(df[(df['price'] >= min_price) & (df['price'] < max_price)])
            
            range_stats[range_name] = {
                'count': count,
                'percentage': round(count / len(df) * 100, 2) if len(df) > 0 else 0
            }
        
        return range_stats
    
    def _analyze_top_equipment(self, df: pd.DataFrame, top_n: int = 10) -> Dict:
        """分析热门装备"""
        # 按记录数量排序（表示关注度）
        equipment_popularity = df.groupby(['equipment_id', 'name']).size().reset_index(name='record_count')
        equipment_popularity = equipment_popularity.sort_values('record_count', ascending=False).head(top_n)
        
        # 按平均价格排序
        equipment_price = df.groupby(['equipment_id', 'name'])['price'].mean().reset_index()
        equipment_price = equipment_price.sort_values('price', ascending=False).head(top_n)
        
        return {
            'most_popular': [
                {
                    'equipment_id': int(row['equipment_id']),
                    'name': row['name'],
                    'record_count': int(row['record_count'])
                }
                for _, row in equipment_popularity.iterrows()
            ],
            'highest_priced': [
                {
                    'equipment_id': int(row['equipment_id']),
                    'name': row['name'],
                    'avg_price': round(float(row['price']), 2)
                }
                for _, row in equipment_price.iterrows()
            ]
        }
    
    def _analyze_daily_trends(self, df: pd.DataFrame) -> Dict:
        """分析每日趋势"""
        daily_stats = df.groupby('date').agg({
            'price': ['count', 'mean'],
            'equipment_id': 'nunique'
        }).round(2)
        
        daily_trends = []
        for date in daily_stats.index:
            daily_trends.append({
                'date': str(date),
                'record_count': int(daily_stats.loc[date, ('price', 'count')]),
                'avg_price': float(daily_stats.loc[date, ('price', 'mean')]),
                'unique_equipment': int(daily_stats.loc[date, ('equipment_id', 'nunique')])
            })
        
        return sorted(daily_trends, key=lambda x: x['date'])
    
    def _generate_trend_summary(self, df: pd.DataFrame) -> Dict:
        """生成趋势摘要"""
        total_equipment = df['equipment_id'].nunique()
        total_records = len(df)
        avg_price = df['price'].mean()
        price_std = df['price'].std()
        
        # 最受欢迎的分类
        popular_category = df['category'].value_counts().index[0] if len(df) > 0 else ''
        
        # 价格变化趋势（简单的线性回归）
        if len(df) > 1:
            df_sorted = df.sort_values('date')
            df_sorted['date_num'] = pd.to_datetime(df_sorted['date']).astype('int64') / 10**9
            correlation = np.corrcoef(df_sorted['date_num'], df_sorted['price'])[0, 1]
            
            if correlation > 0.1:
                price_trend = '上升'
            elif correlation < -0.1:
                price_trend = '下降'
            else:
                price_trend = '稳定'
        else:
            price_trend = '数据不足'
        
        return {
            'total_equipment': total_equipment,
            'total_records': total_records,
            'avg_price': round(avg_price, 2),
            'price_volatility': round(price_std, 2) if not pd.isna(price_std) else 0,
            'popular_category': popular_category,
            'price_trend': price_trend
        }
    
    def analyze_market_competition(self, category: str = None) -> Dict:
        """分析市场竞争情况"""
        try:
            db = self.db
            Equipment = self.Equipment
            EquipmentPrice = self.EquipmentPrice
            
            # 构建查询
            from app import EquipmentCategory
            query = db.session.query(
                Equipment.id,
                Equipment.name,
                Equipment.brand,
                EquipmentCategory.name.label('category'),
                EquipmentPrice.platform,
                EquipmentPrice.price,
                EquipmentPrice.seller_name
            ).join(
                EquipmentPrice, Equipment.id == EquipmentPrice.equipment_id
            ).outerjoin(
                EquipmentCategory, Equipment.category_id == EquipmentCategory.id
            ).filter(
                EquipmentPrice.is_available == True
            )
            
            if category:
                query = query.filter(EquipmentCategory.name == category)
            
            data = query.all()
            
            if not data:
                return {'error': '没有找到竞争数据'}
            
            # 转换为DataFrame
            df = pd.DataFrame([
                {
                    'equipment_id': row.id,
                    'name': row.name,
                    'brand': row.brand or '未知品牌',
                    'category': row.category,
                    'platform': row.platform,
                    'price': float(row.price),
                    'shop_name': row.seller_name or ''
                }
                for row in data
            ])
            
            analysis = {
                'category': category or '全部分类',
                'brand_competition': self._analyze_brand_competition(df),
                'platform_competition': self._analyze_platform_competition(df),
                'price_competition': self._analyze_price_competition(df),
                'market_concentration': self._analyze_market_concentration(df)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"分析市场竞争失败: {str(e)}")
            return {'error': str(e)}
    
    def _analyze_brand_competition(self, df: pd.DataFrame) -> Dict:
        """分析品牌竞争"""
        brand_stats = df.groupby('brand').agg({
            'price': ['count', 'mean', 'min', 'max'],
            'equipment_id': 'nunique'
        }).round(2)
        
        brand_competition = {}
        for brand in brand_stats.index:
            brand_competition[brand] = {
                'product_count': int(brand_stats.loc[brand, ('equipment_id', 'nunique')]),
                'price_records': int(brand_stats.loc[brand, ('price', 'count')]),
                'avg_price': float(brand_stats.loc[brand, ('price', 'mean')]),
                'min_price': float(brand_stats.loc[brand, ('price', 'min')]),
                'max_price': float(brand_stats.loc[brand, ('price', 'max')]),
                'market_share': round(brand_stats.loc[brand, ('equipment_id', 'nunique')] / df['equipment_id'].nunique() * 100, 2)
            }
        
        # 按市场份额排序
        sorted_brands = sorted(brand_competition.items(), key=lambda x: x[1]['market_share'], reverse=True)
        
        return {
            'total_brands': len(brand_competition),
            'brand_details': dict(sorted_brands),
            'top_3_brands': [brand for brand, _ in sorted_brands[:3]]
        }
    
    def _analyze_platform_competition(self, df: pd.DataFrame) -> Dict:
        """分析平台竞争"""
        platform_stats = df.groupby('platform').agg({
            'price': ['count', 'mean'],
            'equipment_id': 'nunique'
        }).round(2)
        
        platform_competition = {}
        for platform in platform_stats.index:
            platform_competition[platform] = {
                'product_count': int(platform_stats.loc[platform, ('equipment_id', 'nunique')]),
                'price_records': int(platform_stats.loc[platform, ('price', 'count')]),
                'avg_price': float(platform_stats.loc[platform, ('price', 'mean')]),
                'market_coverage': round(platform_stats.loc[platform, ('equipment_id', 'nunique')] / df['equipment_id'].nunique() * 100, 2)
            }
        
        return platform_competition
    
    def _analyze_price_competition(self, df: pd.DataFrame) -> Dict:
        """分析价格竞争"""
        # 同一商品在不同平台的价格差异
        price_comparison = []
        
        for equipment_id in df['equipment_id'].unique():
            equipment_data = df[df['equipment_id'] == equipment_id]
            if len(equipment_data) > 1:  # 有多个平台的价格
                equipment_name = equipment_data['name'].iloc[0]
                prices = equipment_data.groupby('platform')['price'].mean()
                
                if len(prices) > 1:
                    min_price = prices.min()
                    max_price = prices.max()
                    price_diff = max_price - min_price
                    price_diff_percent = (price_diff / min_price) * 100 if min_price > 0 else 0
                    
                    price_comparison.append({
                        'equipment_id': int(equipment_id),
                        'name': equipment_name,
                        'min_price': round(min_price, 2),
                        'max_price': round(max_price, 2),
                        'price_difference': round(price_diff, 2),
                        'price_difference_percent': round(price_diff_percent, 2),
                        'platforms': list(prices.index)
                    })
        
        # 按价格差异百分比排序
        price_comparison.sort(key=lambda x: x['price_difference_percent'], reverse=True)
        
        return {
            'total_comparable_products': len(price_comparison),
            'avg_price_difference_percent': round(np.mean([p['price_difference_percent'] for p in price_comparison]), 2) if price_comparison else 0,
            'top_price_differences': price_comparison[:10]
        }
    
    def _analyze_market_concentration(self, df: pd.DataFrame) -> Dict:
        """分析市场集中度"""
        # 计算HHI指数（赫芬达尔-赫希曼指数）
        brand_market_share = df.groupby('brand')['equipment_id'].nunique()
        total_products = df['equipment_id'].nunique()
        
        market_shares = (brand_market_share / total_products * 100).values
        hhi = sum(share ** 2 for share in market_shares)
        
        # 市场集中度判断
        if hhi < 1500:
            concentration_level = '低集中度'
        elif hhi < 2500:
            concentration_level = '中等集中度'
        else:
            concentration_level = '高集中度'
        
        # 计算CR4（前四大品牌市场份额）
        top_4_share = sum(sorted(market_shares, reverse=True)[:4])
        
        return {
            'hhi_index': round(hhi, 2),
            'concentration_level': concentration_level,
            'cr4_ratio': round(top_4_share, 2),
            'total_brands': len(market_shares)
        }
    
    def generate_price_alerts(self, price_change_threshold: float = 10.0) -> List[Dict]:
        """生成价格预警"""
        try:
            db = self.db
            Equipment = self.Equipment
            EquipmentPrice = self.EquipmentPrice
            
            # 获取最近7天的价格数据
            recent_date = datetime.now() - timedelta(days=7)
            older_date = datetime.now() - timedelta(days=14)
            
            # 获取最近价格
            recent_prices = db.session.query(
                EquipmentPrice.equipment_id,
                Equipment.name,
                EquipmentPrice.platform,
                EquipmentPrice.price,
                EquipmentPrice.created_at
            ).join(
                Equipment, EquipmentPrice.equipment_id == Equipment.id
            ).filter(
                EquipmentPrice.created_at >= recent_date,
                EquipmentPrice.is_available == True
            ).all()
            
            # 获取较早价格
            older_prices = db.session.query(
                EquipmentPrice.equipment_id,
                Equipment.name,
                EquipmentPrice.platform,
                EquipmentPrice.price,
                EquipmentPrice.created_at
            ).join(
                Equipment, EquipmentPrice.equipment_id == Equipment.id
            ).filter(
                EquipmentPrice.created_at >= older_date,
                EquipmentPrice.created_at < recent_date,
                EquipmentPrice.is_available == True
            ).all()
            
            # 转换为字典便于查找
            recent_dict = defaultdict(list)
            for price in recent_prices:
                key = (price.equipment_id, price.platform)
                recent_dict[key].append(price.price)
            
            older_dict = defaultdict(list)
            for price in older_prices:
                key = (price.equipment_id, price.platform)
                older_dict[key].append(price.price)
            
            alerts = []
            
            # 比较价格变化
            for key in recent_dict:
                if key in older_dict:
                    recent_avg = np.mean(recent_dict[key])
                    older_avg = np.mean(older_dict[key])
                    
                    if older_avg > 0:
                        price_change_percent = ((recent_avg - older_avg) / older_avg) * 100
                        
                        if abs(price_change_percent) >= price_change_threshold:
                            equipment_id, platform = key
                            equipment_name = next(
                                (p.name for p in recent_prices if p.equipment_id == equipment_id),
                                '未知商品'
                            )
                            
                            alerts.append({
                                'equipment_id': equipment_id,
                                'equipment_name': equipment_name,
                                'platform': platform,
                                'old_price': round(older_avg, 2),
                                'new_price': round(recent_avg, 2),
                                'price_change': round(recent_avg - older_avg, 2),
                                'price_change_percent': round(price_change_percent, 2),
                                'alert_type': '价格上涨' if price_change_percent > 0 else '价格下降',
                                'alert_time': datetime.now().isoformat()
                            })
            
            # 按价格变化幅度排序
            alerts.sort(key=lambda x: abs(x['price_change_percent']), reverse=True)
            
            return alerts
            
        except Exception as e:
            logger.error(f"生成价格预警失败: {str(e)}")
            return []
    
    def get_equipment_recommendations(self, category: str = None, budget_range: Tuple[float, float] = None, 
                                   platform: str = None, limit: int = 10) -> List[Dict]:
        """获取装备推荐"""
        try:
            db = self.db
            Equipment = self.Equipment
            EquipmentPrice = self.EquipmentPrice
            
            # 构建查询
            from app import EquipmentCategory
            query = db.session.query(
                Equipment.id,
                Equipment.name,
                Equipment.brand,
                EquipmentCategory.name.label('category'),
                Equipment.rating,
                Equipment.review_count,
                EquipmentPrice.platform,
                EquipmentPrice.price,
                EquipmentPrice.seller_name
            ).join(
                EquipmentPrice, Equipment.id == EquipmentPrice.equipment_id
            ).outerjoin(
                EquipmentCategory, Equipment.category_id == EquipmentCategory.id
            ).filter(
                EquipmentPrice.is_available == True
            )
            
            if category:
                query = query.filter(EquipmentCategory.name == category)
            
            if platform:
                query = query.filter(EquipmentPrice.platform == platform)
            
            if budget_range:
                min_budget, max_budget = budget_range
                query = query.filter(
                    EquipmentPrice.price >= min_budget,
                    EquipmentPrice.price <= max_budget
                )
            
            data = query.all()
            
            if not data:
                return []
            
            # 转换为DataFrame并计算推荐分数
            df = pd.DataFrame([
                {
                    'equipment_id': row.id,
                    'name': row.name,
                    'brand': row.brand or '未知品牌',
                    'category': row.category,
                    'rating': float(row.rating_avg or 0),
                    'rating_count': int(row.rating_count or 0),
                    'platform': row.platform,
                    'price': float(row.price),
                    'shop_name': row.seller_name or ''
                }
                for row in data
            ])
            
            # 计算推荐分数
            df['recommendation_score'] = self._calculate_recommendation_score(df)
            
            # 按推荐分数排序并去重
            df_sorted = df.sort_values('recommendation_score', ascending=False)
            df_unique = df_sorted.drop_duplicates(subset=['equipment_id'], keep='first')
            
            recommendations = []
            for _, row in df_unique.head(limit).iterrows():
                recommendations.append({
                    'equipment_id': int(row['equipment_id']),
                    'name': row['name'],
                    'brand': row['brand'],
                    'category': row['category'],
                    'rating': row['rating'],
                    'rating_count': row['rating_count'],
                    'platform': row['platform'],
                    'price': row['price'],
                    'seller_name': row['seller_name'],
                    'recommendation_score': round(row['recommendation_score'], 2)
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"获取装备推荐失败: {str(e)}")
            return []
    
    def _calculate_recommendation_score(self, df: pd.DataFrame) -> pd.Series:
        """计算推荐分数"""
        # 评分权重（0-5分，归一化到0-1）
        rating_score = df['rating'] / 5.0
        
        # 评价数量权重（对数归一化）
        rating_count_score = np.log1p(df['rating_count']) / np.log1p(df['rating_count'].max()) if df['rating_count'].max() > 0 else 0
        
        # 价格权重（价格越低分数越高，归一化到0-1）
        if df['price'].max() > df['price'].min():
            price_score = 1 - (df['price'] - df['price'].min()) / (df['price'].max() - df['price'].min())
        else:
            price_score = pd.Series([0.5] * len(df))
        
        # 品牌权重（知名品牌加分）
        known_brands = ['Giant', '捷安特', 'Trek', 'Specialized', 'Shimano', '禧玛诺']
        brand_score = df['brand'].apply(lambda x: 0.8 if x in known_brands else 0.5)
        
        # 综合评分
        recommendation_score = (
            rating_score * 0.3 +
            rating_count_score * 0.2 +
            price_score * 0.3 +
            brand_score * 0.2
        ) * 100  # 转换为0-100分
        
        return recommendation_score
    
    def clear_cache(self):
        """清理分析缓存"""
        self.analysis_cache.clear()
        logger.info("数据分析缓存已清理")