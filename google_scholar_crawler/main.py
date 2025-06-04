from scholarly import scholarly
import json
from datetime import datetime
import os
import time
import random
from requests.exceptions import HTTPError
import sys

# 初始化参数
RETRY_MAX = 3
RETRY_DELAY = 15  # 基础延迟秒数
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0'
]

# 重试封装函数
def scholarly_retry(func, *args, **kwargs):
    for attempt in range(RETRY_MAX):
        try:
            # 随机切换User-Agent
            scholarly.set_headers({
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            })
            
            if attempt > 0:
                print(f"Attempt {attempt+1}/{RETRY_MAX}: Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY + random.randint(0, 10))  # 随机延迟
                
            return func(*args, **kwargs)
        except HTTPError as e:
            print(f"HTTP Error ({e.response.status_code}): {e.response.text[:200]}")
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {type(e).__name__} - {str(e)}")
    
    # 所有重试失败后回退
    print("All attempts failed. Using fallback data.")
    return {
        "name": "Google Scholar Data Unavailable",
        "citedby": 0,
        "publications": {},
        "affiliation": "",
        "interests": [],
        "updated": str(datetime.now())
    }

# 主逻辑
try:
    author_id = os.environ['GOOGLE_SCHOLAR_ID']
    author = scholarly_retry(scholarly.search_author_id, author_id)
    
    # 只获取必要数据减少请求量
    scholarly_retry(scholarly.fill, author, 
                    sections=['basics', 'indices', 'publications'])
    
    # 更新其他字段
    author['updated'] = str(datetime.now())
    
    # 保护性处理关键字段
    author['citedby'] = author.get('citedby', 0)
    author['publications'] = author.get('publications', [])
    
    # 格式化publications
    publications_map = {}
    for pub in author['publications']:
        pub_id = pub.get('author_pub_id')
        if pub_id:
            # 保护性处理可能缺少的字段
            pub.setdefault('title', 'Untitled Publication')
            pub.setdefault('num_citations', 0)
            publications_map[pub_id] = pub
    
    author['publications'] = publications_map
    
except Exception as e:
    print(f"Unexpected error: {str(e)}")
    # 致命错误回退
    author = {
        "name": "Data Unavailable",
        "citedby": 0,
        "publications": {},
        "updated": str(datetime.now())
    }

# 输出结果
print(f"Author: {author.get('name', 'Unknown')}")
print(f"Citations: {author.get('citedby', 0)}")
print(f"Publications: {len(author.get('publications', {}))}")

os.makedirs('results', exist_ok=True)
with open('results/gs_data.json', 'w') as outfile:
    json.dump(author, outfile, ensure_ascii=False, indent=2)

shieldio_data = {
  "schemaVersion": 1,
  "label": "citations",
  "message": f"{author.get('citedby', 0)}",
  "color": "blue" if author.get('citedby', 0) > 0 else "gray"
}

with open('results/gs_data_shieldsio.json', 'w') as outfile:
    json.dump(shieldio_data, outfile)
