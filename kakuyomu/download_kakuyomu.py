import os
import re
import time
import requests
import subprocess
from bs4 import BeautifulSoup

LOCAL_HISTORY_PATH = "/tmp/カクヨムダウンロード経歴.txt"
REMOTE_HISTORY_PATH = "drive:/カクヨムダウンロード経歴.txt"
DOWNLOAD_DIR = "/tmp/novel_dl"

def upload_history_to_drive():
    subprocess.run([
        "rclone", "copyto", LOCAL_HISTORY_PATH, REMOTE_HISTORY_PATH,
        "--progress"
    ], check=True)
    os.remove(LOCAL_HISTORY_PATH)  # 元ファイルを削除してmoveと同じ挙動に

def read_history():
    if os.path.isdir(LOCAL_HISTORY_PATH):
        print(f"{LOCAL_HISTORY_PATH} はディレクトリとして存在していたため削除します。")
        os.rmdir(LOCAL_HISTORY_PATH)
    if not os.path.exists(LOCAL_HISTORY_PATH):
        return {}
    with open(LOCAL_HISTORY_PATH, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    history = {}
    for line in lines:
        if " | " in line:
            url, last_count = line.split(" | ")
            history[url.strip()] = int(last_count.strip())
    return history

def write_history(history):
    with open(LOCAL_HISTORY_PATH, "w", encoding="utf-8") as f:
        for url, count in history.items():
            f.write(f"{url} | {count}\n")

def fetch_episode_urls(work_url):
    print(f"Fetching episode URLs for: {work_url}")  # デバッグ用
    res = requests.get(work_url)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    episode_links = soup.select("a.widget-episode-title")
    episode_urls = [f"https://kakuyomu.jp{a['href']}" for a in episode_links]
    print(f"Found {len(episode_urls)} episode(s).")  # デバッグ用
    return episode_urls

def fetch_episode_content(episode_url):
    res = requests.get(episode_url)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    title = soup.select_one("h1").text.strip()
    body = soup.select_one("div#contentMain-inner")
    paragraphs = body.select("p")
    text = "\n".join(p.text.strip() for p in paragraphs)
    return title, text

def download_new_episodes(work_url, last_downloaded_count):
    episode_urls = fetch_episode_urls(work_url)
    new_urls = episode_urls[last_downloaded_count:]
    if not new_urls:
        print(f"  → 新しい話はありません。スキップします。")
        return last_downloaded_count

    work_id = work_url.rstrip("/").split("/")[-1]
    save_dir = os.path.join(DOWNLOAD_DIR, work_id)
    os.makedirs(save_dir, exist_ok=True)

    for idx, url in enumerate(new_urls, start=last_downloaded_count + 1):
        print(f"  → 第{idx}話 をダウンロード中: {url}")
        title, content = fetch_episode_content(url)
        with open(os.path.join(save_dir, f"{idx:04}_{title}.txt"), "w", encoding="utf-8") as f:
            f.write(f"{title}\n\n{content}")
        time.sleep(1)  # アクセス間隔

    return len(episode_urls)

def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    history = read_history()

    with open("kakuyomu/カクヨム.txt", "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    # 初回時、historyが空の場合は全エピソードをダウンロード
    for url in urls:
        print(f"--- 処理開始: {url} ---")
        last = history.get(url, 0)  # 履歴がない場合は 0
        latest = download_new_episodes(url, last)
        history[url] = latest

    write_history(history)
    upload_history_to_drive()

if __name__ == "__main__":
    main()
