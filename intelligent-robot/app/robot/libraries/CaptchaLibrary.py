# -*- coding: utf-8 -*-
import json
import os
import time

# OSS SDK
import oss2
from oss2.exceptions import OssError

# 阿里云 SDK 核心
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_openapi.client import Client as OpenApiClient
from alibabacloud_tea_util import models as util_models

# OCR SDK (用于 RecognizeAdvanced)
from alibabacloud_ocr_api20210707 import models as ocr_api_20210707_models
from alibabacloud_ocr_api20210707.client import Client as ocr_api20210707Client

# .env 文件加载器
from dotenv import load_dotenv


class CaptchaLibrary:
    """
    一个用于阿里云OSS上传和OCR验证码识别的Robot Framework库。

    在使用前，请确保在项目根目录下有一个 `.env` 文件，并包含以下配置：
    OSS_TEST_ACCESS_KEY_ID=<Your_Access_Key_ID>
    OSS_TEST_ACCESS_KEY_SECRET=<Your_Access_Key_Secret>
    OSS_TEST_BUCKET=<Your_Bucket_Name>
    OSS_TEST_ENDPOINT=<Your_OSS_Endpoint>

    此外，您可以通过设置 `OCR_API_TYPE` 环境变量来选择使用的OCR API：
    - OCR_API_TYPE=ADVANCED (默认): 使用 RecognizeAdvanced API，适用于常规验证码。
    - OCR_API_TYPE=GENERAL: 使用 RecognizeGeneral API，适用于通用文字识别。
    """
    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'

    def __init__(self):
        """
        初始化客户端和配置。
        在导入库时，会自动加载.env文件并初始化OSS和OCR客户端所需配置。
        """
        print("正在初始化 CaptchaLibrary...")
        load_dotenv()
        self.access_key_id = os.getenv('OSS_TEST_ACCESS_KEY_ID')
        self.access_key_secret = os.getenv('OSS_TEST_ACCESS_KEY_SECRET')
        self.bucket_name = os.getenv('OSS_TEST_BUCKET')
        self.oss_endpoint = os.getenv('OSS_TEST_ENDPOINT')
        self.ocr_endpoint = f'ocr-api.cn-hangzhou.aliyuncs.com'

        # 通过环境变量选择OCR API类型，默认为 'ADVANCED'
        self.ocr_api_type = os.getenv('OCR_API_TYPE', 'ADVANCED').upper()
        print(f"正在使用 OCR API 类型: {self.ocr_api_type}")

        # 确认参数都填写正确
        for param_name, param_value in {
            "Access Key ID": self.access_key_id,
            "Access Key Secret": self.access_key_secret,
            "Bucket Name": self.bucket_name,
            "OSS Endpoint": self.oss_endpoint
        }.items():
            if not param_value or '<' in param_value:
                raise ValueError(f"配置错误: '{param_name}' 没有在您的 .env 文件中正确设置。")

        # 初始化OSS Bucket对象，供所有方法复用
        try:
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self.bucket = oss2.Bucket(auth, self.oss_endpoint, self.bucket_name)
            print("OSS Bucket 初始化成功。")
        except Exception as e:
            raise RuntimeError(f"初始化OSS Bucket失败: {e}")

    def upload_file_to_oss_and_return_url(self, local_file_path: str, oss_object_name: str = None) -> str or None:
        """
        上传本地文件到阿里云OSS，并返回其公开访问URL。
        """
        if not os.path.exists(local_file_path):
            print(f"错误: 本地文件不存在 -> {local_file_path}")
            return None

        if not oss_object_name:
            oss_object_name = f"RPA/captcha_{int(time.time())}_{os.path.basename(local_file_path)}"

        try:
            print(f"正在上传文件: {local_file_path} -> OSS 对象: {oss_object_name}")
            result = self.bucket.put_object_from_file(oss_object_name, local_file_path)

            if result.status == 200:
                print("文件上传成功！")
                clean_endpoint = self.oss_endpoint.replace('https://', '').replace('http://', '')
                file_url = f"https://{self.bucket_name}.{clean_endpoint}/{oss_object_name}"
                print(f"文件 URL: {file_url}")
                return file_url
            else:
                print(f"文件上传失败，HTTP 状态码: {result.status}")
                return None
        except (OssError, Exception) as e:
            print(f"上传过程中发生错误: {e}")
            return None

    def get_captcha_from_url(self, image_url: str) -> str or int:
        """
        根据给定的图片URL识别验证码。

        优化：只有在发生API错误或网络异常（识别失败）时才进行重试。
        如果识别成功但结果为空字符串，则直接返回空字符串，不进行重试。
        """
        max_attempts = 3
        for attempt in range(max_attempts):
            print(f"\n--- 第 {attempt + 1}/{max_attempts} 次尝试从 URL 识别验证码 ---")

            if self.ocr_api_type == 'GENERAL':
                captcha_code = self._recognize_with_general(image_url)
            else:
                captcha_code = self._recognize_with_advanced(image_url)

            # --- 核心优化点 ---
            # 使用 'is not None' 来精确判断是否识别成功。
            # 这样空字符串 "" 会被当作成功结果直接返回。
            if captcha_code is not None:
                print(f"识别成功，最终结果为: '{captcha_code}'")
                return captcha_code

            # 只有在 captcha_code 为 None (识别失败) 时，才会执行到这里
            if attempt < max_attempts - 1:
                print("识别失败（API或网络错误），1秒后重试...")
                time.sleep(1)

        print(f"\n尝试 {max_attempts} 次后仍未能成功识别（持续发生错误）。")
        return -1

    def get_captcha_from_local_file(self, local_file_path: str, oss_object_name: str = None) -> str or int:
        """
        一站式方法：上传本地图片并识别其中的验证码。
        """
        print(f"\n--- 开始组合工作流：上传并识别 {local_file_path} ---")
        uploaded_url = self.upload_file_to_oss_and_return_url(local_file_path, oss_object_name)

        if uploaded_url:
            return self.get_captcha_from_url(uploaded_url)
        else:
            print("上传步骤失败，无法进行 OCR 识别。")
            return -1

    def _recognize_with_advanced(self, file_url: str) -> str or None:
        """
        [内部方法] 调用阿里云OCR 'RecognizeAdvanced' 服务并解析结果。
        """
        print("正在使用 OCR 引擎: RecognizeAdvanced")
        try:
            config = open_api_models.Config(
                access_key_id=self.access_key_id,
                access_key_secret=self.access_key_secret,
                endpoint=self.ocr_endpoint
            )
            ocr_client = ocr_api20210707Client(config)
            recognize_request = ocr_api_20210707_models.RecognizeAdvancedRequest(url=file_url)
            runtime = util_models.RuntimeOptions()

            response = ocr_client.recognize_advanced_with_options(recognize_request, runtime)

            response_dict = response.body.to_map()
            data_str = response_dict.get('Data')
            if not data_str:
                print("OCR 错误: 响应中 'Data' 字段为空。")
                return None

            inner_data = json.loads(data_str)
            captcha_code = inner_data.get('content', '').strip()

            if captcha_code is not None:  # 确保返回的是字符串
                print(f"成功提取验证码: '{captcha_code}'")
                return captcha_code
            else:  # 理论上不会发生，因为 get().strip() 总是返回字符串
                print("OCR 警告: data 中 'content' 字段为空或解析失败。")
                return ""  # 返回空字符串表示识别内容为空
        except Exception as error:
            print(f"OCR 识别过程中发生错误 (Advanced): {repr(error)}")
            return None

    def _recognize_with_general(self, file_url: str) -> str or None:
        """
        [内部方法] 调用阿里云OCR 'RecognizeGeneral' 服务并解析结果。
        """
        print("正在使用 OCR 引擎: RecognizeGeneral")
        try:
            config = open_api_models.Config(
                access_key_id=self.access_key_id,
                access_key_secret=self.access_key_secret,
                endpoint=self.ocr_endpoint
            )
            client = OpenApiClient(config)

            params = open_api_models.Params(
                action='RecognizeGeneral',
                version='2021-07-07',
                protocol='HTTPS',
                method='POST',
                auth_type='AK',
                style='V3',
                pathname=f'/',
                req_body_type='json',
                body_type='json'
            )

            request = open_api_models.OpenApiRequest(
                query={'Url': file_url}
            )

            runtime = util_models.RuntimeOptions()

            response = client.call_api(params, request, runtime)

            body = response.get('body', {})
            data_str = body.get('Data')
            if not data_str:
                print("OCR 错误: 响应中 'Data' 字段为空。")
                return None

            inner_data = json.loads(data_str)
            content_str = inner_data.get('content')
            if content_str is not None:
                captcha_code = ''.join(content_str.split())
                print(f"成功提取验证码: '{captcha_code}'")
                return captcha_code
            else:
                print("OCR 警告: data 中 'content' 字段为空。")
                return ""
        except Exception as e:
            print(f"OCR 识别过程中发生错误 (General): {repr(e)}")
            return None