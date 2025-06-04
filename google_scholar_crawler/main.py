import os
import json
import time
import pytesseract
from PIL import Image
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException

def setup_browser():
    """配置无头浏览器"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
    ]
    chrome_options.add_argument(f'user-agent={random.choice(user_agents)}')
    
    return webdriver.Chrome(options=chrome_options)

def save_element_screenshot(element, filename):
    """保存特定元素的屏幕截图"""
    location = element.location_once_scrolled_into_view
    size = element.size
    
    # 截图并裁剪到元素区域
    driver.save_screenshot('full_page.png')
    page_img = Image.open('full_page.png')
    
    left = location['x']
    top = location['y']
    right = left + size['width']
    bottom = top + size['height']
    
    element_img = page_img.crop((left, top, right, bottom))
    element_img.save(filename)
    return filename

def ocr_extract_text_from_image(image_path):
    """从图片中提取文字"""
    img = Image.open(image_path)
    return pytesseract.image_to_string(img).strip()

def scrape_scholar_profile():
    """主抓取流程"""
    scholar_id = os.environ['GOOGLE_SCHOLAR_ID']
    print(f"正在获取Google Scholar ID为 {scholar_id} 的个人资料...")
    
    driver = setup_browser()
    citations = 0
    profile_title = "Google Scholar"
    
    try:
        # 1. 设置长超时时间
        driver.set_page_load_timeout(60)
        
        # 2. 访问Google Scholar个人页面
        profile_url = f"https://scholar.google.com/citations?hl=en&user={scholar_id}"
        driver.get(profile_url)
        
        # 3. 等待关键元素加载
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "gsc_prf"))
        )
        print("个人资料页面加载完成")
        
        # 4. 获取个人名称
        name_element = driver.find_element(By.ID, "gsc_prf_in")
        profile_title = name_element.text
        
        # 5. 获取并处理引用总数
        citations_element = None
        try:
            # 尝试查找常见位置的引用元素
            citations_element = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, "gsc_rsb_cit"))
            )
            citations = citations_element.text.replace('Cited by', '').strip()
        except TimeoutException:
            print("无法找到引用元素，尝试OCR方法")
            
        # 6. 如果无法获取文本值，使用OCR
        if not citations or not citations.isdigit():
            print("使用OCR作为备选方案")
            
            # 截取包含引用数的区域
            citation_box = driver.find_element(By.CSS_SELECTOR, "#gsc_rsb_st .gsc_rsb_std")
            screenshot_path = save_element_screenshot(citation_box, "citations_box.png")
            
            # OCR处理数字
            ocr_text = ocr_extract_text_from_image(screenshot_path)
            num_only = ''.join(filter(str.isdigit, ocr_text))
            citations = int(num_only) if num_only else 0
        
        # 7. 确保citation是数字
        citations = int(citations) if citations.isdigit() else 0
        print(f"获取到的引用数: {citations}")
        
    except (TimeoutException, WebDriverException) as e:
        print(f"浏览器错误: {str(e)}")
    finally:
        driver.quit()
        print("浏览器已关闭")
    
    # 返回最终结果
    return {
        "name": profile_title,
        "citedby": citations,
        "profile_url": f"https://scholar.google.com/citations?user={scholar_id}",
        "updated": datetime.now().isoformat()
    }

if __name__ == "__main__":
    print("===== Google Scholar 数据抓取程序启动 =====")
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)
    
    # 捕获可能的错误
    try:
        scholar_data = scrape_scholar_profile()
    except Exception as e:
        print(f"程序运行出现重大错误: {str(e)}")
        # 创建错误回退数据
        scholar_data = {
            "name": "Google Scholar Profile",
            "citedby": 0,
            "profile_url": "",
            "updated": datetime.now().isoformat(),
            "error": str(e)
        }
    
    # 保存完整数据
    with open(os.path.join(results_dir, 'gs_data.json'), 'w') as f:
        json.dump(scholar_data, f, indent=2, ensure_ascii=False)
    
    # 保存Shields.io需要的数据
    shield_data = {
        "schemaVersion": 1,
        "label": "citations",
        "message": str(scholar_data["citedby"]),
        "color": "blue" if scholar_data["citedby"] > 0 else "gray"
    }
    
    with open(os.path.join(results_dir, 'gs_data_shieldsio.json'), 'w') as f:
        json.dump(shield_data, f)
    
    print("数据已保存！")
    print("===== 程序执行完成 =====")
