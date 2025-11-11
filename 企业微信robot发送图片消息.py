import requests
import base64
import hashlib
import os

def send_image_to_wechat_robot(webhook_url, image_path):
    """
    通过企业微信机器人发送图片
    
    参数:
    webhook_url: 企业微信机器人的Webhook地址
    image_path: 本地图片文件的路径
    """

    if not os.path.exists(image_path):
        print(f"错误: 图片文件不存在 - {image_path}")
        return False
    
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
    file_ext = os.path.splitext(image_path)[1].lower()
    if file_ext not in valid_extensions:
        print(f"错误: 不支持的图片格式 - {file_ext}，支持的格式: {valid_extensions}")
        return False
    
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        base64_str = base64.b64encode(image_data).decode('utf-8')
        md5_str = hashlib.md5(image_data).hexdigest()
        
        payload = {
            "msgtype": "image",
            "image": {
                "base64": base64_str,
                "md5": md5_str
            }
        }
        
        response = requests.post(webhook_url, json=payload)
        response_data = response.json()
        
        if response_data.get('errcode') == 0:
            print("图片发送成功！")
            return True
        else:
            print(f"图片发送失败: {response_data.get('errmsg')}")
            return False
            
    except Exception as e:
        print(f"发送过程中发生错误: {str(e)}")
        return False

