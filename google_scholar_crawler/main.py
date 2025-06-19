import requests
from bs4 import BeautifulSoup
import json
import os
import random
import re
import logging
import time
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
]

def get_scholar_metrics(scholar_id):
    """直接从 Google Scholar 页面获取学术指标"""
    url = f"https://scholar.google.com/citations?user={scholar_id}"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://scholar.google.com/",
        "Dnt": "1",
    }
    
    max_retries = 3
    retry_delay = [3, 5, 8]  # 每次重试的延迟（秒）
    
    for attempt in range(max_retries):
        try:
            logger.info(f"尝试 #{attempt+1} 获取 Scholar 数据")
            
            # 每次尝试使用随机延迟
            if attempt > 0:
                delay = retry_delay[attempt-1] + random.uniform(0.5, 2)
                logger.info(f"等待 {delay:.1f}秒后重试...")
                time.sleep(delay)
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 检查是否被重定向到验证页面
            if "sorry" in response.url:
                raise Exception("被重定向到验证页面")
                
            # 检查响应内容是否是Google验证页面
            if "google.com/sorry" in response.url or "Our systems have detected unusual traffic" in response.text:
                raise Exception("触发了反机器人检测")
                
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 检查是否有有效数据
            if not soup.find('div', id='gsc_prf_in'):
                if "没有公开文件" in response.text:
                    raise Exception("找不到公开文件")
                else:
                    raise Exception("页面结构不符合预期")
                    
            # 提取姓名
            name = soup.find('div', id='gsc_prf_in').text
            
            # 提取被引用次数
            cited_by = 0
            cited_by_element = soup.select_one('td.gsc_rsb_std:nth-child(2)')
            if cited_by_element:
                cited_by = int(re.sub(r'[^\d]', '', cited_by_element.text))
            
            # 提取H指数
            h_index = 0
            try:
                # 尝试查找h-index的常规位置
                h_index_elements = soup.select('td.gsc_rsb_std')
                if len(h_index_elements) > 3:
                    h_index = int(re.sub(r'[^\d]', '', h_index_elements[2].text))
                else:
                    # 备选方案查找h指数列
                    h_index_label = soup.find('td', class_='gsc_rsb_sc1', string=re.compile(r'h-index'))
                    if h_index_label:
                        h_index = int(re.sub(r'[^\d]', '', h_index_label.find_next('td').text))
            except (AttributeError, IndexError, ValueError) as e:
                logger.warning(f"H-index检测失败: {str(e)}")
                h_index = 0
            
            # 提取i10指数
            i10_index = 0
            try:
                # 尝试查找i10-index的常规位置
                i10_index_elements = soup.select('td.gsc_rsb_std')
                if len(i10_index_elements) > 4:
                    i10_index = int(re.sub(r'[^\d]', '', i10_index_elements[4].text))
                else:
                    # 备选方案查找i10指数列
                    i10_label = soup.find('td', class_='gsc_rsb_sc1', string=re.compile(r'i10'))
                    if i10_label:
                        i10_index = int(re.sub(r'[^\d]', '', i10_label.find_next('td').text))
            except (AttributeError, IndexError, ValueError) as e:
                logger.warning(f"I10-index检测失败: {str(e)}")
                i10_index = 0
            
            # 返回成功数据
            return {
                "name": name,
                "citedby": cited_by,
                "hindex": h_index,
                "i10index": i10_index,
                "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "success": True
            }
            
        except requests.RequestException as req_err:
            logger.error(f"请求错误: {str(req_err)}")
        except Exception as gen_err:
            logger.error(f"处理错误: {str(gen_err)}")
    
    # 所有尝试都失败
    logger.error("所有尝试获取数据均失败")
    return {
        "name": "数据获取失败",
        "citedby": 0,
        "hindex": 0,
        "i10index": 0,
        "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "success": False,
        "error": "所有尝试获取数据均失败"
    }

def save_results(data, target_directory="results"):
    """保存结果到不同格式文件"""
    # 确保目标目录存在
    os.makedirs(target_directory, exist_ok=True)
    
    # 1. 保存JSON数据
    with open(f"{target_directory}/scholar_data.json", "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=2)
        logger.info(f"已保存JSON数据到 {target_directory}/scholar_data.json")
    
    # 2. 保存简版徽章数据
    shield_data = {
        "schemaVersion": 1,
        "label": "学术引用",
        "message": f"{data['citedby']}",
        "color": "brightgreen" if data['citedby'] > 0 else "red",
        "style": "flat-square",
        "logoSvg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24"><path d="M12 10l5-5h-4V3H7v2H3v4h4v7h2v-7h4v-2zm2 4v4h2v-4h-2zm-8 0v4h2v-4H6zm4 0v4h2v-4h-2z"/></svg>'
    }
    with open(f"{target_directory}/shield_data.json", "w", encoding="utf-8") as shield_file:
        json.dump(shield_data, shield_file, ensure_ascii=False)
        logger.info(f"已保存徽章数据到 {target_directory}/shield_data.json")
    
    # 3. 保存可读的TXT摘要
    with open(f"{target_directory}/summary.txt", "w", encoding="utf-8") as txt_file:
        txt_file.write(f"Google Scholar 数据更新\n")
        txt_file.write(f"更新日期: {data['updated']}\n")
        txt_file.write("=" * 30 + "\n")
        txt_file.write(f"姓名: {data['name']}\n")
        txt_file.write(f"被引用次数: {data['citedby']}\n")
        txt_file.write(f"H-index: {data['hindex']}\n")
        txt_file.write(f"I10-index: {data['i10index']}\n")
        txt_file.write(f"状态: {'成功' if data.get('success', False) else '失败'}\n")
        if not data.get('success', False):
            txt_file.write(f"错误: {data.get('error', '未知错误')}\n")
        logger.info(f"已保存摘要到 {target_directory}/summary.txt")
    
    return True

def main():
    """主程序逻辑"""
    logger.info("=" * 50)
    logger.info("开始 Google Scholar 数据抓取")
    
    # 获取 Scholar ID - 从环境变量或使用默认值
    scholar_id = os.environ.get("SCHOLAR_ID", "B7vSqZsAAAAJ")  # Andrew Ng的示例ID
    if not scholar_id.startswith("B") or len(scholar_id) != 12:
        logger.warning("使用默认 Scholar ID (Andrew Ng)")
    
    logger.info(f"使用 Scholar ID: {scholar_id}")
    
    # 获取学者数据
    start_time = time.time()
    metrics = get_scholar_metrics(scholar_id)
    elapsed = time.time() - start_time
    
    # 添加额外元数据
    metrics["id"] = scholar_id
    metrics["execution_time"] = f"{elapsed:.2f}秒"
    
    # 保存结果
    save_results(metrics)
    
    # 打印最终结果
    logger.info("=" * 50)
    logger.info(f"处理完成! 用时: {elapsed:.2f}秒")
    logger.info(f"姓名: {metrics['name']}")
    logger.info(f"被引用次数: {metrics['citedby']}")
    logger.info(f"H-index: {metrics['hindex']}")
    logger.info(f"状态: {'成功' if metrics['success'] else '失败'}")
    logger.info("=" * 50)
    
    # 非零退出码表示失败（用于 GitHub Actions）
    if not metrics.get("success", False):
        exit(1)

if __name__ == "__main__":
    main()
