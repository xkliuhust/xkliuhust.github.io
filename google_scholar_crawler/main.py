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
import traceback

# 重试次数和延迟配置
MAX_RETRIES = 3
RETRY_DELAY_BASE = 20  # 基础延迟秒数

# 模拟真实浏览器的用户代理列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.160 Safari/537.36'
]

def setup_scholarly():
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

def parse_citedby_from_profile_page(author_id):
    """从个人主页解析引用数（原来的parse_citedby_from_html）"""
    try:
        url = f"https://scholar.google.com/citations?hl=en&user={4TKvXE8AAAAJ}"  
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        if "https://www.google.com/sorry/index" in response.url:
            print("Google Scholar redirected to captcha page (profile)")
            return None
        
        soup = BeautifulSoup(response.text, 'lxml')
        citedby_elem = (
            soup.select_one('#gsc_rsb_st .gsc_rsb_sc1 tr:nth-child(2) .gsc_rsb_sc2') or
            soup.select_one('.gsc_rsb_std[data-src="gsc_prf_cit"]') or
            soup.select_one('.gsc_rsb_st[name="c"]') or
            soup.select_one('#gsc_rsb_st > tbody > tr:nth-child(1) > td:nth-child(2)')
        )
        
        if not citedby_elem:
            citedby_text = re.search(r'Citations\D+(\d+)', response.text)
            if citedby_text:
                return int(citedby_text.group(1).replace(',', ''))
            return None
        
        citedby_value = citedby_elem.text.strip().replace(',', '')
        return int(citedby_value) if citedby_value.isdigit() else None
    except Exception as e:
        print(f"Error parsing profile page: {str(e)}")
        return None

def parse_citedby_from_publications_page(author_id):
    """从作品列表页解析引用数"""
    try:
        url = f"https://scholar.google.com/citations?hl=en&user={author_id}"
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 在作品列表页的总引用数可能位于同一个地方
        citedby_elem = soup.select_one('#gsc_rsb_st .gsc_rsb_sc1 tr:nth-child(2) .gsc_rsb_sc2')
        if citedby_elem:
            citedby_value = citedby_elem.text.strip().replace(',', '')
            return int(citedby_value) if citedby_value.isdigit() else None
        
        # 尝试通过标题解析
        title_tag = soup.select_one('title')
        if title_tag:
            title_text = title_tag.text
            match = re.search(r'Citations:\s*(\d+)', title_text)
            if match:
                return int(match.group(1))
            # 另一种标题模式
            match = re.search(r'Google Scholar Citations: (\d+)', title_text)
            if match:
                return int(match.group(1))
            
    except Exception as e:
        print(f"Error parsing publications page: {e}")
        return None

def get_citations_with_retries(author_id):
    # 方法列表：按优先级尝试
    methods = [
        ('scholarly', lambda: get_scholarly_citations(author_id)),
        ('profile_page', lambda: parse_citedby_from_profile_page(author_id)),
        ('publications_page', lambda: parse_citedby_from_publications_page(author_id))
    ]
    
    for attempt in range(MAX_RETRIES):
        # 每次优先使用哪种方法：第一次按顺序，如果第一次失败，后续重试时随机顺序（避免同种方法连续）
        if attempt == 0:
            ordered_methods = methods
        else:
            ordered_methods = random.sample(methods, len(methods))
        
        for method_name, method_func in ordered_methods:
            print(f"Attempt {attempt+1}.{method_name}: Trying to get citations")
            try:
                citations = method_func()
                if citations is not None:
                    print(f"Success with method {method_name}: Citations={citations}")
                    return citations
            except Exception as e:
                print(f"Method {method_name} failed: {e}")
        
        if attempt < MAX_RETRIES-1:
            wait = RETRY_DELAY_BASE * (2 ** attempt) + random.uniform(0, 10)
            print(f"Waiting {wait:.1f} seconds before next attempt")
            time.sleep(wait)
    
    return None

def get_scholarly_citations(author_id):
    """使用scholarly库获取引用数"""
    try:
        setup_scholarly()
        author = scholarly.search_author_id(author_id)
        scholarly.fill(author, sections=['basics'])
        return author.get('citedby', 0)  # 这里可能返回0，表示调用成功但获取了0（可能是真实值）
    except Exception as e:
        print(f"Scholarly method error: {e}")
        # 如果出错，返回None，这样我们会重试其他方法
        return None

def main():
    author_id = os.environ.get('GOOGLE_SCHOLAR_ID')
    if not author_id:
        print("Environment variable GOOGLE_SCHOLAR_ID not set")
        author_id = input("Please enter your Google Scholar ID: ")
    
    print(f"Fetching citations for author ID: {author_id}")
    
    citations = None
    try:
        citations = get_citations_with_retries(author_id)
    except Exception as e:
        print(f"Unexpected error in get_citations_with_retries: {e}")
        traceback.print_exc()
    
    if citations is None:
        citations = 0
        print("All citation fetch methods failed. Setting to fallback value (0)")
    
    # 获取作者姓名（使用scholarly从缓存中取）
    author_name = "Your Name"
    try:
        # 这里我们使用scholarly但不重试（因为已经失败多次），只作为尝试
        setup_scholarly()
        author = scholarly.search_author_id(author_id)
        author_name = author.get('name', author_name)
    except:
        pass  # 保持默认名字
    
    result = {
        'name': author_name,
        'citedby': citations,
        'updated': str(datetime.now())
    }
    
    # 保存结果
    os.makedirs('results', exist_ok=True)
    with open('results/gs_data.json', 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    with open('results/gs_data_shieldsio.json', 'w') as f:
        json.dump({
            "schemaVersion": 1,
            "label": "citations",
            "message": str(citations),
            "color": "blue",
        }, f)
    
    print("Done.")

if __name__ == "__main__":
    main()
