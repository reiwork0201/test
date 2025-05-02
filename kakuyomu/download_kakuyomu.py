import os
import re
import time
import requests
import subprocess
from bs4 import BeautifulSoup

BASE_URL = "https://kakuyomu.jp"
DOWNLOAD_DIR = "/tmp/kakuyomu_dl"
HISTORY_FILE = "/tmp/カクヨムダウンロード経歴.txt"  # ローカルに保存されるように変更
NOVEL_LIST_FILE = "kakuyomu/カクヨム.txt"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Google Driveからhistoryファイルをダウンロード
def download_history_from_drive():
    subprocess.run([
        "rclone", "copy", "drive:/カクヨムダウンロード経歴.txt", HISTORY_FILE,
        "--progress"
    ], check=True)

# Google Driveにhistoryファイルをアップロード
def upload_history_to_drive():
    subprocess.run([
        "rclone", "move", HISTORY_FILE, "drive:/カクヨムダウンロード経歴.txt",
        "--progress"
    ], check=True)

def read_history():
    # HISTORY_FILEがディレクトリでないか確認
    if os.path.isdir(HISTORY_FILE):
        raise IsADirectoryError(f"{HISTORY_FILE}はディレクトリです。")

    history = {}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            for line in f:
                work_url, episodes_str = line.strip().split(" | ")
                episodes = set(episodes_str.split(","))
                history[work_url] = episodes
    return history

def write_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        for work_url, episodes in history.items():
            f.write(f"{work_url} | {','.join(episodes)}\n")

def fetch_episode_urls(work_url):
    print(f"Fetching episode URLs for: {work_url}")  # デバッグ用
    res = requests.get(work_url)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    
    # エピソードリンクの取得方法を確認
    episode_links = soup.select("a.widget-episode-link")  # 正しいセレクタを指定
    episode_urls = [f"{BASE_URL}{a['href']}" for a in episode_links]
    print(f"Found {len(episode_urls)} episode(s).")  # デバッグ用
    return episode_urls

def download_episode(episode_url):
    print(f"Downloading episode: {episode_url}")
    res = requests.get(episode_url)
    res.raise_for_status()
    
    # エピソードのタイトルと内容を保存する
    soup = BeautifulSoup(res.text, "html.parser")
    title = soup.select_one("h1.widget-title").text.strip()
    content = soup.select_one("div.widget-episode-body").text.strip()
    
    filename = os.path.join(DOWNLOAD_DIR, f"{title}.txt")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    download_history_from_drive()  # Google Driveから履歴をダウンロード
    history = read_history()

    with open(NOVEL_LIST_FILE, encoding="utf-8") as f:
        novel_urls = f.read().splitlines()

    for novel_url in novel_urls:
        print(f"--- 処理開始: {novel_url} ---")
        episode_urls = fetch_episode_urls(novel_url)
        
        # 各エピソードをダウンロード
        to_download = []
        for episode_url in episode_urls:
            # すでにダウンロードされたエピソードをスキップ
            if episode_url in history.get(novel_url, []):
                continue
            to_download.append(episode_url)
        
        if to_download:
            for episode_url in to_download:
                download_episode(episode_url)  # エピソードのダウンロード処理
                history.setdefault(novel_url, []).append(episode_url)
            print(f"  → {len(to_download)}話ダウンロード完了")
        else:
            print("  → 新しい話はありません。スキップします。")
    
    write_history(history)
    upload_history_to_drive()  # 処理後に履歴をGoogle Driveにアップロード
    
    # ダウンロードした小説をGoogle Driveへアップロード
    subprocess.run([
        "rclone", "copy", DOWNLOAD_DIR, "drive:/kakuyomu_dl",
        "--transfers=4", "--checkers=8", "--fast-list"
    ], check=True)

if __name__ == "__main__":
    main()
