import requests
import os
import re
import time
from bs4 import BeautifulSoup

def get_episode_links(novel_url):
    """目次ページのHTMLを正規表現で解析し、各話のURLを抽出"""
    response = requests.get(novel_url)
    response.raise_for_status()
    html = response.text

    print("小説情報を取得中...")

    # "__typename":"Episode" ブロックを正規表現で抽出
    ep_pattern = r'"__typename":"Episode","id":"(.*?)","title":"(.*?)",'
    ep_matches = re.findall(ep_pattern, html)

    if not ep_matches:
        print("指定されたページからエピソード情報を取得できませんでした。")
        return []

    # 各エピソードURLを作成
    episode_links = []
    for episode_id, title in ep_matches:
        episode_url = f"{novel_url}/episodes/{episode_id}"
        episode_links.append((episode_url, title.strip()))

    print(f"{len(episode_links)} 話の目次情報を取得しました。")
    return episode_links


def download_episode(url, title, index, novel_title):
    """各話の本文を取得して保存"""
    response = requests.get(url)
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # 本文抽出
    text_area = soup.find("div", {"id": "content-main"})
    if not text_area:
        print(f"{index} 話の本文が見つかりませんでした。")
        return

    paragraphs = text_area.find_all("p")
    if not paragraphs:
        print(f"{index} 話の本文が見つかりませんでした。")
        return

    text = "\r\n".join(p.get_text(strip=True) for p in paragraphs)

    folder_index = (index - 1) // 999 + 1  # サブフォルダ番号（999話ごと）
    subfolder_name = f"{folder_index:03}"
    subfolder_path = os.path.join(novel_title, subfolder_name)
    os.makedirs(subfolder_path, exist_ok=True)

    filename = os.path.join(subfolder_path, f"{index:03}.txt")
    if os.path.exists(filename):
        print(f"{filename} は既に存在します。スキップします。")
        return

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"【タイトル】{title}\r\n\r\n{text}")

    print(f"{filename} に保存しました。")
    time.sleep(0.01)  # 軽負荷


def main():
    print("kakudlpy ver1.1 2025/03/07 (c) INOUE, masahiro")

    while True:
        novel_url = input("カクヨム作品トップページのURLを入力してください: ").strip()
        if re.match(r'https://kakuyomu.jp/works/\d{19,20}', novel_url):
            break
        else:
            print("正しいカクヨム作品トップページURLを入力してください。")

    response = requests.get(novel_url)
    response.raise_for_status()
    html = response.text

    title_match = re.search(r'<title>(.*?) - カクヨム</title>', html)
    if title_match:
        novel_title = re.sub(r'[\\/:*?"<>|]', '', title_match.group(1).strip())
    else:
        novel_title = "無題"

    print(f"取得した小説名: {novel_title}")
    os.makedirs(novel_title, exist_ok=True)

    episode_links = get_episode_links(novel_url)
    if not episode_links:
        return

    for i, (url, title) in enumerate(episode_links, start=1):
        download_episode(url, title, i, novel_title)

    print(f"{len(episode_links)} 話のエピソードを取得しました。")

if __name__ == '__main__':
    main()
