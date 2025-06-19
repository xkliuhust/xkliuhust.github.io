import json
from datetime import datetime
import os
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
import re

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/126.0"
]

def safe_request(url, max_retries=5, timeout=30):
    """带有重试机制和安全异常处理的自定义请求函数"""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://scholar.google.com/",
        "DNT": "1"
    }
    
    backoff_times = [1, 2, 3, 5, 8]  # 退避时间（秒）
    
    for attempt in range(max_retries):
        try:
            # 在请求之间添加随机延迟
            if attempt > 0:
                delay = backoff_times[attempt-1] + random.random() * 1.5
                logging.info(f"重试 #{attempt+1}/{max_retries} - 等待 {delay:.1f}秒...")
                time.sleep(delay)
            
            response = requests.get(
                url, 
                headers=headers, 
                timeout=timeout,
                allow_redirects=True
            )
            
            # 检查是否在CAPTCHA页面上
            if "sorry" in response.url or "captcha" in response.text.lower():
                raise Exception(f"被重定向到CAPTCHA页面: {response.url}")
            
            if 200 <= response.status_code < 300:
                return response
            
            # 处理403禁止访问的情况
            if response.status_code == 403:
                raise Exception(f"服务器拒绝访问 (403 Forbidden)")
            
            # 处理429过快访问
            if response.status_code == 429:
                raise Exception(f"请求过多 (429 Too Many Requests)")
                
            response.raise_for_status()
            
        except Exception as e:
            last_error = str(e)
            logging.error(f"{url} 请求失败 (尝试 {attempt+1}/{max_retries}): {last_error}")
            
            # 如果是最后一次尝试，则重新抛出异常
            if attempt == max_retries - 1:
                raise
    
    return None  # 不应该到达这里

def parse_scholar_profile(html_content):
    """解析Google Scholar个人页面HTML内容"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 提取学者名称
    name_element = soup.find('div', id='gsc_prf_in')
    name = name_element.text.strip() if name_element else "未知学者"
    
    # 提取引用信息
    citations_element = soup.find('td', class_='gsc_rsb_std', string=re.compile(r'被引用次数'))
    citations = int(citations_element.text.strip()) if citations_element else 0
    
    # 提取h-index
    hindex_element = soup.select_one('td.gsc_rsb_std:nth-child(2)')
    if hindex_element:
        hindex = int(hindex_element.text.strip())
    else:
        # 尝试替代查找方式
        hindex_row = soup.find('td', class_='gsc_rsb_sc1', string='h指数')
        hindex = int(hindex_row.find_next_sibling('td').text.strip()) if hindex_row else 0
    
    # 提取i10-index
    i10_row = soup.find('td', class_='gsc_rsb_sc1', string='i10指数')
    i10index = int(i10_row.find_next_sibling('td').text.strip()) if i10_row else 0
    
    # 提取最后更新的时间
    updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 创建结构化数据
    profile_data = {
        "name": name,
        "citedby": citations,
        "hindex": hindex,
        "i10index": i10index,
        "updated": updated,
        "source": "HTML直接抓取"
    }
    
    return profile_data

def simulate_scholar_api(scholar_id):
    """模拟API调用来获取数据（不使用scholarly库）"""
    # 获取公共信息的基础URL
    base_url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
    
    logging.info(f"抓取Google Scholar页面: {base_url}")
    response = safe_request(base_url)
    
    # 检查是否有有效响应
    if not response:
        return {"error": "所有请求尝试均失败"}
    
    profile_data = parse_scholar_profile(response.text)
    
    # 添加Scholar ID
    profile_data["scholar_id"] = scholar_id
    
    return profile_data

def save_results(data, target_dir="results"):
    """保存抓取结果到文件"""
    os.makedirs(target_dir, exist_ok=True)
    
    # 1. 保存完整JSON数据
    with open(f'{target_dir}/gs_data.json', 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    # 2. 保存Shields.io徽章数据
    shield_data = {
        "schemaVersion": 1,
        "label": "学术引用",
        "message": f"{data.get('citedby', 0)}",
        "color": "brightgreen",
        "logoSvg": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
    <path d="M20.5 6.1c1.4 0 2.5 1.1 2.5 2.5v7c0 1.4-1.1 2.5-2.5 2.5h-17c-1.4 0-2.5-1.1-2.5-2.5v-7c0-1.4 1.1-2.5 2.5-2.5h17zm0 1h-17c-.8 0-1.5.7-1.5 1.5v7c0 .8.7 1.5 1.5 1.5h17c.8 0 1.5-.7 1.5-1.5v-7c0-.8-.7-1.5-1.5-1.5zm-8.5 8c.4 0 .8.3.8.7s-.4.7-.8.7h-7c-.4 0-.7-.3-.7-.7s.3-.7.7-.7h7zm7-5c.4 0 .7.3.7.7s-.3.7-.7.7h-14c-.4 0-.7-.3-.7-.7s.3-.7.7-.7h14z"/>
    </svg>"""
    }
    
    with open(f'{target_dir}/gs_data_shieldsio.json', 'w') as f:
        json.dump(shield_data, f, ensure_ascii=False)
    
    # 3. 保存人类可读摘要
    summary = f"""Google Scholar 数据更新

学者ID: {data.get('scholar_id', '未提供')}
姓名: {data.get('name', '未知')}
被引次数: {data.get('citedby', 0)}
h-index: {data.get('hindex', 0)}
i10-index: {data.get('i10index', 0)}
更新时间: {data.get('updated', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}
数据来源: {data.get('source', '直接抓取')}

--- 自动生成于 Google Scholar 数据抓取器 ---"""
    
    with open(f'{target_dir}/summary.txt', 'w') as f:
        f.write(summary)
    
    # 4. 保存原始HTML（用于调试）
    if 'html' in data:
        with open(f'{target_dir}/raw_page.html', 'w', encoding='utf-8') as f:
            f.write(data['html'])
    
    return True

# ===================== 主执行流程 =====================
if __name__ == "__main__":
    # 初始化日志
    logging.info("=" * 50)
    logging.info("Google Scholar 数据抓取器启动")
    logging.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取Scholar ID
    scholar_id = os.environ.get('GOOGLE_SCHOLAR_ID')
    if not scholar_id:
        # 使用默认值（示例）
        scholar_id = "B7vSqZsAAAAJ"  # Andrew Ng的Scholar ID作为示例
        logging.warning(f"未设置环境变量 GOOGLE_SCHOLAR_ID, 使用默认示例ID: {scholar_id}")
    
    logging.info(f"目标学者ID: {scholar_id}")
    
    try:
        # 获取数据
        start_time = time.time()
        scholar_data = simulate_scholar_api(scholar_id)
        elapsed = time.time() - start_time
        
        # 添加处理时间
        scholar_data["processing_time"] = f"{elapsed:.2f} 秒"
        
        # 保存结果
        save_results(scholar_data)
        
        # 成功日志
        logging.info(f"成功抓取数据! 用时 {elapsed:.2f} 秒")
        logging.info(f"- 姓名: {scholar_data['name']}")
        logging.info(f"- 被引次数: {scholar_data['citedby']}")
        logging.info(f"- h-index: {scholar_data['hindex']}")
        
    except Exception as e:
        # 创建错误报告
        error_data = {
            "error": f"抓取失败: {str(e)}",
            "scholar_id": scholar_id,
            "timestamp": datetime.now().isoformat()
        }
        
        # 保存错误结果而不是让整个流程失败
        save_results(error_data)
        logging.error(f"发生无法处理的错误: {str(e)}")
    
    finally:
        logging.info("=" * 50)
        logging.info("流程完成\n")
