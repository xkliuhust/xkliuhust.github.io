import os
import json
import time
import random
from scholarly import scholarly

# 超时设置
TIMEOUT = 30  # 整个获取过程的超时时间（秒）
MAX_RETRIES = 5

# 缓存文件路径
CACHE_FILE = 'results/gs_data.json'

def fetch_scholarly_data(author_id):
    """通过scholarly获取作者数据，带重试机制"""
    start_time = time.time()
    for retry in range(MAX_RETRIES):
        try:
            # 设置随机的用户代理（可选）
            # scholarly.set_user_agent('Mozilla/5.0 ...')
            author = scholarly.search_author_id(author_id)
            scholarly.fill(author, sections=['basics', 'indices', 'counts', 'publications'])
            return author
        except Exception as e:
            elapsed = time.time() - start_time
            if elapsed > TIMEOUT:
                raise RuntimeError(f'Fetch timed out after {TIMEOUT} seconds') from e
            wait = 10 + random.randint(0, 10)  # 等待10到20秒
            time.sleep(wait)
    raise RuntimeError(f'Failed after {MAX_RETRIES} retries')

def get_cached_data():
    """从缓存文件中读取数据"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return None

def save_cache(data):
    """保存数据到缓存文件"""
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f)

def main():
    author_id = os.environ.get('GOOGLE_SCHOLAR_ID')
    if not author_id:
        raise ValueError('GOOGLE_SCHOLAR_ID not set')

    try:
        data = fetch_scholarly_data(author_id)
        # 提取需要的信息        citedby = data.get('citedby', 0)
        # ... 提取其他信息
        # 保存最新数据到缓存
        save_cache({'citedby': citedby})
        print("Successfully fetched new data")
    except Exception as e:
        print(f"Error fetching data: {str(e)}")
        # 尝试使用缓存
        cached_data = get_cached_data()
        if cached_data:
            citedby = cached_data['citedby']
            print("Using cached data")
        else:
            citedby = 0  # 或使用其他默认值
            print("No cache available, using default")

    # 接下来使用citedby更新README等操作
    print(f"Citedby: {citedby}")

if __name__ == "__main__":
    main()
