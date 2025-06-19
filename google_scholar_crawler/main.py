from scholarly import scholarly, ProxyGenerator
import json
from datetime import datetime
import os
import time
import random
import logging
import urllib3
import requests
from bs4 import BeautifulSoup

# 禁用不必要的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
]

def setup_proxy():
    """配置代理，使用 Tor 或免费代理"""
    pg = ProxyGenerator()
    
    if os.environ.get("USE_TOR_PROXY", "false").lower() == "true":
        # 使用 Tor 代理（GitHub Actions 中需配置 Tor 服务）
        pg.Tor_Internal(proxy_port=9050)
        logging.info("使用 Tor 代理")
    else:
        # 使用免费代理（备选方案）
        pg.FreeProxies()
        logging.info("使用免费代理")
    
    try:
        scholarly.use_proxy(pg)
        logging.info("代理设置成功")
        return True
    except Exception as e:
        logging.error(f"代理设置失败: {e}")
        return False

def fetch_author_data():
    """获取学者数据（具有更好的错误处理和重试机制）"""
    scholar_id = os.environ.get('GOOGLE_SCHOLAR_ID')
    if not scholar_id:
        logging.error("环境变量 GOOGLE_ SCHOLAR_ID 未设置")
        raise ValueError("Google Scholar ID 未配置")
    
    max_retries = 5
    backoff_factor = 2
    
    current_settings = scholarly.settings
    logging.info(f"当前scholarly设置: {current_settings}")
    
    # 设置全局请求配置
    scholarly.set_retries(3)
    scholarly.set_timeout(30)
    
    for attempt in range(1, max_retries + 1):
        try:
            # 设置随机 User-Agent
            scholarly.headers.update({"User-Agent": random.choice(USER_AGENTS)})
            
            # 添加随机延迟，防止被屏蔽
            delay = random.uniform(1, 3) + (attempt - 1) * backoff_factor
            logging.info(f"尝试 #{attempt} - 等待 {delay:.1f}秒...")
            time.sleep(delay)
            
            # 获取作者数据
            logging.info(f"获取作者数据 ID: {scholar_id}")
            author = scholarly.search_author_id(scholar_id)
            
            # 定义并随机化要填充的部分
            sections = ['basics', 'indices', 'counts', 'publications']
            random.shuffle(sections)
            
            # 仅填充必要的基础信息（提高成功率）
            scholarly.fill(author, sections=['basics', 'indices', 'counts'])
            
            # 单独处理出版物（最容易失败的部分）
            try:
                logging.info("尝试获取出版物列表...")
                scholarly.fill(author, sections=['publications'])
            except Exception as pub_error:
                logging.error(f"获取出版物失败: {pub_error}")
            
            logging.info("数据获取成功!")
            return author
        except requests.exceptions.RequestException as e:
            logging.error(f"网络请求错误 (尝试 {attempt}/{max_retries}): {str(e)}")
            time.sleep(attempt * 5)  # 递增的等待时间
        except Exception as e:
            logging.error(f"处理过程中出错 (尝试 {attempt}/{max_retries}): {str(e)}")
            time.sleep(attempt * 3)  # 递增的等待时间
    
    logging.error(f"所有 {max_retries} 次尝试均失败")
    return None

def manual_fallback(scholar_id):
    """当 scholarly 失败时的备选方案：抓取公开页面"""
    try:
        url = f"https://scholar.google.com/citations?user={scholar_id}"
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 解析关键指标
        citedby = soup.select_one("#gsc_rsb_st tbody tr:nth-child(1) td:nth-child(2)").text
        citedby = int(''.join(filter(str.isdigit, citedby))) if citedby else 0
        
        # 解析 h-index
        hindex = soup.select_one("#gsc_rsb_st tbody tr:nth-child(2) td:nth-child(2)").text
        hindex = int(''.join(filter(str.isdigit, hindex))) if hindex else 0
        
        # 创建简化数据
        return {
            "name": "数据获取失败，使用公开API",
            "citedby": citedby,
            "hindex": hindex,
            "publications": [],
            "updated": str(datetime.now()),
            "source": "manual_fallback"
        }
    except Exception as e:
        logging.error(f"备选方案也失败: {str(e)}")
        return {
            "name": "错误：所有尝试失败",
            "citedby": 0,
            "hindex": 0,
            "publications": [],
            "updated": str(datetime.now()),
            "source": "fallback"
        }

def process_data(author_data):
    """处理并精简数据以适应GitHub限制"""
    # 获取基本指标
    citedby = author_data.get('citedby', 0)
    hindex = author_data.get('hindex', 0)
    
    # 处理publications字段（避免超出GitHub文件大小限制）
    publications = author_data.get('publications', [])
    if publications:
        # 筛选必要字段，减少大小
        cleaned_pubs = []
        for pub in publications:
            # 避免处理None值的异常
            if not isinstance(pub, dict):
                continue
                
            cleaned = {
                "title": pub.get('bib', {}).get('title', ''),
                "year": pub.get('bib', {}).get('pub_year', ''),
                "citation": pub.get("num_citations", 0)
            }
            cleaned_pubs.append(cleaned)
    else:
        cleaned_pubs = []
    
    # 创建精简的数据结构
    processed = {
        "name": author_data.get("name", "Unknown"),
        "affiliation": author_data.get("affiliation", ""),
        "citedby": citedby,
        "hindex": hindex,
        "total_publications": len(cleaned_pubs),
        "publications_sample": cleaned_pubs[:3],  # 仅保存少量样例
        "updated": author_data.get("updated", str(datetime.now())),
        "source": author_data.get("source", "scholarly")
    }
    
    return processed

# ===================== 主执行流程 =====================
if __name__ == "__main__":
    logging.info("=" * 60)
    logging.info("开始 Google Scholar 数据抓取工作流")
    logging.info("=" * 60)
    
    # 1. 设置代理
    setup_proxy()
    
    # 2. 获取学者数据
    scholar_id = os.environ.get('GOOGLE_SCHOLAR_ID')
    author_data = fetch_author_data()
    
    # 3. 处理失败情况
    if not author_data:
        logging.warning("主要方法失败，尝试备选方案...")
        author_data = manual_fallback(scholar_id)
    
    # 4. 添加更新时间戳
    author_data["updated"] = str(datetime.now())
    
    # 5. 处理数据
    final_data = process_data(author_data)
    
    # 6. 保存结果
    os.makedirs('results', exist_ok=True)
    
    # 保存完整数据
    with open('results/gs_data.json', 'w') as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)
    
    # 保存屏蔽徽章数据
    shield_data = {
        "schemaVersion": 1,
        "label": "Google Scholar 引用",
        "message": f"{final_data.get('citedby', 0)}",
        "color": "blue",
        "namedLogo": "google scholar",
        "logoSvg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="#4285F4" d="M12 24a7 7 0 100-14 7 7 0 000 14z"/><path fill="#34A853" d="M18 10A6 6 0 116 10c0 3.32 2.69 6 6 6s6-2.68 6-6z"/><path fill="#FBBC05" d="M12 7a3 3 0 100 6 3 3 0 000-6z"/><path fill="#EA4335" d="M12 16c-2.76 0-5-1.79-5-4h10c0 2.21-2.24 4-5 4z"/></svg>'
    }
    
    with open('results/gs_data_shieldsio.json', 'w') as f:
        json.dump(shield_data, f)
    
    # 保存文本文件便于在 Actions 日志中查看
    with open('results/summary.txt', 'w') as f:
        f.write(f"更新于: {final_data['updated']}\n")
        f.write(f"姓名: {final_data['name']}\n")
        f.write(f"引用次数: {final_data['citedby']}\n")
        f.write(f"h-index: {final_data['hindex']}\n")
    
    logging.info("=" * 60)
    logging.info("数据抓取完成!")
    logging.info(f"- 被引次数: {final_data['citedby']}")
    logging.info(f"- H指数: {final_data['hindex']}")
    logging.info(f"- 出版物数量: {final_data['total_publications']}")
    logging.info(f"数据来源: {final_data.get('source', 'scholarly')}")
    logging.info("=" * 60)
