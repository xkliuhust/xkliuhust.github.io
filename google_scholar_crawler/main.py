import os
import json
from datetime import datetime
import time
import random
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pytesseract
from PIL import Image, ImageEnhance
import base64

def setup_browser():
    """配置无头浏览器进行网页渲染"""
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

def enhance_image(image_path):
    """增强图像以提高OCR识别率"""
    img = Image.open(image_path)
    
    # 提高对比度
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    
    # 提高锐度
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)
    
    # 提高亮度
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(1.2)
    
    # 转换为灰度图像
    img = img.convert('L')
    
    enhanced_path = "enhanced_" + image_path
    img.save(enhanced_path)
    return enhanced_path

def ocr_extract_text_from_image(image_path):
    """从图片中提取数字"""
    try:
        
        # 增强图像并处理
        enhanced_path = enhance_image(image_path)
        img = Image.open(enhanced_path)
        custom_config = r'--oem 3 --psm 6 outputbase digits'
        text = pytesseract.image_to_string(img, config=custom_config).strip()
        
        # 提取所有数字并组合
        digits = ''.join(filter(str.isdigit, text))
        if digits:
            print(f"OCR识别结果: {digits}")
            return int(digits)
        return 0
    except Exception as e:
        print(f"OCR处理失败: {e}")
        return 0

def capture_element_screenshot(driver, element, filename):
    """捕获特定元素的截图"""
    # 滚动元素到视图中
    driver.execute_script("arguments[0].scrollIntoView(true);", element)
    time.sleep(0.5)  # 确保滚动完成
    
    # 获取元素位置
    location = element.location
    size = element.size
    
    # 保存整页截图
    driver.save_screenshot('full_page.png')
    
    # 裁剪元素区域
    img = Image.open('full_page.png')
    left = location['x']
    top = location['y']
    right = left + size['width']
    bottom = top + size['height']
    
    element_img = img.crop((left, top, right, bottom))
    element_img.save(filename)
    return filename

def parse_citations_from_html_selenium(scholar_id):
    """使用Selenium解析引文数并提供视觉备份"""
    driver = setup_browser()
    citations = 0
    
    try:
        # 1. 访问Google Scholar个人页面
        profile_url = f"https://scholar.google.com/citations?hl=en&user={scholar_id}"
        driver.get(profile_url)
        print(f"访问个人主页: {profile_url}")
        
        # 2. 等待元素加载
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "gsc_rsb_cit"))
        )
        
        # 3. 尝试解析引文数字
        try:
            citations_element = driver.find_element(By.ID, "gsc_rsb_cit")
            citations_text = citations_element.text.replace('Cited by', '').replace(',', '').strip()
            if citations_text.isdigit():
                print(f"成功解析引文数: {citations_text}")
                return int(citations_text)
        except:
            pass
        
        # 4. 使用视觉方式作为备份
        try:
            citation_container = driver.find_element(By.CSS_SELECTOR, "#gsc_rsb_cit")
            screenshot_path = capture_element_screenshot(driver, citation_container, "citations_screenshot.png")
            citations = ocr_extract_text_from_image(screenshot_path)
            print(f"视觉解析引文数: {citations}")
        except Exception as e:
            print(f"视觉解析失败: {e}")
        
        return citations
    
    except Exception as e:
        print(f"Selenium解析异常: {e}")
        return citations
    finally:
        driver.quit()

def update_about_md(citation_count):
    """更新About.md文件"""
    try:
        # 读取现有的About.md文件
        with open('About.md', 'r', encoding='utf-8') as file:
            content = file.read()
        
        # 替换引文数占位符
        new_content = re.sub(
            r'<span id=\'total_cit\'>\[loading\]</span>',
            f'<span id=\'total_cit\'>{citation_count}</span>',
            content
        )
        
        # 保存更新后的文件
        with open('About.md', 'w', encoding='utf-8') as file:
            file.write(new_content)
        
        print("About.md文件更新成功")
        return True
    
    except Exception as e:
        print(f"更新About.md失败: {e}")
        return False

def create_shieldio_endpoint(citations):
    """创建Shields.io端点所需的JSON文件"""
    shieldio_data = {
        "schemaVersion": 1,
        "label": "citations",
        "message": str(citations),
        "color": "blue",
        "namedLogo": "google-scholar",
        "logoColor": "4285F4",
        "style": "flat"
    }
    
    os.makedirs('results', exist_ok=True)
    with open('results/gs_data_shieldsio.json', 'w') as f:
        json.dump(shieldio_data, f)
    
    # 返回Shields.io端点URL
    return "https://github.citation.shields.endpoint/results/gs_data_shieldsio.json"

def main():
    try:
        scholar_id = os.environ['GOOGLE_SCHOLAR_ID']
        print(f"=== 开始处理Google Scholar数据，ID: {scholar_id} ===")
        
        # 尝试使用Selenium解析引文数
        citations = parse_citations_from_html_selenium(scholar_id)
        print(f"最终引文数: {citations}")
        
        # 准备完整的数据结构
        scholar_data = {
            "name": f"Google Scholar: {scholar_id}",
            "citedby": citations,
            "profile_url": f"https://scholar.google.com/citations?user={scholar_id}",
            "updated": datetime.now().isoformat()
        }
        
        # 保存完整数据
        with open('results/gs_data.json', 'w') as f:
            json.dump(scholar_data, f, indent=2, ensure_ascii=False)
        print("数据文件保存完成")
        
        # 创建Shields.io端点
        endpoint_url = create_shieldio_endpoint(citations)
        print(f"Shields.io端点已创建: {endpoint_url}")
        
        # 更新About.md文件
        if update_about_md(citations):
            print("About.md成功更新")
        else:
            print("About.md更新失败，将继续使用旧值")
            
    except KeyError:
        print("错误：未找到GOOGLE_SCHOLAR_ID环境变量")
        return
    
    except Exception as e:
        print(f"主函数异常: {e}")
    
    print("=== 处理完成 ===")

if __name__ == "__main__":
    main()
