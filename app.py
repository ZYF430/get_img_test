from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import json
import io
import re
from urllib.parse import urljoin
import time
import logging

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# 正确配置CORS
CORS(app, resources={r"/*": {"origins": "*"}})


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({'status': 'healthy', 'message': '后端服务正常运行'})


@app.route('/api/get-images', methods=['POST', 'OPTIONS'])
def get_images():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        logger.info("收到获取图片请求")

        data = request.get_json()
        if not data:
            logger.error("没有收到JSON数据")
            return jsonify({'error': 'No JSON data provided'}), 400

        url = data.get('url')
        if not url:
            logger.error("缺少URL参数")
            return jsonify({'error': '缺少URL参数'}), 400

        logger.info(f"请求的URL: {url}")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'http://www.cnu.cc/'
        }

        # 测试CNU网站连接
        logger.info("开始请求CNU网站...")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        logger.info("CNU网站请求成功")

        soup = BeautifulSoup(response.text, 'html.parser')

        # 查找JSON数据
        imgs_json_div = soup.find('div', id='imgs_json')
        if imgs_json_div and imgs_json_div.text:
            logger.info("找到JSON数据")
            images = json.loads(imgs_json_div.text)
            image_urls = []

            for img_info in images:
                img_url = f"http://imgoss.cnu.cc/{img_info['img']}?x-oss-process=style/content"
                image_urls.append({
                    'url': img_url,
                    'width': img_info.get('width', 0),
                    'height': img_info.get('height', 0),
                    'index': len(image_urls)
                })

            logger.info(f"成功解析 {len(image_urls)} 张图片")
            return jsonify({'success': True, 'images': image_urls})
        else:
            logger.warning("未找到JSON数据，尝试从HTML提取")
            # 备用方案：从HTML中提取
            thumbnail_divs = soup.find_all('div', class_='thumbnail')
            image_urls = []

            for i, div in enumerate(thumbnail_divs):
                img = div.find('img')
                if img:
                    img_url = img.get('data-original') or img.get('src')
                    if img_url and '1_1.gif' not in img_url:
                        img_url = urljoin(url, img_url)
                        image_urls.append({
                            'url': img_url,
                            'width': img.get('width', 0),
                            'height': img.get('height', 0),
                            'index': i
                        })

            if image_urls:
                logger.info(f"从HTML找到 {len(image_urls)} 张图片")
                return jsonify({'success': True, 'images': image_urls})
            else:
                logger.error("完全未找到图片数据")
                return jsonify({'error': '未找到图片数据'}), 404

    except requests.exceptions.RequestException as e:
        logger.error(f"网络请求错误: {e}")
        return jsonify({'error': f'网络请求失败: {str(e)}'}), 500
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析错误: {e}")
        return jsonify({'error': '数据解析失败'}), 500
    except Exception as e:
        logger.error(f"未知错误: {e}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@app.route('/api/download-image', methods=['GET', 'OPTIONS'])
def download_image():
    if request.method == 'OPTIONS':
        return '', 200

    try:
        image_url = request.args.get('url')
        if not image_url:
            return jsonify({'error': '缺少图片URL'}), 400

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'http://www.cnu.cc/'
        }

        response = requests.get(image_url, headers=headers, timeout=30)
        response.raise_for_status()

        return send_file(
            io.BytesIO(response.content),
            mimetype='image/jpeg',
            as_attachment=True,
            download_name=f'cnu_image_{int(time.time())}.jpg'
        )

    except Exception as e:
        logger.error(f"下载图片错误: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    logger.info("启动Flask应用...")
    app.run(host='0.0.0.0', port=5000, debug=True)