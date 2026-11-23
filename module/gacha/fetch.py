"""Game cache discovery and pagination, independent of Qt."""
from bisect import bisect_left
import glob
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from module.gacha.pools import POOLS
from module.localization import tr


class WarpClient:
    def __init__(self, config=None, *, progress=None, load_uid=None):
        self.progress = progress
        self.load_uid = load_uid
        self.error = None
        # Keep the original request sequence: event warps before standard and departure.
        ordered = sorted(POOLS.values(), key=lambda pool: pool.fetch_last)
        self.gacha_type = {pool.id: pool.label for pool in ordered}
        self.info = {
            "uid": "",
            "lang": "",
            "region_time_zone": None,
            "export_timestamp": 0,
            "export_app": "",
            "export_app_version": "",
            "srgf_version": ""
        }
        self.gacha_data = {}
        for type in self.gacha_type:
            self.gacha_data[type] = []
        self._load_config(config)

    def _load_config(self, config):
        if config:
            self.info = config.get("info")
            for item in config.get("list"):
                type = item["gacha_type"]
                self.gacha_data[type].append(item)

    def detect_game_locale(self):
        list = []
        strs = ['/miHoYo/崩坏：星穹铁道/', '/Cognosphere/Star Rail/']
        for str in strs:
            log_file_path = os.path.join(os.path.expanduser('~'), f"AppData/LocalLow{str}Player.log")
            if not os.path.exists(log_file_path):
                continue

            try:
                with open(log_file_path, 'r', encoding='utf-8') as file:
                    log_content = file.read()
                regex_pattern = r'\w:\/.*?\/StarRail_Data\/'
                matches = re.findall(regex_pattern, log_content)

                for match in matches:
                    if match not in list:
                        list.append(match)
            except Exception:
                pass

        if len(list) > 0:
            return list
        else:
            return None

    def get_url_from_cache_text(self, game_path):
        try:
            results = glob.glob(os.path.join(game_path, 'webCaches/*/Cache/Cache_Data/data_2'), recursive=True)
            results_with_mtime = [(file, os.stat(file).st_mtime) for file in results]
            sorted_results = sorted(results_with_mtime, key=lambda x: x[1], reverse=True)

            if sorted_results:
                latest_file_path = sorted_results[0][0]

                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_file_path = os.path.join(Path(temp_dir), Path(latest_file_path).name)
                    from win32api import CopyFile  # 延迟导入，避免非 Windows 平台报错
                    CopyFile(latest_file_path, temp_file_path)
                    cache_text = Path(temp_file_path).read_bytes().decode(errors="ignore")

                regex_pattern = r'https.+?&auth_appid=webview_gacha&.+?authkey=.+?&game_biz=hkrpg_'
                matches = re.findall(regex_pattern, cache_text)
                return matches[-1]
            else:
                return None
        except Exception:
            return None

    def get_url(self):
        game_locale = self.detect_game_locale()
        if game_locale:
            url_list = [url for locale in game_locale if (url := self.get_url_from_cache_text(locale)) is not None]
            if url_list:
                return url_list[0]
        return None

    def remove_query_params(self, url):
        params_to_remove = ['page', 'size', 'gacha_type', 'end_id']
        # 解析URL
        parsed_url = urlparse(url)

        # 将查询参数解析为字典
        query_params = parse_qs(parsed_url.query)

        host = parsed_url.netloc
        if 'webstatic-sea' in host or 'hkrpg-api-os' in host or 'api-os-takumi' in host or 'hoyoverse.com' in host:
            apiDomain = 'https://public-operation-hkrpg-sg.hoyoverse.com'
        else:
            apiDomain = 'https://public-operation-hkrpg.mihoyo.com'

        # 删除指定的参数
        for param in params_to_remove:
            query_params.pop(param, None)

        # 重新构建查询字符串
        updated_query = urlencode(query_params, doseq=True)

        return apiDomain, updated_query

    def show_info_message(self, content, title=None):
        if self.progress:
            self.progress(content, title)

    def fail(self, content, title=None):
        self.error = f"{title} · {content}" if title else content
        self.show_info_message(content, title)

    def get_gacha_log(self, api_domain, gacha_type, updated_query, page, size, end_id, max_retry=5):
        gacha_url_path = POOLS[gacha_type].log_endpoint
        url = f'{api_domain}/common/hkrpg_gacha_record/api/{gacha_url_path}?{updated_query}&gacha_type={gacha_type}&page={page}&size={size}&end_id={end_id}'
        if not hasattr(self, 'warplink'):
            self.warplink = url
        for i in range(max_retry):
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                retcode = response.json()['retcode']
                if retcode != 0:
                    if retcode == -101:
                        self.fail(tr("请重新打开游戏抽卡记录"), tr("身份认证已过期"))
                        return None
                    else:
                        self.fail(response.json()['message'], tr("请求出错"))
                        return None
                else:
                    self.show_info_message(tr('正在获取{gacha_name}第{page}页').format(gacha_name=self.gacha_type[gacha_type], page=page))
                    return response.json()['data']
            except Exception:
                self.show_info_message(tr('等待5秒后重试，剩余重试次数：') + str(max_retry - i) + '', tr("请求出错"))
                time.sleep(5)
        self.fail(tr("跃迁数据获取失败(´▔∀▔`)"), tr("请求出错"))
        return None

    def init_info(self, response):
        item = response['list'][0]
        region_time_zone = response['region_time_zone']
        uid = str(item['uid'])
        if self.load_uid is not None:
            self._load_config(self.load_uid(uid))
            self.load_uid = None

        if self.info['uid'] == "":
            self.info['uid'] = uid
        elif self.info['uid'] != uid:
            self.fail(tr("UID与原始数据不一致"), tr("请求出错"))
            return False

        if self.info['lang'] == "":
            self.info['lang'] = item['lang']
        elif self.info['lang'] != item['lang']:
            self.fail(tr("语言与原始数据不一致"), tr("请求出错"))
            return False

        if self.info['region_time_zone'] is None:
            self.info['region_time_zone'] = region_time_zone
        elif self.info['region_time_zone'] != region_time_zone:
            self.fail(tr("时区与原始数据不一致"), tr("请求出错"))
            return False

        return True

    def get_gacha_logs(self, api_domain, gacha_type, updated_query, type="normal"):
        last_id = 0
        gacha_list = []
        page = 1
        size = 20
        end_id = 0
        init = False
        while True:
            if page % 10 == 0:
                time.sleep(1)

            response = self.get_gacha_log(api_domain, gacha_type, updated_query, page, size, end_id)
            time.sleep(0.3)
            if response is None:
                return None

            list = response['list']
            if len(list) == 0:
                return gacha_list[::-1]

            if not self.init_info(response):
                return None
            if not init:
                if type == "normal" and self.gacha_data[gacha_type]:
                    last_id = int(self.gacha_data[gacha_type][-1]["id"])
                init = True
            if page > 1 and int(list[-1]["id"]) >= int(end_id):
                self.fail(tr("记录分页没有前进，请重新打开游戏抽卡记录后重试。"))
                return None

            for item in list:
                if (str(item.get("uid")) != self.info["uid"] or item.get("lang") != self.info["lang"]
                        or str(item.get("gacha_type")) != gacha_type):
                    self.fail(tr("本页记录的账号、语言或卡池不一致，已停止更新。"))
                    return None
                if int(item["id"]) <= last_id:
                    return gacha_list[::-1]
                gacha_list.append({k: v for k, v in item.items() if k not in ("uid", "lang")})

            page += 1
            end_id = list[-1]['id']

    def fetch_data(self, api_domain, updated_query, type="normal"):
        for gtype in self.gacha_type:
            gacha_list = self.get_gacha_logs(api_domain, gtype, updated_query, type)
            if gacha_list is None:
                return False
            else:
                if gacha_list == []:
                    continue
                elif type == "normal":
                    self.gacha_data[gtype] += gacha_list
                else:
                    last_id = gacha_list[0]['id']

                    # 裁剪错误数据，使用二分查找
                    # 获取所有 ID 列表
                    ids = [int(entry["id"]) for entry in self.gacha_data[gtype]]
                    # 找到第一个 >= last_id 的位置
                    index = bisect_left(ids, int(last_id))
                    # 保留 ID 小于 last_id 的部分
                    self.gacha_data[gtype] = self.gacha_data[gtype][:index]

                    self.gacha_data[gtype] += gacha_list

        self.info['export_timestamp'] = int(time.time())
        self.info['export_app'] = "March7thAssistant"
        try:
            with open("./assets/config/version.txt", 'r', encoding='utf-8') as file:
                version = file.read()
        except Exception:
            version = ""
        self.info['export_app_version'] = version
        self.info['srgf_version'] = "v1.0"
        return True

    def export_data(self):
        gacha_data = []
        for data in self.gacha_data.values():
            gacha_data += data

        sorted_list = sorted(gacha_data, key=lambda x: int(x["id"]))

        config = {
            "info": self.info,
            "list": sorted_list
        }
        return config
