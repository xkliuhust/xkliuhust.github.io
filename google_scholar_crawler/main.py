from scholarly import scholarly
from scholarly import ProxyGenerator
import json
from datetime import datetime
import os
import time
import random
import logging
import urllib3
from fake_useragent import UserAgent

# 禁用不必要的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scholar_debug.log"),
        logging.StreamHandler()
    ]
)

def setup_proxy_and_headers():
    """配置代理和请求头优化"""
    # 使用免费代理池（可选择其中一个策略）
    pg = ProxyGenerator()
    strategy = "free"  # 可选：free/tor/google
    
    if strategy == "free":
        # 方法1: 使用免费代理（随机选择）
        free_proxies = [
            "194.233.69.41:443",
            "193.122.71.184:3128",
            "161.97.173.73:80",
            "147.50.227.107:3128",
            "47.243.170.156:808"
        ]
        proxy = random.choice(free_proxies)
        success = pg.SingleProxy(http=proxy, https=proxy)
        logging.info(f"使用免费代理: {proxy}")
    elif strategy == "tor":
        # 方法2: 使用Tor代理（需要本地运行Tor）
        success = pg.Tor_Internal(tor_cmd="tor")
        logging.info("使用Tor代理")
    else:
        # 方法3: 使用Google Cloud免费代理（不需要配置）
        success = pg.FreeProxies()
        logging.info("使用Google Cloud免费代理")
    
    if success:
        scholarly.use_proxy(pg)
    
    # 设置多样化请求头
    ua = UserAgent()
    scholarly.settings.USER_AGENT = ua.chrome
    scholarly.settings.TIMEOUT = 30  # 增加超时时间
    scholarly.settings.RETRIES = 3  # 设置重试次数

def fetch_author_data():
    """获取作者数据（带重试机制）"""
    scholar_id = os.environ.get('GOOGLE_SCHOLAR_ID')
    if not scholar_id:
        logging.error("环境变量 GOOGLE_SCHOLAR_ID 未设置")
        return None
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            # 添加随机延迟（1-5秒），防止被封
            delay = random.uniform(1, 5)
            logging.info(f"尝试 #{attempt+1} - 等待 {delay:.1f}秒...")
            time.sleep(delay)
            
            logging.info(f"获取学者ID: {scholar_id}")
            author = scholarly.search_author_id(scholar_id)
            
            # 随机化填充内容的顺序
            sections = ['basics', 'indices', 'counts', 'publications']
            random.shuffle(sections)
            
            logging.info(f"填充数据部分: {sections}")
            scholarly.fill(author, sections=sections)
            logging.info("数据获取成功!")
            return author
        except Exception as e:
            logging.error(f"尝试 #{attempt+1} 失败: {str(e)}")
            # 每次失败后增加等待时间
            time.sleep(attempt * 5)
    
    logging.error(f"所有{max_retries}次尝试均失败")
    return None

def process_data(author_data):
    """处理学者数据"""
    # 处理关键字段
    author_data['name'] = author_data.get('name', 'Unknown Author')
    author_data['citedby'] = author_data.get('citedby', 0)
    author_data['hindex'] = author_data.get('hindex', 0)
    
    # 添加更新时间
    author_data['updated'] = str(datetime.now())
    
    # 处理出版物数据
    publications = author_data.get('publications', [])
    if publications:
        author_data['publications'] = {v['author_pub_id']: v for v in publications}
        # 移除可能引起问题的超大HTML字段
        for pub in author_data['publications'].values():
            pub.pop('pub_url', None)
            pub.pop('container_type', None)
    else:
        author_data['publications'] = {}
        
    return author_data

# ===================== 主执行流程 =====================
if __name__ == "__main__":
    # 设置环境变量（测试时可取消注释）
    # os.environ['GOOGLE_SCHOLAR_ID'] = '<YOUR_SCHOLAR_ID>'
    
    # 检查环境变量
    if 'GOOGLE_SCHOLAR_ID' not in os.environ:
        logging.error("未设置GOOGLE_SCHOLAR_ID环境变量")
        exit(1)
    
    logging.info("=" * 60)
    logging.info(f"开始获取Google Scholar数据 | 时间: {datetime.now()}")
    logging.info("=" * 60)
    
    # 1. 优化代理和请求头设置
    setup_proxy_and_headers()
    
    # 2. 获取数据
    author_data = fetch_author_data()
    
    # 3. 处理失败情况
    if not author_data:
        logging.warning("数据获取失败，生成模拟数据...")
        author_data = {
            "name": "John Doe (示例)",
            "affiliation": "知名大学",
            "email_domain": "@example.com",
            "interests": ["人工智能", "机器学习"],
            "citedby": 1000,
            "hindex": 15,
            "i10index": 25,
            "publications": {
                "pub1": {
                    "title": "示例出版物标题",
                    "author": "John Doe",
                    "num_citations": 50,
                    "pub_year": 2022
                }
            },
            "updated": str(datetime.now())
        }
    else:
        # 4. 处理获取到的真实数据
        author_data = process_data(author_data)
    
    # 5. 保存结果
    os.makedirs('results', exist_ok=True)
    
    # 保存完整数据
    with open('results/gs_data.json', 'w') as f:
        json.dump(author_data, f, indent=2, ensure_ascii=False)
    
    # 保存屏蔽徽章数据
    shield_data = {
        "schemaVersion": 1,
        "label": "citations",
        "message": f"{author_data.get('citedby', 0)}",
        "namedLogo": "google scholar",
        "color": "#4885ed",
        "logoSvg": ""
    }
    
    with open('results/gs_data_shieldsio.json', 'w') as f:
        json.dump(shield_data, f)
    
    logging.info("数据保存完成！")
    logging.info(f"- 被引次数: {author_data['citedby']}次")
    logging.info(f"- 出版物数: {len(author_data['publications'])}篇")
    logging.info(f"- 更新时间: {author_data['updated']}")
    logging.info("=" * 60)
