import os
import re
import time
import requests
import subprocess
from bs4 import BeautifulSoup
import urllib.request
import codecs

BASE_URL = "https://kakuyomu.jp"
HISTORY_FILE = "カクヨムダウンロード経歴.txt"
LOCAL_HISTORY_PATH = f"/tmp/{HISTORY_FILE}"
REMOTE_HISTORY_PATH = f"drive:{HISTORY_FILE}"
DOWNLOAD_DIR_BASE = "/tmp/kakuyomu_dl"
page_list = []  # 各話のURL
url = ''  # 小説URL
startn = 0  # DL開始番号
novel_name = ''  # 小説名（自動取得）


# 初期ディレクトリ作成
os.makedirs(DOWNLOAD_DIR_BASE, exist_ok=True)

def load_history():
    """履歴ファイルを読み込んで辞書形式で返す"""
    if not os.path.exists(LOCAL_HISTORY_PATH):
        subprocess.run(['rclone', 'copyto', REMOTE_HISTORY_PATH, LOCAL_HISTORY_PATH], check=False)

    history = {}
    if os.path.exists(LOCAL_HISTORY_PATH):
        with open(LOCAL_HISTORY_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.match(r'(https?://[^\s|]+)\s*\|\s*(\d+)', line.strip())
                if match:
                    url, last = match.groups()
                    history[url] = int(last)
    return history


def save_history(history):
    """履歴をローカルとGoogle Driveに保存"""
    with open(LOCAL_HISTORY_PATH, 'w', encoding='utf-8') as f:
        for url, last in history.items():
            f.write(f'{url}  |  {last}\n')
    subprocess.run(['rclone', 'copyto', LOCAL_HISTORY_PATH, REMOTE_HISTORY_PATH], check=True)


def loadfromhtml(url: str) -> str:
    """HTMLファイルのダウンロード"""
    with urllib.request.urlopen(url) as res:
        html_content = res.read().decode()
    return html_content


def elimbodytags(base: str) -> str:
    """余分なタグを除去"""
    return re.sub('<.*?>', '', base).replace(' ', '')


def changebrks(base: str) -> str:
    """改行タグを変換"""
    return re.sub('<br />', '\r\n', base)


def tagfilter(line: str) -> str:
    """タグ変換とフィルター実行"""
    tmp = changebrks(line)
    tmp = elimbodytags(tmp)
    return tmp


def get_novel_title(body: str) -> str:
    """小説タイトルの取得"""
    title_match = re.search(r'<title>(.*?) - カクヨム</title>', body)
    if title_match:
        title = title_match.group(1).strip()
        # フォルダ名として使えない文字を削除
        title = re.sub(r'[\\/:*?"<>|]', '', title)
        return title
    return "無題"


def get_episode_links(novel_url):
    """目次ページの解析と各話のURL取得"""
    response = requests.get(novel_url)
    response.raise_for_status()
    body = response.text
    ep_pattern = r'"__typename":"Episode","id":".*?","title":".*?",'
    ep_matches = re.findall(ep_pattern, body)

    if not ep_matches:
        print("指定されたページからエピソード情報を取得できませんでした。")
        return []

    episode_links = []
    for ep in ep_matches:
        purl_id_match = re.search(r'"id":"(.*?)"', ep)
        if purl_id_match:
            purl_id = purl_id_match.group(1)
            purl_full_url = f"{BASE_URL}/episodes/{purl_id}"
            episode_links.append(purl_full_url)

    print(f"{len(episode_links)} 話の目次情報を取得しました。")
    return episode_links


def download_episode(episode_url, index, novel_title):
    """各話の本文解析と保存処理"""
    response = requests.get(episode_url)
    response.raise_for_status()
    body = response.text

    sect_match = re.search(r'<p class="widget-episodeTitle.*?">.*?</p>', body)
    if sect_match:
        sect_title = sect_match.group(0)
        sect_title_cleaned = re.sub('<.*?>', '', sect_title).strip()

        # 本文取得
        text_body_pattern = r'<p id="p.*?</p>'
        text_matches = re.findall(text_body_pattern, body)

        text_content = ""
        for match in text_matches:
            cleaned_text = tagfilter(match)
            text_content += cleaned_text + "\r\n"

        if text_content:
            folder_index = (index - 1) // 999 + 1  # サブフォルダ番号（999話ごと）
            subfolder_name = f"{folder_index:03}"
            subfolder_path = os.path.join(DOWNLOAD_DIR_BASE, novel_title, subfolder_name)

            os.makedirs(subfolder_path, exist_ok=True)  # サブフォルダ作成

            # ファイル名生成（ゼロ埋め）
            file_name_prefix = f"{index:03}"
            file_name = f"{file_name_prefix}.txt"
            file_path = os.path.join(subfolder_path, file_name)

            if os.path.exists(file_path):  # 既に存在する場合はスキップ
                print(f"{file_path} は既に存在します。スキップします。")
                return

            with codecs.open(file_path, "w", "utf-8") as fout:
                fout.write(f"【タイトル】{sect_title_cleaned}\r\n\r\n{text_content}")

            print(f"{file_path} に保存しました。")
        else:
            print(f"{index} 話の本文が見つかりませんでした。")


def download_novels(urls, history):
    for novel_url in urls:
        try:
            print(f'\n--- 処理開始: {novel_url} ---')

            # 小説タイトルを取得
            toppage_content = loadfromhtml(novel_url)
            novel_title = get_novel_title(toppage_content)

            print(f"小説名: {novel_title}")

            episode_links = get_episode_links(novel_url)

            download_from = history.get(novel_url, 0)
            new_max = download_from

            for i, episode_url in enumerate(episode_links):
                if i + 1 <= download_from:
                    continue

                print(f"{i + 1:03d} downloading...")
                download_episode(episode_url, i + 1, novel_title)
                new_max = i + 1

            history[novel_url] = new_max

        except Exception as e:
            print(f"エラー発生: {novel_url} → {e}")
            continue


# ==== メイン処理 ====

if __name__ == "__main__":
    script_dir = os.path.dirname(__file__)
    url_file_path = os.path.join(script_dir, 'カクヨム.txt')

    with open(url_file_path, 'r', encoding='utf-8') as f:
        urls = [line.strip().rstrip('/') for line in f if line.strip().startswith('http')]

    history = load_history()
    download_novels(urls, history)
    save_history(history)

    subprocess.run([
        'rclone', 'copy', '/tmp/kakuyomu_dl', 'drive:',
        '--transfers=4', '--checkers=8', '--fast-list'
    ], check=True)
