import requests
import time
import json
import uuid
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from fake_useragent import UserAgent
from loguru import logger
import threading
from concurrent.futures import ThreadPoolExecutor
import re
from urllib.parse import urljoin, urlparse
import hashlib
import hmac
import base64

class CrawlerService:
    """爬虫服务类"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.tasks = {}  # 存储爬虫任务状态
        self.session = requests.Session()
        
        # 反反爬配置
        self.request_delay = (1, 3)  # 请求间隔范围（秒）
        self.max_retries = 3  # 最大重试次数
        self.timeout = 30  # 请求超时时间
        
        self._setup_session()
        
        # 代理池（可选）
        self.proxy_pool = []
        self.current_proxy_index = 0
        
        # 第三方API配置
        self.api_config = {
            'onebound': {
                'base_url': 'https://api-gw.onebound.cn',
                'app_key': '',  # 需要配置
                'app_secret': '',  # 需要配置
                'enabled': False
            },
            'juhe': {
                'base_url': 'http://apis.juhe.cn',
                'app_key': '',  # 需要配置
                'enabled': False
            }
        }
        
        # 爬取方式配置
        self.crawl_methods = {
            'selenium': True,  # 使用Selenium爬取
            'api': True,      # 使用API接口
            'requests': False  # 使用requests直接爬取（容易被反爬）
        }
        
        # 骑行装备关键词分类
        self.equipment_categories = {
            'bike': ['自行车', '山地车', '公路车', '折叠车', '电动车'],
            'helmet': ['头盔', '骑行头盔', '安全帽'],
            'clothing': ['骑行服', '骑行裤', '骑行手套', '骑行鞋'],
            'accessories': ['车灯', '码表', '水壶', '车锁', '打气筒', '工具包'],
            'parts': ['轮胎', '内胎', '刹车片', '链条', '齿轮', '座垫']
        }
    
    def _setup_session(self):
        """设置请求会话"""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        })
        
        # 设置超时
        self.session.timeout = self.timeout
    
    def _get_random_delay(self):
        """获取随机延迟时间"""
        import random
        return random.uniform(self.request_delay[0], self.request_delay[1])
    
    def _rotate_user_agent(self):
        """轮换User-Agent"""
        self.session.headers['User-Agent'] = self.ua.random
    
    def _get_proxy(self):
        """获取代理"""
        if not self.proxy_pool:
            return None
        
        proxy = self.proxy_pool[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_pool)
        return proxy
    
    def _make_request_with_retry(self, url, method='GET', **kwargs):
        """带重试机制的请求"""
        for attempt in range(self.max_retries):
            try:
                # 轮换User-Agent
                self._rotate_user_agent()
                
                # 添加随机延迟
                if attempt > 0:
                    delay = self._get_random_delay() * (attempt + 1)
                    time.sleep(delay)
                
                # 获取代理
                proxy = self._get_proxy()
                if proxy:
                    kwargs['proxies'] = {'http': proxy, 'https': proxy}
                
                # 发送请求
                if method.upper() == 'GET':
                    response = self.session.get(url, **kwargs)
                else:
                    response = self.session.post(url, **kwargs)
                
                # 检查响应状态
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # 请求过于频繁
                    logger.warning(f"请求频率限制，等待重试: {url}")
                    time.sleep(self._get_random_delay() * 2)
                    continue
                else:
                    logger.warning(f"请求失败，状态码: {response.status_code}, URL: {url}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"请求异常 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
        
        raise Exception(f"请求失败，已重试 {self.max_retries} 次: {url}")
    
    def _get_webdriver(self, headless=True):
        """获取WebDriver实例"""
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument('--headless')
        
        # 基础配置
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument(f'--user-agent={self.ua.random}')
        
        # 反检测配置
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-images')
        chrome_options.add_argument('--disable-javascript')
        
        # 性能优化
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values": {
                "notifications": 2,
                "media_stream": 2,
            },
            "profile.managed_default_content_settings.media_stream": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            # 使用webdriver-manager自动管理ChromeDriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # 执行反检测脚本
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']})")
            
            # 设置页面加载超时
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(10)
            
            return driver
        except Exception as e:
            logger.error(f"创建WebDriver失败: {str(e)}")
            return None
    
    def start_crawl_task(self, platform='all', category='all'):
        """启动爬虫任务"""
        task_id = str(uuid.uuid4())
        
        self.tasks[task_id] = {
            'id': task_id,
            'status': 'running',
            'platform': platform,
            'category': category,
            'start_time': datetime.now(),
            'progress': 0,
            'total_items': 0,
            'crawled_items': 0,
            'errors': [],
            'message': '任务启动中...'
        }
        
        # 在新线程中执行爬虫任务
        thread = threading.Thread(
            target=self._execute_crawl_task,
            args=(task_id, platform, category)
        )
        thread.daemon = True
        thread.start()
        
        return task_id
    
    def _execute_crawl_task(self, task_id, platform, category):
        """执行爬虫任务"""
        try:
            self.tasks[task_id]['message'] = '正在获取商品列表...'
            
            # 优先使用API方式，如果失败则使用Selenium
            if platform == 'all' or platform == 'taobao':
                success = False
                if self.crawl_methods['api']:
                    try:
                        self._crawl_taobao_api(task_id, category)
                        success = True
                        logger.info("使用API方式成功爬取淘宝数据")
                    except Exception as e:
                        logger.warning(f"API方式爬取淘宝失败，尝试Selenium方式: {str(e)}")
                
                if not success and self.crawl_methods['selenium']:
                    self._crawl_taobao(task_id, category)
            
            if platform == 'all' or platform == 'jd':
                success = False
                if self.crawl_methods['api']:
                    try:
                        self._crawl_jd_api(task_id, category)
                        success = True
                        logger.info("使用API方式成功爬取京东数据")
                    except Exception as e:
                        logger.warning(f"API方式爬取京东失败，尝试Selenium方式: {str(e)}")
                
                if not success and self.crawl_methods['selenium']:
                    self._crawl_jd(task_id, category)
            
            self.tasks[task_id]['status'] = 'completed'
            self.tasks[task_id]['message'] = '爬取任务完成'
            self.tasks[task_id]['end_time'] = datetime.now()
            
        except Exception as e:
            logger.error(f"爬虫任务执行失败: {str(e)}")
            self.tasks[task_id]['status'] = 'failed'
            self.tasks[task_id]['message'] = f'任务失败: {str(e)}'
            self.tasks[task_id]['errors'].append(str(e))
            self.tasks[task_id]['end_time'] = datetime.now()
    
    def _crawl_taobao(self, task_id, category):
        """爬取淘宝数据"""
        logger.info(f"开始爬取淘宝数据，分类: {category}")
        
        keywords = self._get_keywords_for_category(category)
        
        for keyword in keywords:
                try:
                    self.tasks[task_id]['message'] = f'正在爬取淘宝: {keyword}'
                    self._crawl_taobao_keyword(task_id, keyword)
                    # 随机延迟，避免请求过快
                    delay = self._get_random_delay()
                    time.sleep(delay)
                except Exception as e:
                    logger.error(f"爬取淘宝关键词 {keyword} 失败: {str(e)}")
                    self.tasks[task_id]['errors'].append(f"淘宝-{keyword}: {str(e)}")
                    # 出错后增加延迟
                    time.sleep(self._get_random_delay() * 2)
    
    def _crawl_taobao_keyword(self, task_id, keyword):
        """爬取淘宝特定关键词的商品"""
        # 淘宝搜索URL
        search_url = f"https://s.taobao.com/search?q={keyword}&sort=sale-desc"
        
        driver = self._get_webdriver()
        if not driver:
            raise Exception("无法创建WebDriver")
        
        try:
            driver.get(search_url)
            time.sleep(3)
            
            # 等待商品列表加载
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".item"))
            )
            
            # 获取商品列表
            items = driver.find_elements(By.CSS_SELECTOR, ".item")
            
            for i, item in enumerate(items[:20]):  # 限制每个关键词爬取20个商品
                try:
                    self._parse_taobao_item(task_id, item, keyword)
                    self.tasks[task_id]['crawled_items'] += 1
                    self.tasks[task_id]['progress'] = min(90, (i + 1) * 4)
                except Exception as e:
                    logger.error(f"解析淘宝商品失败: {str(e)}")
                    continue
        
        finally:
            driver.quit()
    
    def _parse_taobao_item(self, task_id, item_element, keyword):
        """解析淘宝商品信息"""
        try:
            # 商品标题
            title_elem = item_element.find_element(By.CSS_SELECTOR, ".title a")
            title = title_elem.get_attribute("title") or title_elem.text
            
            # 商品链接
            link = title_elem.get_attribute("href")
            if link and not link.startswith('http'):
                link = 'https:' + link
            
            # 价格
            price_elem = item_element.find_element(By.CSS_SELECTOR, ".price strong")
            price_text = price_elem.text.replace('¥', '').replace(',', '')
            price = float(re.findall(r'\d+\.?\d*', price_text)[0]) if re.findall(r'\d+\.?\d*', price_text) else 0
            
            # 商品图片
            img_elem = item_element.find_element(By.CSS_SELECTOR, ".pic img")
            image_url = img_elem.get_attribute("src") or img_elem.get_attribute("data-src")
            if image_url and not image_url.startswith('http'):
                image_url = 'https:' + image_url
            
            # 店铺信息
            shop_elem = item_element.find_element(By.CSS_SELECTOR, ".shop a")
            shop_name = shop_elem.text
            
            # 销量信息
            deal_cnt_elem = item_element.find_element(By.CSS_SELECTOR, ".deal-cnt")
            sales_text = deal_cnt_elem.text
            sales = self._extract_number(sales_text)
            
            # 保存商品信息
            equipment_data = {
                'name': title,
                'platform': 'taobao',
                'platform_url': link,
                'price': price,
                'image_url': image_url,
                'shop_name': shop_name,
                'sales': sales,
                'keyword': keyword,
                'crawl_time': datetime.now()
            }
            
            # 这里应该调用数据库保存方法
            self._save_equipment_data(equipment_data)
            
            logger.info(f"成功解析淘宝商品: {title}")
            
        except Exception as e:
            logger.error(f"解析淘宝商品元素失败: {str(e)}")
            raise
    
    def _crawl_jd(self, task_id, category):
        """爬取京东数据"""
        logger.info(f"开始爬取京东数据，分类: {category}")
        
        keywords = self._get_keywords_for_category(category)
        
        for keyword in keywords:
            try:
                self.tasks[task_id]['message'] = f'正在爬取京东: {keyword}'
                self._crawl_jd_keyword(task_id, keyword)
                # 随机延迟，避免请求过快
                delay = self._get_random_delay()
                time.sleep(delay)
            except Exception as e:
                logger.error(f"爬取京东关键词 {keyword} 失败: {str(e)}")
                self.tasks[task_id]['errors'].append(f"京东-{keyword}: {str(e)}")
                # 出错后增加延迟
                time.sleep(self._get_random_delay() * 2)
    
    def _crawl_jd_keyword(self, task_id, keyword):
        """爬取京东特定关键词的商品"""
        # 京东搜索URL
        search_url = f"https://search.jd.com/Search?keyword={keyword}&enc=utf-8&suggest=1.def.0.base&wq={keyword}&pvid=1"
        
        driver = self._get_webdriver()
        if not driver:
            raise Exception("无法创建WebDriver")
        
        try:
            driver.get(search_url)
            time.sleep(3)
            
            # 等待商品列表加载
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".gl-item"))
            )
            
            # 获取商品列表
            items = driver.find_elements(By.CSS_SELECTOR, ".gl-item")
            
            for i, item in enumerate(items[:20]):  # 限制每个关键词爬取20个商品
                try:
                    self._parse_jd_item(task_id, item, keyword)
                    self.tasks[task_id]['crawled_items'] += 1
                    self.tasks[task_id]['progress'] = min(90, (i + 1) * 4)
                except Exception as e:
                    logger.error(f"解析京东商品失败: {str(e)}")
                    continue
        
        finally:
            driver.quit()
    
    def _parse_jd_item(self, task_id, item_element, keyword):
        """解析京东商品信息"""
        try:
            # 商品标题
            title_elem = item_element.find_element(By.CSS_SELECTOR, ".p-name a em")
            title = title_elem.text
            
            # 商品链接
            link_elem = item_element.find_element(By.CSS_SELECTOR, ".p-name a")
            link = link_elem.get_attribute("href")
            if link and not link.startswith('http'):
                link = 'https:' + link
            
            # 价格
            price_elem = item_element.find_element(By.CSS_SELECTOR, ".p-price i")
            price_text = price_elem.text.replace('¥', '').replace(',', '')
            price = float(re.findall(r'\d+\.?\d*', price_text)[0]) if re.findall(r'\d+\.?\d*', price_text) else 0
            
            # 商品图片
            img_elem = item_element.find_element(By.CSS_SELECTOR, ".p-img img")
            image_url = img_elem.get_attribute("src") or img_elem.get_attribute("data-lazy-img")
            if image_url and not image_url.startswith('http'):
                image_url = 'https:' + image_url
            
            # 店铺信息
            try:
                shop_elem = item_element.find_element(By.CSS_SELECTOR, ".p-shop a")
                shop_name = shop_elem.text
            except:
                shop_name = "京东自营"
            
            # 评价数
            try:
                commit_elem = item_element.find_element(By.CSS_SELECTOR, ".p-commit a")
                commit_text = commit_elem.text
                commit_count = self._extract_number(commit_text)
            except:
                commit_count = 0
            
            # 保存商品信息
            equipment_data = {
                'name': title,
                'platform': 'jd',
                'platform_url': link,
                'price': price,
                'image_url': image_url,
                'shop_name': shop_name,
                'commit_count': commit_count,
                'keyword': keyword,
                'crawl_time': datetime.now()
            }
            
            # 这里应该调用数据库保存方法
            self._save_equipment_data(equipment_data)
            
            logger.info(f"成功解析京东商品: {title}")
            
        except Exception as e:
            logger.error(f"解析京东商品元素失败: {str(e)}")
            raise
    
    def _get_keywords_by_category(self, category):
        """根据分类获取关键词"""
        if category == 'all':
            keywords = []
            for cat_keywords in self.equipment_categories.values():
                keywords.extend(cat_keywords)
            return keywords
        elif category in self.equipment_categories:
            return self.equipment_categories[category]
        else:
            return [category]  # 如果是自定义分类，直接作为关键词
    
    def _extract_number(self, text):
        """从文本中提取数字"""
        numbers = re.findall(r'\d+', text.replace(',', ''))
        return int(numbers[0]) if numbers else 0
    
    def _clean_equipment_data(self, data):
        """清洗装备数据"""
        cleaned = data.copy()
        
        # 清洗商品名称
        if 'name' in cleaned:
            name = cleaned['name']
            # 移除多余的空格和特殊字符
            name = re.sub(r'\s+', ' ', name).strip()
            # 移除HTML标签
            name = re.sub(r'<[^>]+>', '', name)
            # 限制长度
            cleaned['name'] = name[:200] if name else ''
        
        # 清洗价格
        if 'price' in cleaned:
            price = cleaned['price']
            if isinstance(price, str):
                # 提取数字
                price_match = re.search(r'\d+\.?\d*', price.replace(',', ''))
                cleaned['price'] = float(price_match.group()) if price_match else 0.0
            elif price is None:
                cleaned['price'] = 0.0
        
        # 清洗图片URL
        if 'image_url' in cleaned and cleaned['image_url']:
            image_url = cleaned['image_url']
            if not image_url.startswith('http'):
                if image_url.startswith('//'):
                    cleaned['image_url'] = 'https:' + image_url
                elif image_url.startswith('/'):
                    cleaned['image_url'] = 'https://img.alicdn.com' + image_url
        
        # 清洗店铺名称
        if 'shop_name' in cleaned:
            shop_name = cleaned['shop_name']
            if shop_name:
                cleaned['shop_name'] = re.sub(r'\s+', ' ', shop_name).strip()[:100]
        
        return cleaned
    
    # ==================== API接口方法 ====================
    
    def configure_api(self, provider, app_key, app_secret=None):
        """配置API接口"""
        if provider in self.api_config:
            self.api_config[provider]['app_key'] = app_key
            if app_secret:
                self.api_config[provider]['app_secret'] = app_secret
            self.api_config[provider]['enabled'] = True
            logger.info(f"已配置{provider} API接口")
            return True
        return False
    
    def _generate_onebound_signature(self, params, app_secret):
        """生成万邦API签名"""
        # 按参数名排序
        sorted_params = sorted(params.items())
        # 拼接参数字符串
        param_str = '&'.join([f'{k}={v}' for k, v in sorted_params])
        # 生成签名
        sign_str = app_secret + param_str + app_secret
        signature = hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()
        return signature
    
    def _crawl_taobao_api(self, task_id, category):
        """使用API方式爬取淘宝数据"""
        if not self.api_config['onebound']['enabled']:
            raise Exception("万邦API未配置")
        
        keywords = self._get_keywords_for_category(category)
        
        for keyword in keywords:
            try:
                self.tasks[task_id]['message'] = f'正在通过API搜索: {keyword}'
                
                # 万邦API - 淘宝商品搜索
                params = {
                    'key': self.api_config['onebound']['app_key'],
                    'secret': self.api_config['onebound']['app_secret'],
                    'api_name': 'item_search',
                    'cache': 'yes',
                    'result_type': 'json',
                    'lang': 'cn',
                    'q': keyword,
                    'start_price': '0',
                    'end_price': '10000',
                    'page': '1',
                    'page_size': '20',
                    'sort': 'sale-desc',
                    'platform': '1688'  # 使用1688平台作为替代
                }
                
                # 生成签名
                sign_params = {k: v for k, v in params.items() if k != 'secret'}
                signature = self._generate_onebound_signature(sign_params, params['secret'])
                params['sign'] = signature
                del params['secret']
                
                response = self.session.get(
                    f"{self.api_config['onebound']['base_url']}/taobao/item_search",
                    params=params,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('error') == 0:
                        items = data.get('results', {}).get('items', [])
                        
                        for item in items:
                            equipment_data = {
                                'name': item.get('title', ''),
                                'platform_url': item.get('detail_url', ''),
                                'price': self._extract_number(item.get('price', '0')),
                                'image_url': item.get('pic_url', ''),
                                'shop_name': item.get('shop_name', ''),
                                'sales': self._extract_number(item.get('volume', '0')),
                                'platform': 'taobao',
                                'keyword': keyword,
                                'crawl_time': datetime.now()
                            }
                            
                            self._save_equipment_data(equipment_data)
                            self.tasks[task_id]['crawled_items'] += 1
                    else:
                        logger.error(f"API返回错误: {data.get('reason', '未知错误')}")
                else:
                    logger.error(f"API请求失败: {response.status_code}")
                
                time.sleep(1)  # API请求间隔
                
            except Exception as e:
                logger.error(f"API爬取淘宝商品失败 - 关键词: {keyword}, 错误: {str(e)}")
                self.tasks[task_id]['errors'].append(f"API爬取失败: {keyword} - {str(e)}")
    
    def _crawl_jd_api(self, task_id, category):
        """使用API方式爬取京东数据"""
        if not self.api_config['onebound']['enabled']:
            raise Exception("万邦API未配置")
        
        keywords = self._get_keywords_for_category(category)
        
        for keyword in keywords:
            try:
                self.tasks[task_id]['message'] = f'正在通过API搜索京东: {keyword}'
                
                # 万邦API - 京东商品搜索
                params = {
                    'key': self.api_config['onebound']['app_key'],
                    'secret': self.api_config['onebound']['app_secret'],
                    'api_name': 'jd_item_search',
                    'cache': 'yes',
                    'result_type': 'json',
                    'lang': 'cn',
                    'q': keyword,
                    'start_price': '0',
                    'end_price': '10000',
                    'page': '1',
                    'page_size': '20',
                    'sort': 'sale-desc'
                }
                
                # 生成签名
                sign_params = {k: v for k, v in params.items() if k != 'secret'}
                signature = self._generate_onebound_signature(sign_params, params['secret'])
                params['sign'] = signature
                del params['secret']
                
                response = self.session.get(
                    f"{self.api_config['onebound']['base_url']}/jd/item_search",
                    params=params,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('error') == 0:
                        items = data.get('results', {}).get('items', [])
                        
                        for item in items:
                            equipment_data = {
                                'name': item.get('title', ''),
                                'platform_url': item.get('item_url', ''),
                                'price': self._extract_number(item.get('price', '0')),
                                'image_url': item.get('pic_url', ''),
                                'shop_name': item.get('shop_name', ''),
                                'commit_count': self._extract_number(item.get('comment_count', '0')),
                                'platform': 'jd',
                                'keyword': keyword,
                                'crawl_time': datetime.now()
                            }
                            
                            self._save_equipment_data(equipment_data)
                            self.tasks[task_id]['crawled_items'] += 1
                    else:
                        logger.error(f"京东API返回错误: {data.get('reason', '未知错误')}")
                else:
                    logger.error(f"京东API请求失败: {response.status_code}")
                
                time.sleep(1)  # API请求间隔
                
            except Exception as e:
                logger.error(f"API爬取京东商品失败 - 关键词: {keyword}, 错误: {str(e)}")
                self.tasks[task_id]['errors'].append(f"API爬取失败: {keyword} - {str(e)}")
    
    def get_api_status(self):
        """获取API配置状态"""
        status = {}
        for provider, config in self.api_config.items():
            status[provider] = {
                'enabled': config['enabled'],
                'configured': bool(config['app_key'])
            }
        return status
    
    def set_crawl_method(self, method, enabled):
        """设置爬取方式"""
        if method in self.crawl_methods:
            self.crawl_methods[method] = enabled
            logger.info(f"已{'启用' if enabled else '禁用'}{method}爬取方式")
            return True
        return False
    
    def _classify_equipment(self, name, keyword=''):
        """根据商品名称和关键词自动分类"""
        name_lower = name.lower()
        keyword_lower = keyword.lower()
        text = f"{name_lower} {keyword_lower}"
        
        # 自行车分类
        if any(word in text for word in ['自行车', '山地车', '公路车', '折叠车', '电动车', 'bike', 'bicycle']):
            return '自行车'
        
        # 头盔分类
        elif any(word in text for word in ['头盔', '安全帽', 'helmet']):
            return '安全防护'
        
        # 服装分类
        elif any(word in text for word in ['骑行服', '骑行裤', '手套', '骑行鞋', '袜子', 'jersey', 'shorts']):
            return '骑行服装'
        
        # 配件分类
        elif any(word in text for word in ['车灯', '码表', '水壶', '车锁', '打气筒', '工具', 'light', 'computer']):
            return '骑行配件'
        
        # 零件分类
        elif any(word in text for word in ['轮胎', '内胎', '刹车', '链条', '齿轮', '座垫', 'tire', 'brake']):
            return '自行车零件'
        
        # 默认分类
        else:
            return '其他'
    
    def _save_equipment_data(self, data):
        """保存装备数据到数据库"""
        try:
            from app import db, Equipment, EquipmentPrice, EquipmentCategory
            
            # 数据清洗
            cleaned_data = self._clean_equipment_data(data)
            
            # 检查是否已存在相同商品
            existing_equipment = Equipment.query.filter(
                Equipment.name == cleaned_data['name'],
                Equipment.source_url == cleaned_data.get('platform_url')
            ).first()
            
            if existing_equipment:
                # 更新现有商品信息
                existing_equipment.price = cleaned_data['price']
                existing_equipment.updated_at = datetime.now()
                equipment_id = existing_equipment.id
                logger.info(f"更新现有装备: {cleaned_data['name']}")
            else:
                # 按分类名称查找分类ID，找不到时逐级回退
                category_name = self._classify_equipment(cleaned_data['name'], cleaned_data.get('keyword', ''))
                category = EquipmentCategory.query.filter_by(name=category_name).first()
                if not category:
                    category = EquipmentCategory.query.filter_by(name='骑行装备').first()
                if not category:
                    category = EquipmentCategory.query.first()
                
                if not category:
                    logger.error("数据库中没有装备分类，无法保存爬取数据")
                    db.session.rollback()
                    return
                
                # 创建新商品
                equipment = Equipment(
                    name=cleaned_data['name'],
                    brand=cleaned_data.get('brand') or '未知品牌',
                    category_id=category.id,
                    price=cleaned_data['price'],
                    description=cleaned_data.get('description', ''),
                    images=[cleaned_data.get('image_url')] if cleaned_data.get('image_url') else [],
                    review_count=cleaned_data.get('sales', 0) or 0,
                    source=cleaned_data.get('platform') or 'unknown',
                    source_url=cleaned_data.get('platform_url', ''),
                    availability=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.session.add(equipment)
                db.session.flush()  # 获取ID
                equipment_id = equipment.id
                logger.info(f"创建新装备: {cleaned_data['name']}")
            
            # 保存价格历史
            price_record = EquipmentPrice(
                equipment_id=equipment_id,
                platform=cleaned_data['platform'],
                platform_url=cleaned_data.get('platform_url', ''),
                price=cleaned_data['price'],
                currency='CNY',
                seller_name=cleaned_data.get('shop_name', ''),
                stock_status='有货',
                is_available=True,
                created_at=datetime.now()
            )
            db.session.add(price_record)
            
            db.session.commit()
            logger.info(f"成功保存装备数据: {cleaned_data['name']} - {cleaned_data['platform']} - ¥{cleaned_data['price']}")
            
        except Exception as e:
            logger.error(f"保存装备数据失败: {str(e)}")
            if 'db' in locals():
                db.session.rollback()
    
    def get_task_status(self, task_id):
        """获取任务状态"""
        if task_id not in self.tasks:
            raise ValueError(f"任务 {task_id} 不存在")
        
        task = self.tasks[task_id].copy()
        
        # 计算运行时间
        if 'start_time' in task:
            if task['status'] == 'running':
                task['duration'] = (datetime.now() - task['start_time']).total_seconds()
            elif 'end_time' in task:
                task['duration'] = (task['end_time'] - task['start_time']).total_seconds()
        
        # 格式化时间
        if 'start_time' in task:
            task['start_time'] = task['start_time'].isoformat()
        if 'end_time' in task:
            task['end_time'] = task['end_time'].isoformat()
        
        return task
    
    def cleanup_old_tasks(self, days=7):
        """清理旧任务记录"""
        cutoff_time = datetime.now() - timedelta(days=days)
        
        tasks_to_remove = []
        for task_id, task in self.tasks.items():
            if 'start_time' in task and task['start_time'] < cutoff_time:
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
        
        logger.info(f"清理了 {len(tasks_to_remove)} 个旧任务记录")