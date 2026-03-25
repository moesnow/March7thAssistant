import argparse
import sys
from module.config import cfg
from module.logger import log

parser = argparse.ArgumentParser(description='March7thAssistant')
parser.add_argument('--force-resolution', action='store_true', help='force 1920*1080 resolution')
args = parser.parse_args()

if args.force_resolution:
    cfg.force_resolution = True
else:
    cfg.force_resolution = False

# Rest of your code remains the same
from module.automation.automation import Automation
auto = Automation(cfg.get_value('game_title_name'), log)
