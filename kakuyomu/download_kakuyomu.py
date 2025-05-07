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
    # work_idの抽出
    work_id_match = re.search(r'https://kakuyomu.jp/works/(\d+)', novel_url)
    if not work_id_match:
        print("小説のURLからwork_idを取得できませんでした。")
        return []

    work_id = work_id_match.group(1)

    for ep in ep_matches:
        purl_id_match = re.search(r'"id":"(.*?)"', ep)
        if purl_id_match:
            purl_id = purl_id_match.group(1)
            # 修正：完全なURLを生成
            purl_full_url = f"{BASE_URL}/works/{work_id}/episodes/{purl_id}"
            episode_links.append(purl_full_url)

    print(f"{len(episode_links)} 話の目次情報を取得しました。")
    return episode_links
