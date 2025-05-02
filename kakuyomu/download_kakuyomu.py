import os
import re
import time
import requests
import subprocess
from bs4 import BeautifulSoup

BASE_URL = "https://kakuyomu.jp"
DOWNLOAD_DIR = "/tmp/kakuyomu_dl"
TMP_HISTORY_FILE = os.path.join(DOWNLOAD_DIR, "カクヨムダウンロード経歴.txt")
HISTORY_FILE = TMP_HISTORY_FILE  # ローカルでダウンロードした履歴ファイルをそのまま使用
NOVEL_LIST_FILE = "kakuyomu/カクヨム.txt"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Google Driveからhistoryファイルを一時ディレクトリにダウンロード
def download_history_from_drive():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    subprocess.run([
        "rclone", "copy", "drive:/カクヨムダウンロード経歴.txt", DOWNLOAD_DIR,
        "--progress"
    ], check=True)

# 履歴ファイルを読み込む
def read_history():
    history = {}
    if os.path.exists(TMP_HISTORY_FILE):
        with open(TMP_HISTORY_FILE, encoding="utf-8") as f:
            for line in f:
                url, last = line.strip().split(" | ")
                history[url] = int(last)
    return history

# 履歴ファイルを書き込む
def write_history(history):
    with open(TMP_HISTORY_FILE, "w", encoding="utf-8") as f:
        for url, last in history.items():
            f.write(f"{url} | {last}\n")

# 目次ページからエピソードリンクを取得
def get_episode_links(novel_url):
    res = requests.get(novel_url)
    soup = BeautifulSoup(res.text, "html.parser")
    links = soup.select("a.widget-toc-episode")
    return [BASE_URL + a["href"] for a in links]

# エピソードをダウンロード
def download_episode(url):
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    title = soup.select_one("h1.widget-episodeTitle").text.strip()
    content = soup.select_one("div.widget-episodeBody").decode_contents()
    episode_id = url.split("/")[-1]
    return f"# {title}\n\n{content}", episode_id

# ファイル名に使用できない文字を除去
def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

# 小説タイトルを取得
def get_novel_title(novel_url):
    res = requests.get(novel_url)
    soup = BeautifulSoup(res.text, "html.parser")
    return soup.select_one("h1.widget-title").text.strip()

# メイン処理
def main():
    download_history_from_drive()  # Google Driveから履歴をダウンロード
    history = read_history()

    with open(NOVEL_LIST_FILE, encoding="utf-8") as f:
        novels = [line.strip() for line in f if line.strip()]

    for novel_url in novels:
        print(f"--- 処理開始: {novel_url} ---")
        episode_links = get_episode_links(novel_url)
        last_downloaded = history.get(novel_url, 0)
        to_download = episode_links[last_downloaded:]

        if not to_download:
            print("  → 新しい話はありません。スキップします。")
            continue

        novel_title = sanitize_filename(get_novel_title(novel_url))
        novel_dir = os.path.join(DOWNLOAD_DIR, novel_title)
        os.makedirs(novel_dir, exist_ok=True)

        for i, episode_url in enumerate(to_download, 1):
            content, eid = download_episode(episode_url)
            with open(os.path.join(novel_dir, f"{last_downloaded+i:04}_{eid}.html"), "w", encoding="utf-8") as f:
                f.write(content)

            if i % 300 == 0:
                print("  → 300話ごとに1分待機...")
                time.sleep(60)

        history[novel_url] = last_downloaded + len(to_download)
        print(f"  → {len(to_download)}話ダウンロード完了")

    write_history(history)

    # Google Driveへアップロード
    subprocess.run([
        "rclone", "copy", DOWNLOAD_DIR, "drive:/kakuyomu_dl",
        "--transfers=4", "--checkers=8", "--fast-list"
    ], check=True)

if __name__ == "__main__":
    main()
