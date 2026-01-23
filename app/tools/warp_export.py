from PySide6.QtCore import QThread, Signal
from qfluentwidgets import InfoBar, InfoBarPosition, StateToolTip
from urllib.parse import urlencode, urlparse, parse_qs
from datetime import datetime
from pathlib import Path
from enum import Enum
import markdown
import requests
import tempfile
import random
import time
import glob
import json
import re
import os
from module.localization import tr


def srgf_to_uigf_hkrpg(srgf: dict) -> dict:
    if "info" not in srgf or "list" not in srgf:
        raise ValueError("Invalid SRGF input")

    info = srgf["info"]
    raw_list = srgf["list"]

    uigf = {
        "info": {
            "export_timestamp": info.get("export_timestamp"),
            "export_app": info.get("export_app", "Unknown App"),
            "export_app_version": info.get("export_app_version", ""),
            "version": "v4.1"
        },
        "hkrpg": [
            {
                "uid": info.get("uid"),
                "timezone": int(info.get("region_time_zone", 0)),
                "lang": info.get("lang", "zh-cn"),
                "list": []
            }
        ]
    }

    for item in raw_list:
        record = {
            "gacha_id": item.get("gacha_id"),
            "gacha_type": item.get("gacha_type"),
            "item_id": item.get("item_id"),
            "count": item.get("count", "1"),
            "time": item.get("time"),
            "name": item.get("name"),
            "item_type": item.get("item_type"),
            "rank_type": item.get("rank_type"),
            "id": item.get("id")
        }
        uigf["hkrpg"][0]["list"].append(record)

    return uigf


def uigf_to_srgf_hkrpg(uigf: dict) -> dict:
    if "info" not in uigf or "hkrpg" not in uigf:
        raise ValueError("Invalid UIGF input")

    info = uigf["info"]
    first_entry = uigf["hkrpg"][0]  # UIGF 支持多个 UID，但 SRGF 只支持单 UID

    srgf = {
        "info": {
            "uid": first_entry.get("uid"),
            "lang": first_entry.get("lang", "zh-cn"),
            "region_time_zone": first_entry.get("timezone", 0),
            "export_timestamp": info.get("export_timestamp"),
            "export_app": info.get("export_app"),
            "export_app_version": info.get("export_app_version"),
            "srgf_version": "v1.0"
        },
        "list": []
    }

    for item in first_entry.get("list", []):
        record = {
            "gacha_id": item.get("gacha_id"),
            "gacha_type": item.get("gacha_type"),
            "item_id": item.get("item_id"),
            "count": item.get("count", "1"),
            "time": item.get("time"),
            "name": item.get("name"),
            "item_type": item.get("item_type"),
            "rank_type": item.get("rank_type"),
            "id": item.get("id")
        }
        srgf["list"].append(record)

    return srgf


def detect_format(data: dict) -> str:
    if not isinstance(data, dict):
        return "neither"

    # SRGF
    if "info" in data and "list" in data and isinstance(data.get("list"), list):
        return "srgf"

    # UIGF
    if "info" in data and any(k in data for k in ("hkrpg", "hk4e", "nap")):
        return "uigf"

    return "neither"


class WarpExport:
    def __init__(self, config=None, parent=None, infoSignal=None):
        self.parent = parent
        self.infoSignal = infoSignal
        self.gacha_type = {
            "11": tr("角色活动跃迁"),
            "12": tr("光锥活动跃迁"),
            "21": tr("角色联动跃迁"),
            "22": tr("光锥联动跃迁"),
            "1": tr("常驻跃迁"),
            "2": tr("新手跃迁"),
        }
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
        self.__init_data(config)

    def __init_data(self, config):
        if config:
            self.info = config.get("info")
            for item in config.get("list"):
                type = item["gacha_type"]
                self.gacha_data[type].append(item)

    def __set_color(self, content, color):
        return f"<font color='{color}'>{content}</font>"

    def __get_random_color(self, theme="light"):
        if not hasattr(self, 'previous_color'):
            self.previous_color = None
        if theme == "light":
            colors = ['DarkRed', 'DarkOrange', 'DarkKhaki', 'DarkGreen', 'DarkCyan', 'DarkBlue', 'DarkMagenta']
        else:
            colors = ['Red', 'Orange', 'Yellow', 'Lime', 'Turquoise', 'Cyan', 'Fuchsia']
        self.previous_color = random.choice([color for color in colors if color != self.previous_color])
        return self.previous_color

    def get_uid(self):
        return self.info.get("uid")

    def data_to_html(self, theme="light"):
        css = '''
        <style>
        p {
            font-size: 15px;
            font-weight: 500;
        }
        </style>
        '''
        content = ""

        def warp_analyze(value, content):
            start_time = datetime.strptime(value[0]["time"], "%Y-%m-%d %H:%M:%S").strftime('%Y/%m/%d')
            end_time = datetime.strptime(value[-1]["time"], "%Y-%m-%d %H:%M:%S").strftime('%Y/%m/%d')
            content += f"{start_time}  -  {end_time}\n\n"
            total = len(value)
            rank_type = {
                "5": 0,
                "4": 0,
                "3": 0
            }
            rank_5 = []
            grand_total = 0
            for item in value:
                grand_total += 1
                type = item["rank_type"]
                name = item["name"]
                rank_type[type] = rank_type.get(type, 0) + 1
                if type == "5":
                    rank_5.append([name, grand_total])
                    grand_total = 0

            content += f"一共 {self.__set_color(total, 'DeepSkyBlue')} {tr('抽')} {tr('已累计')} {self.__set_color(grand_total, 'LimeGreen')} {tr('抽未出5星')}\n\n"
            for star, count in rank_type.items():
                percentage = count / total * 100
                color = 'Goldenrod' if star == '5' else 'darkorchid' if star == '4' else 'DodgerBlue'
                text = f"{star}{tr('星')}: {count:<4d} [{percentage:.2f}%]"
                content += f"{self.__set_color(text, color)}\n\n"
            if len(rank_5) > 0:
                rank_5_str = ' '.join([f"{self.__set_color(f'{key}[{value}]', self.__get_random_color(theme))}" for key, value in rank_5])
                rank_5_sum = sum(value for _, value in rank_5)
                rank_5_avg = rank_5_sum / len(rank_5)
                content += f"{tr('5星历史记录')}: {rank_5_str}\n\n"
                content += f"{tr('五星平均出货次数为')}: {self.__set_color(f'{rank_5_avg:.2f}', 'green')}\n\n<hr>"
            else:
                content += "<hr>"

            return content

        for type, list in self.gacha_data.items():
            if len(list) > 0:
                content += f"## {self.__set_color(self.gacha_type[type], '#f18cb9')}\n\n"
                content = warp_analyze(list, content)
        return css + markdown.markdown(content)

    def detect_game_locale(self):
        list = []
        strs = ['/miHoYo/崩坏：星穹铁道/', '/Cognosphere/Star Rail/']
        for str in strs:
            log_file_path = os.path.join(os.getenv('userprofile'), f"AppData/LocalLow{str}Player.log")
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
        # 主线程 UI 操作通过信号发射
        if self.infoSignal:
            self.infoSignal.emit(content, title)
        elif self.parent:
            self.parent.stateTooltip.setContent(content)
            if title:
                self.parent.stateTooltip.setTitle(title)

    def get_gacha_log(self, api_domain, gacha_type, updated_query, page, size, end_id, max_retry=5):
        gacha_url_path = "getGachaLog"
        if gacha_type == "21" or gacha_type == "22":
            gacha_url_path = "getLdGachaLog"
        url = f'{api_domain}/common/gacha_record/api/{gacha_url_path}?{updated_query}&gacha_type={gacha_type}&page={page}&size={size}&end_id={end_id}'
        if not hasattr(self, 'warplink'):
            self.warplink = url
        for i in range(max_retry):
            try:
                response = requests.get(url)
                response.raise_for_status()
                retcode = response.json()['retcode']
                if retcode != 0:
                    if retcode == -101:
                        self.show_info_message(tr("请重新打开游戏抽卡记录"), tr("身份认证已过期"))
                        return None
                    else:
                        self.show_info_message(response.json()['message'], tr("请求出错"))
                        return None
                else:
                    self.show_info_message(tr('正在获取{self.gacha_type[gacha_type]}第{page}页').format(self=self, gacha_type=gacha_type, page=page))
                    return response.json()['data']
            except Exception:
                self.show_info_message(tr('等待5秒后重试，剩余重试次数：') + str(max_retry - i) + '', tr("请求出错"))
                time.sleep(5)
        return None

    def init_info(self, response):
        item = response['list'][0]
        region_time_zone = response['region_time_zone']

        if self.info['uid'] == "":
            self.info['uid'] = item['uid']
        elif self.info['uid'] != item['uid']:
            self.show_info_message(tr("UID与原始数据不一致"), tr("请求出错"))
            return False

        if self.info['lang'] == "":
            self.info['lang'] = item['lang']
        elif self.info['lang'] != item['lang']:
            self.show_info_message(tr("语言与原始数据不一致"), tr("请求出错"))
            return False

        if self.info['region_time_zone'] is None:
            self.info['region_time_zone'] = region_time_zone
        elif self.info['region_time_zone'] != region_time_zone:
            self.show_info_message(tr("时区与原始数据不一致"), tr("请求出错"))
            return False

        return True

    def get_gacha_logs(self, api_domain, gacha_type, updated_query, type="normal"):
        if type == "normal" and len(self.gacha_data[gacha_type]) > 0:
            last_id = self.gacha_data[gacha_type][-1]['id']
        else:
            last_id = "0"
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

            if not init:
                if not self.init_info(response):
                    return None
                init = True

            for item in list:
                item.pop('uid')
                item.pop('lang')
                if item['id'] > last_id:
                    gacha_list.append(item)
                else:
                    return gacha_list[::-1]

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
                    from bisect import bisect_left
                    # 获取所有 ID 列表
                    ids = [entry["id"] for entry in self.gacha_data[gtype]]
                    # 找到第一个 >= last_id 的位置
                    index = bisect_left(ids, last_id)
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


class WarpStatus(Enum):
    SUCCESS = 1
    FAILURE = 0
    UPDATE = 2
    COPY = 3


class WarpThread(QThread):
    warpSignal = Signal(WarpStatus)
    infoSignal = Signal(str, object)  # 新增信号

    def __init__(self, parent, type="normal"):
        super().__init__()
        self.parent = parent
        self.type = type

    def run(self):
        try:
            with open("./warp.json", 'r', encoding='utf-8') as file:
                config = json.load(file)
                warp = WarpExport(config, self.parent, self.infoSignal)
        except Exception:
            warp = WarpExport(None, self.parent, self.infoSignal)

        # self.parent.stateTooltip.setContent("测试测试(＾∀＾●)")
        try:
            url = warp.get_url()
            if not url:
                # self.parent.stateTooltip.setTitle("未找到URL")
                # self.parent.stateTooltip.setContent("请确认是否已打开游戏抽卡记录")
                self.infoSignal.emit(tr("请确认是否已打开游戏抽卡记录"), tr("未找到URL"))
                self.warpSignal.emit(WarpStatus.FAILURE)
                return

            api_domain, updated_query = warp.remove_query_params(url)

            if warp.fetch_data(api_domain, updated_query, self.type):
                self.parent.warplink = warp.warplink
                config = warp.export_data()

                with open("./warp.json", 'w', encoding='utf-8') as file:
                    json.dump(config, file, ensure_ascii=False, indent=4)

                # content = warp.data_to_html()
                # self.parent.contentLabel.setText(markdown.markdown(content))

                # self.parent.setContent()
                self.warpSignal.emit(WarpStatus.UPDATE)

                # self.parent.copyLinkBtn.setEnabled(True)
                self.warpSignal.emit(WarpStatus.COPY)
                self.warpSignal.emit(WarpStatus.SUCCESS)
            else:
                self.warpSignal.emit(WarpStatus.FAILURE)
        except Exception:
            # self.parent.stateTooltip.setContent("跃迁数据获取失败(´▔∀▔`)")
            self.infoSignal.emit(tr("跃迁数据获取失败(´▔∀▔`)"))
            self.warpSignal.emit(WarpStatus.FAILURE)


def warpExport(self, type="normal"):
    self.stateTooltip = StateToolTip(tr("抽卡记录"), tr("正在获取跃迁数据..."), self.window())
    self.stateTooltip.closeButton.setVisible(False)
    self.stateTooltip.move(self.stateTooltip.getSuitablePos())
    self.stateTooltip.show()
    self.updateBtn.setEnabled(False)
    self.updateFullBtn.setEnabled(False)

    def handle_warp(status):
        if status == WarpStatus.SUCCESS:
            self.stateTooltip.setContent(tr("跃迁数据获取完成(＾∀＾●)"))
            self.stateTooltip.setState(True)
            self.stateTooltip = None
            self.updateBtn.setEnabled(True)
            self.updateFullBtn.setEnabled(True)
        elif status == WarpStatus.FAILURE:
            # self.stateTooltip.setContent("跃迁数据获取失败(´▔∀▔`)")
            self.stateTooltip.setState(True)
            self.stateTooltip = None
            self.updateBtn.setEnabled(True)
            self.updateFullBtn.setEnabled(True)
        elif status == WarpStatus.UPDATE:
            self.setContent()
        elif status == WarpStatus.COPY:
            self.copyLinkBtn.setEnabled(True)

    # 连接 infoSignal 到主线程 UI
    def handle_info(content, title=None):
        self.stateTooltip.setContent(content)
        if title:
            self.stateTooltip.setTitle(title)

    self.warp_thread = WarpThread(self, type)
    self.warp_thread.warpSignal.connect(handle_warp)
    self.warp_thread.infoSignal.connect(handle_info)
    self.warp_thread.start()
