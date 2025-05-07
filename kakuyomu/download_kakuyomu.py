import os
import re
import time
import requests
import subprocess
from bs4 import BeautifulSoup

BASE_URL = "https://kakuyomu.jp"
HISTORY_FILE = "カクヨムダウンロード経歴.txt"
LOCAL_HISTORY_PATH = f"/tmp/{HISTORY_FILE}"
REMOTE_HISTORY_PATH = f"drive:{HISTORY_FILE}"
DOWNLOAD_DIR_BASE = "/tmp/kakuyomu_dl"

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

def get_novel_title(novel_url):
    """<title>タグから小説タイトルを取得"""
    response = requests.get(novel_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.text.strip()
        title_text = re.sub(r'\s*[-ー]?\s*カクヨム.*$', '', title_text)
        return title_text
    else:
        return "タイトルなし"

def get_episode_links(novel_url):
    """目次ページの解析と各話のURL取得"""
    response = requests.get(novel_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    links = soup.select("a.widget-toc-episode")
    
    episode_links = []
    
    # ベースURLを抽出（例：https://kakuyomu.jp/works/16817139555994570519）
    base_url_match = re.match(r"(https://kakuyomu.jp/works/\d+)", novel_url)
    if not base_url_match:
        print("小説のURLからベースURLを抽出できませんでした。")
        return []
    
    base_url = base_url_match.group(1)

    # 各エピソードのURLを作成してリストに追加
    for link in links:
        episode_id = link["href"].split("/")[-1]  # 例：16817139555994608102
        episode_url = f"{base_url}/episodes/{episode_id}"
        episode_links.append((episode_url, link.text.strip()))

    print(f"取得したエピソードURL: {episode_links}")  # デバッグ用に出力
    return episode_links

def download_episode(episode_url, title, novel_title, index):
    """1話分をダウンロードしてファイルに保存"""
    response = requests.get(episode_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    body = soup.select_one("div.widget-episodeBody").get_text("\n", strip=True)

    folder_num = (index // 999) + 1
    folder_name = f"{folder_num:03d}"
    safe_novel_title = re.sub(r'[\\/*?:"<>|]', '_', novel_title)
    folder_path = os.path.join(DOWNLOAD_DIR_BASE, safe_novel_title, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    file_name = f"{index + 1:03d}.txt"
    file_path = os.path.join(folder_path, file_name)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(body)
    time.sleep(1)

def download_novels(urls, history):
    for novel_url in urls:
        try:
            print(f'\n--- 処理開始: {novel_url} ---')

            novel_title = get_novel_title(novel_url)
            novel_title = re.sub(r'[\\/*?:"<>|]', '', novel_title).strip()

            episode_links = get_episode_links(novel_url)

            download_from = history.get(novel_url, 0)
            new_max = download_from

            for i, (episode_url, episode_title) in enumerate(episode_links):
                if i + 1 <= download_from:
                    continue

                print(f"{i + 1:03d}_{episode_title} downloading...")
                download_episode(episode_url, episode_title, novel_title, i)
                new_max = i + 1

                # 300話ごとに30秒休憩を挟む
                if (i + 1) % 300 == 0:
                    print("300話処理完了。30秒間の休憩...")
                    time.sleep(30)

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
