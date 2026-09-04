#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据初始化脚本
用于插入示例装备数据和测试数据
"""

from app import app, db
from models.equipment import Equipment, EquipmentCategory, EquipmentPrice, EquipmentReview
from datetime import datetime, timedelta
import json
import random
from loguru import logger

def init_sample_equipment():
    """初始化示例装备数据"""
    
    # 示例装备数据
    sample_equipment = [
        {
            'name': '捷安特 ATX 820 山地自行车',
            'brand': '捷安特',
            'model': 'ATX 820',
            'category_name': '山地车',
            'description': '入门级山地自行车，适合城市骑行和轻度越野',
            'specifications': {
                '车架材质': '铝合金',
                '轮径': '26寸',
                '变速': '21速',
                '刹车': '线拉碟刹',
                '适合身高': '165-180cm'
            },
            'images': [
                'https://example.com/images/giant-atx820-1.jpg',
                'https://example.com/images/giant-atx820-2.jpg'
            ],
            'tags': ['入门', '山地', '城市', '通勤'],
            'weight': 14500,
            'material': '铝合金',
            'color_options': ['黑色', '蓝色', '红色'],
            'size_options': ['S', 'M', 'L']
        },
        {
            'name': '美利达 公爵 600 山地车',
            'brand': '美利达',
            'model': '公爵 600',
            'category_name': '山地车',
            'description': '专业山地自行车，适合越野和山地骑行',
            'specifications': {
                '车架材质': '铝合金',
                '轮径': '27.5寸',
                '变速': '24速',
                '刹车': '油压碟刹',
                '适合身高': '170-185cm'
            },
            'images': [
                'https://example.com/images/merida-duke600-1.jpg'
            ],
            'tags': ['专业', '山地', '越野'],
            'weight': 13800,
            'material': '铝合金',
            'color_options': ['黑色', '绿色'],
            'size_options': ['M', 'L', 'XL']
        },
        {
            'name': 'POC Ventral Air SPIN 骑行头盔',
            'brand': 'POC',
            'model': 'Ventral Air SPIN',
            'category_name': '头盔',
            'description': '专业公路骑行头盔，轻量化设计，优秀的通风性能',
            'specifications': {
                '重量': '230g',
                '通风孔': '22个',
                '安全标准': 'CE EN1078',
                '尺寸': 'S/M/L'
            },
            'images': [
                'https://example.com/images/poc-ventral-1.jpg'
            ],
            'tags': ['专业', '轻量', '通风', '安全'],
            'weight': 230,
            'material': 'PC+EPS',
            'color_options': ['白色', '黑色', '蓝色'],
            'size_options': ['S(51-54cm)', 'M(55-58cm)', 'L(59-62cm)']
        },
        {
            'name': 'Shimano SH-RP3 公路骑行鞋',
            'brand': 'Shimano',
            'model': 'SH-RP3',
            'category_name': '骑行鞋',
            'description': '入门级公路骑行鞋，舒适透气，性价比高',
            'specifications': {
                '鞋底': '玻纤强化尼龙',
                '扣具': '3个魔术贴',
                '重量': '约280g(42码)',
                '兼容': 'SPD-SL锁片'
            },
            'images': [
                'https://example.com/images/shimano-rp3-1.jpg'
            ],
            'tags': ['入门', '舒适', '透气'],
            'weight': 280,
            'material': '合成革+网布',
            'color_options': ['黑色', '白色'],
            'size_options': ['39', '40', '41', '42', '43', '44', '45']
        },
        {
            'name': 'Garmin Edge 530 GPS码表',
            'brand': 'Garmin',
            'model': 'Edge 530',
            'category_name': '码表',
            'description': '专业GPS骑行码表，支持导航和训练分析',
            'specifications': {
                '屏幕': '2.6寸彩色屏',
                '电池': '20小时续航',
                '防水': 'IPX7',
                '存储': '16GB',
                '连接': 'ANT+/蓝牙'
            },
            'images': [
                'https://example.com/images/garmin-edge530-1.jpg'
            ],
            'tags': ['专业', 'GPS', '导航', '训练'],
            'weight': 75.8,
            'material': '塑料+金属',
            'color_options': ['黑色'],
            'size_options': ['标准版']
        }
    ]
    
    with app.app_context():
        try:
            for equipment_data in sample_equipment:
                # 查找分类ID
                category = EquipmentCategory.query.filter_by(
                    name=equipment_data['category_name']
                ).first()
                
                if not category:
                    logger.warning(f"分类 {equipment_data['category_name']} 不存在，跳过")
                    continue
                
                # 检查装备是否已存在
                existing = Equipment.query.filter_by(
                    name=equipment_data['name']
                ).first()
                
                if existing:
                    logger.info(f"装备 {equipment_data['name']} 已存在，跳过")
                    continue
                
                # 创建装备
                equipment = Equipment(
                    name=equipment_data['name'],
                    brand=equipment_data['brand'],
                    model=equipment_data['model'],
                    category_id=category.id,
                    description=equipment_data['description'],
                    specifications=equipment_data['specifications'],
                    images=equipment_data['images'],
                    tags=equipment_data['tags'],
                    weight=equipment_data['weight'],
                    material=equipment_data['material'],
                    color_options=equipment_data['color_options'],
                    size_options=equipment_data['size_options'],
                    price=round(random.uniform(200, 8000), 2),
                    rating=round(random.uniform(4.0, 5.0), 1),
                    review_count=random.randint(10, 200),
                    sales_count=random.randint(50, 500),
                    source='sample',
                    availability=True
                )
                
                db.session.add(equipment)
                logger.info(f"添加装备: {equipment_data['name']}")
            
            db.session.commit()
            logger.info("示例装备数据初始化完成")
            
        except Exception as e:
            logger.error(f"初始化装备数据失败: {str(e)}")
            db.session.rollback()
            raise

def add_sample_prices(equipment_id, base_price=None):
    """为装备添加示例价格数据"""
    platforms = ['taobao', 'jd']
    if base_price is None:
        base_price = random.uniform(100, 5000)
    
    # 添加最近30天的价格数据
    for i in range(30):
        date = datetime.now() - timedelta(days=i)
        
        for platform in platforms:
            # 价格有小幅波动
            price_variation = random.uniform(0.9, 1.1)
            price = round(base_price * price_variation, 2)
            
            price_record = EquipmentPrice(
                equipment_id=equipment_id,
                platform=platform,
                platform_url=f'https://{platform}.com/item/{random.randint(100000, 999999)}',
                platform_id=str(random.randint(100000, 999999)),
                price=price,
                original_price=round(price * random.uniform(1.0, 1.3), 2),
                discount=random.uniform(0.7, 0.95),
                currency='CNY',
                stock_status='有货',
                seller_name=f'{platform}官方旗舰店',
                seller_rating=random.uniform(4.5, 5.0),
                shipping_info={'free_shipping': True, 'delivery_time': '1-3天'},
                promotion_info={'discount': '满300减30'},
                is_available=True,
                created_at=date
            )
            
            db.session.add(price_record)

def add_sample_reviews(equipment_id):
    """为装备添加示例评价数据"""
    sample_reviews = [
        {
            'user_name': '骑行爱好者',
            'rating': 5,
            'title': '非常满意的购买',
            'content': '质量很好，骑行体验很棒，值得推荐！',
            'platform': 'taobao'
        },
        {
            'user_name': '山地车手',
            'rating': 4,
            'title': '性价比不错',
            'content': '整体还可以，适合入门使用，后续可能会升级。',
            'platform': 'jd'
        },
        {
            'user_name': '新手骑友',
            'rating': 5,
            'title': '很适合新手',
            'content': '作为新手第一辆车很满意，店家服务也很好。',
            'platform': 'taobao'
        }
    ]
    
    for review_data in sample_reviews:
        review = EquipmentReview(
            equipment_id=equipment_id,
            platform=review_data['platform'],
            platform_review_id=str(random.randint(100000, 999999)),
            user_name=review_data['user_name'],
            user_avatar=f'https://example.com/avatar/{random.randint(1, 100)}.jpg',
            rating=review_data['rating'],
            title=review_data['title'],
            content=review_data['content'],
            images=[],
            purchase_info={'verified': True, 'purchase_date': '2024-01-01'},
            helpful_count=random.randint(0, 50),
            reply_count=random.randint(0, 5),
            is_verified=True,
            review_date=datetime.now() - timedelta(days=random.randint(1, 30))
        )
        
        db.session.add(review)

def init_sample_prices():
    """为所有缺少价格记录的装备生成示例价格历史（幂等）"""
    with app.app_context():
        try:
            equipment_list = Equipment.query.all()
            added = 0
            for equipment in equipment_list:
                existing = EquipmentPrice.query.filter_by(equipment_id=equipment.id).first()
                if existing:
                    continue
                base_price = float(equipment.price) if equipment.price else None
                add_sample_prices(equipment.id, base_price=base_price)
                added += 1
            
            db.session.commit()
            logger.info(f"价格数据初始化完成，为 {added} 个装备添加了示例价格")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"初始化价格数据失败: {str(e)}")
            raise

def check_categories():
    """检查分类数据是否存在"""
    with app.app_context():
        categories = EquipmentCategory.query.all()
        if not categories:
            logger.error("没有找到装备分类数据，请先执行数据库初始化脚本")
            return False
        
        logger.info(f"找到 {len(categories)} 个装备分类")
        for category in categories:
            logger.info(f"  - {category.name} ({category.name_en})")
        
        return True

def main():
    """主函数"""
    logger.info("开始初始化示例数据")
    
    # 检查分类数据
    if not check_categories():
        return
    
    # 初始化装备数据
    init_sample_equipment()
    
    # 初始化价格历史数据
    init_sample_prices()
    
    logger.info("示例数据初始化完成")

if __name__ == '__main__':
    main()