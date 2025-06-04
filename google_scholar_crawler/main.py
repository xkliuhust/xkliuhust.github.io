from scholarly import scholarly
import json
from datetime import datetime
import os
import time
import random
import re
import sys
from bs4 import BeautifulSoup
import requests

# 重试次数和延迟配置
MAX_RETRIES = 5
RETRY_DELAY_BASE = 20  # 基础延迟秒数

# 模拟真实浏览器的用户代理列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.160 Safari/537.36'
]

# 更新headers和代理设置
def setup_scholarly():
    # 随机选择用户代理
    user_agent = random.choice(USER_AGENTS)
    
    scholarly.set_headers({
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://scholar.google.com/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    })
    
    # 如果可以使用代理，在这里设置
    # scholarly.use_proxy(http='your-proxy', https='your-proxy')

# 防御性解析引用数
def parse_citedby_from_html(author_id):
    """直接从HTML解析引用数，避免API限制"""
    try:
        # 创建Google Scholar URL
        url = f"https://scholar.google.com/citations?hl=en&user={author_id}"
        
        # 发送带自定义headers的请求
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 验证是否被重定向到验证码页面
        if "https://www.google.com/sorry/index" in response.url:
            print("Google Scholar redirected to captcha page")
            return None
        
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 查找引用数 - 尝试多个选择器
        citedby_elem = (
            # 新版本选择器
            soup.select_one('#gsc_rsb_st .gsc_rsb_sc1 tr:nth-child(2) .gsc_rsb_sc2') or
            soup.select_one('.gsc_rsb_std[data-src="gsc_prf_cit"]') or
            soup.select_one('.gsc_rsb_st[name="c"]') or
            # 旧版本选择器
            soup.select_one('#gsc_rsb_st > tbody > tr:nth-child(1) > td:nth-child(2)')
        )
        
        if not citedby_elem:
            # 尝试备份解析方式
            citedby_text = re.search(r'Citations\D+(\d+)', response.text)
            if citedby_text:
                return int(citedby_text.group(1).replace(',', ''))
            return None
        
        citedby_value = citedby_elem.text.strip().replace(',', '')
        return int(citedby_value) if citedby_value.isdigit() else None
    except Exception as e:
        print(f"HTML parse error: {str(e)}")
        return None

def main():
    try:
        author_id = os.environ['GOOGLE_SCHOLAR_ID']
        print(f"Starting for author ID: {author_id}")
        
        # 尝试次数计数器
        attempts = 0
        
        while attempts < MAX_RETRIES:
            attempts += 1
            setup_scholarly()  # 每次尝试前重新设置headers
            
            try:
                # STEP 1: 直接获取引文数（绕过scholarly的解析问题）
                citedby = parse_citedby_from_html(author_id)
                
                if citedby is not None:
                    print(f"Parsed citations directly: {citedby}")
                    break
                else:
                    print(f"Direct parse failed. Using scholarly API... (Attempt {attempts}/{MAX_RETRIES})")
                    
                    # STEP 2: 回退到scholarly API
                    author = scholarly.search_author_id(author_id)
                    scholarly.fill(author, sections=['basics'])
                    
                    if 'citedby' in author and author['citedby'] > 0:
                        citedby = author['citedby']
                        print(f"Scholarly API citations: {citedby}")
                        break
                    else:
                        print(f"Scholarly returned 0 citations. Retrying...")
            except Exception as e:
                print(f"Attempt {attempts} failed: {type(e).__name__} - {str(e)}")
            
            # 指数退避策略：增加延迟时间
            delay = RETRY_DELAY_BASE * (2 ** attempts) + random.uniform(0, 10)
            print(f"Waiting {delay:.1f} seconds before next attempt...")
            time.sleep(delay)
        
        # 如果所有尝试都失败，使用回退值
        if citedby is None:
            print(f"All attempts failed. Using fallback citations.")
            citedby = 0
        
        # 构造基本作者信息，即使其他调用失败
        author = {
            'name': "Your Name",  # 默认名称，可修改
            'citedby': citedby,
            'updated': str(datetime.now()),
            'publications': {}
        }
        
        # STEP 3: 只在有引用数的情况下尝试获取出版物
        if citedby > 0:
            try:
                setup_scholarly()
                print("Fetching publications...")
                scholarly.fill(author, sections=['publications'])
            except Exception as e:
                print(f"Publications fetch failed: {str(e)}")
        
        # 格式化出版物
        if 'publications' in author:
            publications_map = {}
            for pub in author['publications']:
                pub_id = pub.get('author_pub_id')
                if pub_id:
                    pub.setdefault('title', 'Untitled Publication')
                    publications_map[pub_id] = pub
            author['publications'] = publications_map
        else:
            author['publications'] = {}
        
        # 输出结果
        print(f"Final citations: {author['citedby']}")
        print(f"Publications count: {len(author['publications'])}")
        
        # 保存结果
        os.makedirs('results', exist_ok=True)
        with open('results/gs_data.json', 'w') as outfile:
            json.dump(author, outfile, ensure_ascii=False, indent=2)
        
        shieldio_data = {
            "schemaVersion": 1,
            "label": "citations",
            "message": f"{author['citedby']}",
            "color": "brightgreen" if author['citedby'] > 0 else "orange"
        }
        
        with open('results/gs_data_shieldsio.json', 'w') as outfile:
            json.dump(shieldio_data, outfile)
        
        print("Data saved successfully.")
        
    except Exception as e:
        print(f"Critical error in main: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
