import os
import requests
from bs4 import BeautifulSoup
import re
import subprocess

BASE_URL = 'https://kakuyomu.jp'
HISTORY_FILE = 'カクヨムダウンロード経歴.txt'
LOCAL_HISTORY_PATH = f'/tmp/{HISTORY_FILE}'  # ローカル経歴ファイルのパス
REMOTE_HISTORY_PATH = f'drive:/{HISTORY_FILE}'  # Google Driveの経歴ファイルのパス

# URL一覧の読み込み（スクリプトと同じディレクトリにあるファイルを参照）
script_dir = os.path.dirname(__file__)
url_file_path = os.path.join(script_dir, 'カクヨム.txt')

def fetch_url(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    return requests.get(url, headers=headers)

def load_history():
    if not os.path.exists(LOCAL_HISTORY_PATH):
        subprocess.run(['rclone', 'copyto', REMOTE_HISTORY_PATH, LOCAL_HISTORY_PATH], check=False)

    history = {}
    if os.path.exists(LOCAL_HISTORY_PATH):
        with open(LOCAL_HISTORY_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.match(r'(https?://[^\s|]+)\s*\|\s*(\d+)', line.strip())
                if match:
                    url, last = match.groups()
                    history[url.rstrip('/')] = int(last)
    return history

def save_history(history):
    with open(LOCAL_HISTORY_PATH, 'w', encoding='utf-8') as f:
        for url, last in history.items():
            f.write(f'{url}  |  {last}\n')
    subprocess.run(['rclone', 'copyto', LOCAL_HISTORY_PATH, REMOTE_HISTORY_PATH], check=True)

# 履歴を読み込み
history = load_history()

# 小説URLのリストを読み込み
with open(url_file_path, 'r', encoding='utf-8') as f:
    urls = [line.strip().rstrip('/') for line in f if line.strip().startswith('http')]

for novel_url in urls:
    try:
        print(f'\n--- 処理開始: {novel_url} ---')
        url = novel_url
        sublist = []

        # ページ分割対応
        while True:
            res = fetch_url(url)
            soup = BeautifulSoup(res.text, 'html.parser')
            title_text = soup.find('title').get_text()
            sublist += soup.select('.p-eplist__sublist .p-eplist__subtitle')
            next_page = soup.select_one('.c-pager__item--next')
            if next_page and next_page.get('href'):
                url = f'{BASE_URL}{next_page.get("href")}'
            else:
                break

        # タイトルのクリーンアップ
        for char in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
            title_text = title_text.replace(char, '')
        title_text = title_text.strip()

        # ダウンロード開始位置
        download_from = history.get(novel_url, 0)
        os.makedirs(f'/tmp/kakuyomu_dl/{title_text}', exist_ok=True)

        sub_len = len(sublist)
        new_max = download_from

        for i, sub in enumerate(sublist):
            if i + 1 <= download_from:
                continue

            sub_title = sub.text.strip()
            link = sub.get('href')
            file_name = f'{i+1:03d}.txt'
            folder_num = (i // 999) + 1
            folder_name = f'{folder_num:03d}'
            folder_path = f'/tmp/kakuyomu_dl/{title_text}/{folder_name}'
            os.makedirs(folder_path, exist_ok=True)
            file_path = f'{folder_path}/{file_name}'

            # 本文の取得
            res = fetch_url(f'{BASE_URL}{link}')
            soup = BeautifulSoup(res.text, 'html.parser')
            sub_body = soup.select_one('.p-novel__body')
            sub_body_text = sub_body.get_text() if sub_body else '[本文が取得できませんでした]'

            with open(file_path, 'w', encoding='UTF-8') as f:
                f.write(f'{sub_title}\n\n{sub_body_text}')

            print(f'{file_name} downloaded in folder {folder_name} ({i+1}/{sub_len})')
            new_max = i + 1

        history[novel_url] = new_max

    except Exception as e:
        print(f'エラー発生: {novel_url} → {e}')
        continue

# 履歴を保存
save_history(history)

# Google Driveへアップロード
subprocess.run(['rclone', 'copy', '/tmp/kakuyomu_dl', 'drive:', '--transfers=4', '--checkers=8', '--fast-list'], check=True)
