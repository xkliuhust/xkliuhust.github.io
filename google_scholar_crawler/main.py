import os
import json
import time
import random
import re
import logging
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image, ImageEnhance
import pytesseract

# 配置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scholar_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('GoogleScholarScraper')

# 结果目录
RESULTS_DIR = Path('results')
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

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
    
    logger.info("启动Chrome浏览器")
    return webdriver.Chrome(options=chrome_options)

def save_artifact(content, filename):
    """保存调试工件"""
    path = RESULTS_DIR / filename
    with open(path, 'w', encoding='utf-8') as f:
        if isinstance(content, str):
            f.write(content)
        else:
            json.dump(content, f, indent=2)
    logger.info(f"保存工件: {path}")

def capture_debug_screenshots(driver, prefix):
    """捕获调试截图"""
    try:
        # 完整页面截图
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        full_screenshot = RESULTS_DIR / f"{prefix}_full_page_{timestamp}.png"
        driver.save_screenshot(str(full_screenshot))
        logger.info(f"保存完整页面截图: {full_screenshot}")
        
        # 捕获引文元素截图
        try:
            citations_element = driver.find_element(By.ID, "gsc_rsb_cit")
            loc = citations_element.location
            size = citations_element.size
            
            # 创建元素截图
            left = loc['x']
            top = loc['y']
            right = left + size['width']
            bottom = top + size['height']
            
            full_img = Image.open(full_screenshot)
            element_img = full_img.crop((left, top, right, bottom))
            element_path = RESULTS_DIR / f"{prefix}_citation_element_{timestamp}.png"
            element_img.save(str(element_path))
            logger.info(f"保存引文区域截图: {element_path}")
            
            # 尝试OCR处理
            return ocr_extract_text_from_image(str(element_path))
            
        except Exception as e:
            logger.warning(f"无法捕获引文元素截图: {str(e)}")
            return 0
            
    except Exception as e:
        logger.error(f"截图失败: {str(e)}")
        return 0

def enhance_image(image_path):
    """增强图像以提高OCR识别率"""
    try:
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
        
        enhanced_path = RESULTS_DIR / f"enhanced_{Path(image_path).name}"
        img.save(str(enhanced_path))
        logger.info(f"保存增强版图像: {enhanced_path}")
        return str(enhanced_path)
    except Exception as e:
        logger.error(f"图像增强失败: {str(e)}")
        return image_path

def ocr_extract_text_from_image(image_path):
    """从图片中提取数字"""
    try:
        logger.info(f"尝试OCR识别: {image_path}")
        enhanced_path = enhance_image(image_path)
        img = Image.open(enhanced_path)
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789'
        text = pytesseract.image_to_string(img, config=custom_config).strip()
        
        # 提取所有数字
        digits = ''.join(filter(str.isdigit, text))
        if digits:
            logger.info(f"OCR识别结果: {digits}")
            return int(digits)
        return 0
    except Exception as e:
        logger.error(f"OCR处理失败: {str(e)}")
        return 0

def get_citations(driver, scholar_id):
    """获取引文数量"""
    url = f"https://scholar.google.com/citations?hl=en&user={scholar_id}"
    logger.info(f"访问Google Scholar个人主页: {url}")
    
    try:
        driver.get(url)
        
        # 保存HTML源码用于调试
        save_artifact(driver.page_source, "gs_page.html")
        logger.info("页面HTML已保存")
        
        # 等待页面加载
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "gsc_rsb_cit"))
        )
        logger.info("页面元素加载完成")
        
        # 保存加载后的HTML
        save_artifact(driver.page_source, "gs_page_after_wait.html")
        
        # 尝试提取引文数量
        citations_element = driver.find_element(By.ID, "gsc_rsb_cit")
        text = citations_element.text
        
        # 保存元素文本用于调试
        element_text = f"Element Text: {text}"
        save_artifact(element_text, "citation_element_text.txt")
        
        # 尝试解析数字
        if "Cited by" in text:
            cit_text = text.replace("Cited by", "").replace(',', '').strip()
            if cit_text.isdigit():
                citations = int(cit_text)
                logger.info(f"成功解析引文数: {citations}")
                return citations
        
        # 尝试其他选择器
        for selector in ["#gsc_rsb_cit", ".gsc_rsb_std"]:
            try:
                alt_element = driver.find_element(By.CSS_SELECTOR, selector)
                alt_text = alt_element.text
                numbers = ''.join(filter(str.isdigit, alt_text))
                if numbers:
                    citations = int(numbers)
                    logger.info(f"备选解析成功: {citations} (by {selector})")
                    return citations
            except:
                pass
        
        # 使用视觉识别作为最后手段
        logger.warning("文本解析失败，尝试视觉识别...")
        return capture_debug_screenshots(driver, "debug")
        
    except Exception as e:
        logger.error(f"获取引文数时出错: {str(e)}")
        return capture_debug_screenshots(driver, "error")

def update_about_md(citation_count):
    """更新About.md文件"""
    try:
        about_path = 'About.md'
        logger.info(f"更新 {about_path} 文件")
        
        with open(about_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找并替换占位符
        new_content = re.sub(
            r"<span id='total_cit'>\[loading\]</span>",
            f"<span id='total_cit'>{citation_count}</span>",
            content
        )
        
        # 如果没找到带方括号的占位符，尝试更智能的替换
        if new_content == content:
            logger.warning("未找到 [loading] 占位符，尝试其他替换方式")
            new_content = re.sub(
                r'<span id=\'total_cit\'>.*?</span>',
                f'<span id=\'total_cit\'>{citation_count}</span>',
                content
            )
        
        # 保存更新
        with open(about_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        logger.info(f"{about_path} 更新成功")
        return True
        
    except Exception as e:
        logger.error(f"更新About.md失败: {str(e)}")
        return False

def main():
    try:
        scholar_id = os.environ['GOOGLE_SCHOLAR_ID']
        logger.info(f"===== 开始处理Google Scholar数据 =====")
        logger.info(f"学术ID: {scholar_id}")
        logger.info(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        driver = setup_browser()
        
        try:
            # 获取引文数
            citations = get_citations(driver, scholar_id)
            
            # 保存结果数据
            result_data = {
                "scholar_id": scholar_id,
                "citation_count": citations,
                "retrieved_at": datetime.now().isoformat(),
                "source": "google_scholar"
            }
            save_artifact(result_data, "scholar_results.json")
            logger.info(f"最终引文数: {citations}")
            
            # 更新About.md
            update_about_md(citations)
            
            # 创建徽章数据
            shield_data = {
                "schemaVersion": 1,
                "label": "citations",
                "message": str(citations),
                "color": "blue",
                "namedLogo": "google-scholar",
                "logoColor": "#4285F4",
                "style": "flat"
            }
            save_artifact(shield_data, "gs_data_shieldsio.json")
            logger.info("徽章数据已保存")
            
        finally:
            driver.quit()
            logger.info("浏览器已关闭")
            
        logger.info("===== 处理完成 =====")
        logger.info(f"下次更新应在24小时内自动运行")
        
    except Exception as e:
        logger.exception(f"严重错误: {str(e)}")
        # 保存错误状态
        error_data = {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        save_artifact(error_data, "last_error.json")

if __name__ == "__main__":
    main()
