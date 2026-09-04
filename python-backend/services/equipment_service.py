from sqlalchemy import and_, or_, desc, func
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
from loguru import logger
import re
from collections import defaultdict

class EquipmentService:
    """装备服务类"""
    
    def __init__(self, db=None, equipment_model=None, category_model=None, price_model=None, review_model=None):
        self.db = db
        self.Equipment = equipment_model
        self.EquipmentCategory = category_model
        self.EquipmentPrice = price_model
        self.EquipmentReview = review_model
    
    def get_all_categories(self):
        """获取所有装备分类"""
        try:
            # 获取顶级分类（没有父分类的）
            top_categories = self.EquipmentCategory.query.filter(
                self.EquipmentCategory.parent_id.is_(None),
                self.EquipmentCategory.is_active == True
            ).order_by(self.EquipmentCategory.sort_order).all()
            
            return [category.to_dict() for category in top_categories]
        
        except Exception as e:
            logger.error(f"获取装备分类失败: {str(e)}")
            raise
    
    def search_equipment(self, keyword='', category_id=None, min_price=None,
                         max_price=None, platform='', page=1, per_page=20, sort_by='rating'):
        """搜索装备，支持关键词、分类、价格、平台筛选以及多种排序方式"""
        try:
            query = self.Equipment.query.filter(self.Equipment.availability == True)

            # 关键词搜索
            if keyword:
                keyword_filter = or_(
                    self.Equipment.name.contains(keyword),
                    self.Equipment.brand.contains(keyword),
                    self.Equipment.description.contains(keyword)
                )
                query = query.filter(keyword_filter)

            # 分类筛选
            if category_id:
                query = query.filter(self.Equipment.category_id == category_id)

            # 价格筛选（基于 Equipment.price 字段）
            if min_price is not None:
                try:
                    query = query.filter(self.Equipment.price >= float(min_price))
                except (ValueError, TypeError):
                    pass
            if max_price is not None:
                try:
                    query = query.filter(self.Equipment.price <= float(max_price))
                except (ValueError, TypeError):
                    pass

            # 平台筛选：通过关联的 EquipmentPrice 表过滤
            if platform:
                platform_subquery = self.db.session.query(
                    self.EquipmentPrice.equipment_id
                ).filter(
                    self.EquipmentPrice.platform == platform,
                    self.EquipmentPrice.is_available == True
                ).subquery()
                query = query.filter(self.Equipment.id.in_(platform_subquery))

            # 排序
            if sort_by == 'price_asc':
                query = query.order_by(
                    self.Equipment.price.asc(),
                    self.Equipment.rating.desc()
                )
            elif sort_by == 'price_desc':
                query = query.order_by(
                    self.Equipment.price.desc(),
                    self.Equipment.rating.desc()
                )
            elif sort_by == 'newest':
                query = query.order_by(
                    self.Equipment.created_at.desc()
                )
            else:  # 默认 rating
                query = query.order_by(
                    self.Equipment.rating.desc(),
                    self.Equipment.review_count.desc(),
                    self.Equipment.created_at.desc()
                )

            # 分页
            total = query.count()
            equipment_list = query.offset((page - 1) * per_page).limit(per_page).all()

            # 构建返回数据
            equipment_data = []
            for equipment in equipment_list:
                equipment_dict = equipment.to_dict()
                # 附加最新价格信息（用于卡片展示）
                latest_price = self.EquipmentPrice.query.filter(
                    self.EquipmentPrice.equipment_id == equipment.id,
                    self.EquipmentPrice.is_available == True
                ).order_by(self.EquipmentPrice.created_at.desc()).first()
                if latest_price:
                    equipment_dict['latest_price'] = {
                        'price': float(latest_price.price),
                        'platform': latest_price.platform,
                        'url': latest_price.platform_url
                    }
                else:
                    equipment_dict['latest_price'] = None
                equipment_data.append(equipment_dict)

            return {
                'items': equipment_data,
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': (total + per_page - 1) // per_page
            }
        except Exception as e:
            logger.error(f"搜索装备失败: {str(e)}")
            raise
    
    def get_equipment_list(self, page=1, per_page=20, category_id=None, sort_by='rating'):
        """获取装备列表"""
        query = self.Equipment.query.filter_by(availability=True)
        
        if category_id:
            query = query.filter_by(category_id=category_id)
            
        # 排序
        if sort_by == 'price_asc':
            query = query.order_by(self.Equipment.price.asc())
        elif sort_by == 'price_desc':
            query = query.order_by(self.Equipment.price.desc())
        elif sort_by == 'newest':
            query = query.order_by(self.Equipment.created_at.desc())
        else:  # 默认 rating
            query = query.order_by(
                self.Equipment.rating.desc(),
                self.Equipment.review_count.desc()
            )
        
        total = query.count()
        equipment_items = query.offset((page - 1) * per_page).limit(per_page).all()
        
        equipment_list = []
        for equipment in equipment_items:
            # 获取最新价格
            latest_price = self.EquipmentPrice.query.filter_by(
                equipment_id=equipment.id
            ).order_by(self.EquipmentPrice.created_at.desc()).first()
            
            # 获取评价数量
            review_count = self.EquipmentReview.query.filter_by(
                equipment_id=equipment.id
            ).count()
            
            equipment_list.append({
                'id': equipment.id,
                'name': equipment.name,
                'brand': equipment.brand,
                'model': equipment.model,
                'category': {
                    'id': equipment.category_obj.id,
                    'name': equipment.category_obj.name
                } if equipment.category_obj else None,
                'description': equipment.description[:200] + '...' if len(equipment.description or '') > 200 else equipment.description,
                'images': equipment.images[:1] if equipment.images else [],  # 只返回第一张图片
                'tags': equipment.tags[:5] if equipment.tags else [],  # 只返回前5个标签
                'rating': float(equipment.rating_avg) if equipment.rating_avg else 0,
                'review_count': review_count,
                'current_price': {
                    'price': float(latest_price.price) if latest_price else None,
                    'platform': latest_price.platform if latest_price else None
                } if latest_price else None
            })
        
        return {
            'items': equipment_list,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        }
    
    def get_equipment_detail(self, equipment_id):
        """获取装备详情"""
        try:
            equipment = self.Equipment.query.get(equipment_id)
            if not equipment:
                return None
                
            # 获取最新价格
            latest_price = self.EquipmentPrice.query.filter_by(
                equipment_id=equipment_id
            ).order_by(self.EquipmentPrice.created_at.desc()).first()
            
            # 获取评价统计
            reviews = self.EquipmentReview.query.filter_by(equipment_id=equipment_id).all()
            avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else 0
            
            return {
                'id': equipment.id,
                'name': equipment.name,
                'brand': equipment.brand,
                'model': equipment.model,
                'category': {
                    'id': equipment.category_obj.id,
                    'name': equipment.category_obj.name
                } if equipment.category_obj else None,
                'description': equipment.description,
                'specifications': equipment.specifications,
                'images': equipment.images,
                'tags': equipment.tags,
                'weight': float(equipment.weight) if equipment.weight else None,
                'material': equipment.material,
                'color_options': equipment.color_options,
                'size_options': equipment.size_options,
                'rating': float(equipment.rating_avg) if equipment.rating_avg else avg_rating,
                'review_count': len(reviews),
                'current_price': {
                    'price': float(latest_price.price) if latest_price else None,
                    'platform': latest_price.platform if latest_price else None,
                    'url': latest_price.platform_url if latest_price else None,
                    'updated_at': latest_price.created_at.isoformat() if latest_price else None
                } if latest_price else None,
                'created_at': equipment.created_at.isoformat(),
                'updated_at': equipment.updated_at.isoformat()
            }
        except Exception as e:
            logger.error(f"获取装备详情失败: {str(e)}")
            raise
    
    def get_latest_prices(self, equipment_id, limit=5):
        """获取装备的最新价格"""
        try:
            prices = self.EquipmentPrice.query.filter(
                self.EquipmentPrice.equipment_id == equipment_id,
                self.EquipmentPrice.is_available == True
            ).order_by(desc(self.EquipmentPrice.created_at)).limit(limit).all()
            
            return [price.to_dict() for price in prices]
        
        except Exception as e:
            logger.error(f"获取最新价格失败: {str(e)}")
            return []
    
    def get_price_range(self, equipment_id):
        """获取装备的价格范围"""
        try:
            # 获取最近30天的价格数据
            thirty_days_ago = datetime.now() - timedelta(days=30)
            
            price_stats = db.session.query(
                func.min(EquipmentPrice.price).label('min_price'),
                func.max(EquipmentPrice.price).label('max_price'),
                func.avg(EquipmentPrice.price).label('avg_price')
            ).filter(
                EquipmentPrice.equipment_id == equipment_id,
                EquipmentPrice.created_at >= thirty_days_ago,
                EquipmentPrice.is_available == True
            ).first()
            
            if price_stats and price_stats.min_price:
                return {
                    'min_price': float(price_stats.min_price),
                    'max_price': float(price_stats.max_price),
                    'avg_price': float(price_stats.avg_price)
                }
            
            return None
        
        except Exception as e:
            logger.error(f"获取价格范围失败: {str(e)}")
            return None
    
    def get_price_history(self, equipment_id, days=30):
        """获取装备价格历史"""
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            prices = self.EquipmentPrice.query.filter(
                self.EquipmentPrice.equipment_id == equipment_id,
                self.EquipmentPrice.created_at >= start_date
            ).order_by(self.EquipmentPrice.created_at).all()
            
            # 按平台分组
            platform_prices = defaultdict(list)
            for price in prices:
                platform_prices[price.platform].append(price.to_dict())
            
            # 计算价格趋势
            price_trend = self._calculate_price_trend(prices)
            
            return {
                'platform_prices': dict(platform_prices),
                'price_trend': price_trend,
                'total_records': len(prices)
            }
        
        except Exception as e:
            logger.error(f"获取价格历史失败: {str(e)}")
            raise
    
    def _calculate_price_trend(self, prices):
        """计算价格趋势"""
        if len(prices) < 2:
            return {'trend': 'stable', 'change_percent': 0}
        
        # 按时间排序
        sorted_prices = sorted(prices, key=lambda x: x.created_at)
        
        # 计算最近价格变化
        recent_prices = sorted_prices[-7:]  # 最近7个价格点
        if len(recent_prices) < 2:
            return {'trend': 'stable', 'change_percent': 0}
        
        first_price = float(recent_prices[0].price)
        last_price = float(recent_prices[-1].price)
        
        if first_price == 0:
            return {'trend': 'stable', 'change_percent': 0}
        
        change_percent = ((last_price - first_price) / first_price) * 100
        
        if change_percent > 5:
            trend = 'rising'
        elif change_percent < -5:
            trend = 'falling'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'change_percent': round(change_percent, 2),
            'first_price': first_price,
            'last_price': last_price
        }
    
    def get_recommendations(self, equipment_id, limit=10):
        """获取装备推荐"""
        try:
            # 获取当前装备信息
            current_equipment = self.Equipment.query.get(equipment_id)
            if not current_equipment:
                raise ValueError(f"装备 {equipment_id} 不存在")
            
            # 基于分类的推荐
            category_recommendations = self._get_category_recommendations(
                current_equipment, limit // 2
            )
            
            # 基于品牌的推荐
            brand_recommendations = self._get_brand_recommendations(
                current_equipment, limit // 2
            )
            
            # 合并推荐结果，去重
            all_recommendations = category_recommendations + brand_recommendations
            seen_ids = set()
            unique_recommendations = []
            
            for rec in all_recommendations:
                if rec['id'] not in seen_ids and rec['id'] != equipment_id:
                    seen_ids.add(rec['id'])
                    unique_recommendations.append(rec)
                    if len(unique_recommendations) >= limit:
                        break
            
            return unique_recommendations
        
        except Exception as e:
            logger.error(f"获取推荐失败: {str(e)}")
            raise
    
    def _get_category_recommendations(self, equipment, limit):
        """基于分类的推荐"""
        recommendations = self.Equipment.query.filter(
            self.Equipment.category_id == equipment.category_id,
            self.Equipment.id != equipment.id,
            self.Equipment.availability == True
        ).order_by(
            desc(self.Equipment.rating),
            desc(self.Equipment.review_count)
        ).limit(limit).all()
        
        result = []
        for rec in recommendations:
            rec_dict = rec.to_dict()
            rec_dict['recommendation_reason'] = '同类商品'
            rec_dict['latest_prices'] = self.get_latest_prices(rec.id, 3)
            result.append(rec_dict)
        
        return result
    
    def _get_brand_recommendations(self, equipment, limit):
        """基于品牌的推荐"""
        if not equipment.brand:
            return []
        
        recommendations = self.Equipment.query.filter(
            self.Equipment.brand == equipment.brand,
            self.Equipment.id != equipment.id,
            self.Equipment.availability == True
        ).order_by(
            desc(self.Equipment.rating),
            desc(self.Equipment.review_count)
        ).limit(limit).all()
        
        result = []
        for rec in recommendations:
            rec_dict = rec.to_dict()
            rec_dict['recommendation_reason'] = '同品牌商品'
            rec_dict['latest_prices'] = self.get_latest_prices(rec.id, 3)
            result.append(rec_dict)
        
        return result
    
    def get_equipment_detail(self, equipment_id):
        """获取装备详情"""
        try:
            equipment = self.Equipment.query.get(equipment_id)
            if not equipment:
                raise ValueError(f"装备 {equipment_id} 不存在")
            
            equipment_dict = equipment.to_dict(include_prices=True, include_reviews=True)
            
            # 获取价格历史
            price_history = self.get_price_history(equipment_id, 90)
            equipment_dict['price_history'] = price_history
            
            # 获取推荐商品
            recommendations = self.get_recommendations(equipment_id, 6)
            equipment_dict['recommendations'] = recommendations
            
            return equipment_dict
        
        except Exception as e:
            logger.error(f"获取装备详情失败: {str(e)}")
            raise
    
    def get_popular_equipment(self, category_id=None, limit=20):
        """获取热门装备"""
        try:
            query = self.Equipment.query.filter(self.Equipment.availability == True)
            
            if category_id:
                query = query.filter(self.Equipment.category_id == category_id)
            
            # 按评分和评价数量排序
            equipment_list = query.order_by(
                desc(self.Equipment.rating),
                desc(self.Equipment.review_count)
            ).limit(limit).all()
            
            result = []
            for equipment in equipment_list:
                equipment_dict = equipment.to_dict()
                equipment_dict['latest_prices'] = self.get_latest_prices(equipment.id, 3)
                result.append(equipment_dict)
            
            return result
        
        except Exception as e:
            logger.error(f"获取热门装备失败: {str(e)}")
            raise
    
    def get_price_alerts(self, user_id=None):
        """获取价格提醒（预留接口）"""
        # 这里可以实现价格提醒功能
        # 比如用户设置某个商品的目标价格，当价格低于目标价格时发送提醒
        pass
    
    def add_equipment_category(self, name, name_en, description=None, parent_id=None):
        """添加装备分类"""
        try:
            category = self.EquipmentCategory(
                name=name,
                name_en=name_en,
                description=description,
                parent_id=parent_id
            )
            
            self.db.session.add(category)
            self.db.session.commit()
            
            return category.to_dict()
        
        except Exception as e:
            logger.error(f"添加装备分类失败: {str(e)}")
            self.db.session.rollback()
            raise
    
    def update_equipment_rating(self, equipment_id):
        """更新装备评分"""
        try:
            # 计算平均评分和评价数量
            rating_stats = self.db.session.query(
                func.avg(self.EquipmentReview.rating).label('avg_rating'),
                func.count(self.EquipmentReview.id).label('review_count')
            ).filter(self.EquipmentReview.equipment_id == equipment_id).first()
            
            equipment = self.Equipment.query.get(equipment_id)
            if equipment and rating_stats:
                equipment.rating_avg = float(rating_stats.avg_rating) if rating_stats.avg_rating else 0.0
                equipment.rating_count = rating_stats.review_count or 0
                
                self.db.session.commit()
                
                logger.info(f"更新装备 {equipment_id} 评分: {equipment.rating_avg}")
        
        except Exception as e:
            logger.error(f"更新装备评分失败: {str(e)}")
            self.db.session.rollback()