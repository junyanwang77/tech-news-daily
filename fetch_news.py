#!/usr/bin/env python3
import subprocess
import xml.etree.ElementTree as ET
import datetime
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 读取 API Key
with open(os.path.join(BASE_DIR, ".env")) as f:
    for line in f:
        k, _, v = line.strip().partition("=")
        os.environ[k] = v

import anthropic

FEEDS = [
    ("TechCrunch",           "https://techcrunch.com/feed/"),
    ("The Verge",            "https://www.theverge.com/rss/index.xml"),
    ("Wired",                "https://www.wired.com/feed/rss"),
    ("MIT Technology Review","https://www.technologyreview.com/feed/"),
    ("Ars Technica",         "https://feeds.arstechnica.com/arstechnica/index"),
    ("Hacker News",          "https://news.ycombinator.com/rss"),
]

def clean(text):
    return re.sub(r'<[^>]+>', '', text or '').strip()[:300]

# ── 抓取 RSS ──────────────────────────────────────────────
articles = []
for source, url in FEEDS:
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "15", "-L", "-A", "Mozilla/5.0", url],
            capture_output=True, text=True
        )
        root = ET.fromstring(result.stdout)
        items = root.findall(".//item")
        for item in items[:3]:
            title = clean(item.findtext("title", ""))
            link  = (item.findtext("link") or "").strip()
            desc  = clean(item.findtext("description", ""))
            if title and link:
                articles.append({"source": source, "title": title, "link": link, "desc": desc})
        if not items:
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            for entry in entries[:3]:
                title   = clean(entry.findtext("{http://www.w3.org/2005/Atom}title", ""))
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
                link    = link_el.get("href", "") if link_el is not None else ""
                desc    = clean(entry.findtext("{http://www.w3.org/2005/Atom}summary", ""))
                if title and link:
                    articles.append({"source": source, "title": title, "link": link, "desc": desc})
    except Exception as e:
        print(f"跳过 {source}: {e}")

articles = articles[:10]

# ── 翻译 ──────────────────────────────────────────────────
client = anthropic.Anthropic()
to_translate = "\n".join(
    f"{i+1}. 标题：{a['title']}\n   摘要：{a['desc']}"
    for i, a in enumerate(articles)
)
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2000,
    messages=[{"role": "user", "content": (
        "请将以下科技新闻的标题和摘要翻译成中文，保持编号对应，格式严格如下：\n"
        "1. 标题：<中文标题>\n   摘要：<中文摘要>\n\n" + to_translate
    )}]
)
translations = {}
current = None
for line in response.content[0].text.splitlines():
    m = re.match(r'^(\d+)\.\s*标题[：:]\s*(.+)', line.strip())
    if m:
        current = int(m.group(1)) - 1
        translations[current] = {"title_cn": m.group(2).strip(), "desc_cn": ""}
    elif current is not None:
        m2 = re.match(r'摘要[：:]\s*(.+)', line.strip())
        if m2:
            translations[current]["desc_cn"] = m2.group(1).strip()

# ── 日期 ──────────────────────────────────────────────────
today     = datetime.date.today()
today_str = today.strftime("%Y-%m-%d")
today_cn  = today.strftime("%Y年%m月%d日")

# ── 生成 Markdown ─────────────────────────────────────────
news_dir = os.path.join(BASE_DIR, "news")
os.makedirs(news_dir, exist_ok=True)

md_lines = [f"# 每日科技要闻 · {today_cn}\n"]
for i, a in enumerate(articles, 1):
    t = translations.get(i - 1, {})
    md_lines.append(f"**{i}. {t.get('title_cn', '')}**")
    md_lines.append(f"*{a['title']}*")
    if t.get("desc_cn"):
        md_lines.append(f"摘要：{t['desc_cn']}")
    if a["desc"]:
        md_lines.append(f"Summary: {a['desc']}")
    md_lines.append(f"来源 / Source：[{a['source']}]({a['link']})")
    md_lines.append("\n---\n")
md_lines.append("*自动生成 · 每日科技要闻*")

md_path = os.path.join(news_dir, f"{today_str}.md")
with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(md_lines))

# ── 生成 index.html ───────────────────────────────────────
cards_html = ""
for i, a in enumerate(articles, 1):
    t = translations.get(i - 1, {})
    title_cn = t.get("title_cn", a["title"])
    desc_cn  = t.get("desc_cn", "")
    cards_html += f"""
    <div class="card">
      <div class="num">{i}</div>
      <div class="content">
        <h2><a href="{a['link']}" target="_blank">{title_cn}</a></h2>
        <p class="en-title">{a['title']}</p>
        {"<p class='desc'>" + desc_cn + "</p>" if desc_cn else ""}
        {"<p class='desc en'>" + a['desc'] + "</p>" if a['desc'] else ""}
        <span class="source">{a['source']}</span>
      </div>
    </div>"""

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日科技要闻 · {today_cn}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
          background: #f4f6f9; color: #222; }}
  header {{ background: #1a1a2e; color: #fff; padding: 24px 20px; text-align: center; }}
  header h1 {{ font-size: 1.4em; font-weight: 700; }}
  header p  {{ font-size: 0.9em; opacity: 0.7; margin-top: 6px; }}
  .container {{ max-width: 720px; margin: 0 auto; padding: 16px; }}
  .card {{ background: #fff; border-radius: 12px; padding: 18px;
            margin-bottom: 14px; box-shadow: 0 2px 8px rgba(0,0,0,.06);
            display: flex; gap: 14px; }}
  .num {{ font-size: 1.6em; font-weight: 800; color: #e0e0e0;
           min-width: 32px; line-height: 1; padding-top: 2px; }}
  .content {{ flex: 1; }}
  .content h2 {{ font-size: 1.05em; line-height: 1.4; }}
  .content h2 a {{ color: #1a1a2e; text-decoration: none; }}
  .content h2 a:hover {{ text-decoration: underline; }}
  .en-title {{ font-size: 0.8em; color: #999; margin-top: 4px; font-style: italic; }}
  .desc {{ font-size: 0.88em; color: #444; margin-top: 8px; line-height: 1.6; }}
  .desc.en {{ color: #888; font-size: 0.82em; }}
  .source {{ display: inline-block; margin-top: 10px; font-size: 0.75em;
              background: #f0f4ff; color: #5568d4; padding: 3px 10px;
              border-radius: 20px; }}
  footer {{ text-align: center; padding: 24px; font-size: 0.78em; color: #aaa; }}
</style>
</head>
<body>
<header>
  <h1>📡 每日科技要闻</h1>
  <p>{today_cn} · 中英双语</p>
</header>
<div class="container">
  {cards_html}
</div>
<footer>自动生成 · 每日科技要闻 · Claude Code</footer>
</body>
</html>"""

html_path = os.path.join(BASE_DIR, "index.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

# ── 推送到 GitHub ─────────────────────────────────────────
os.chdir(BASE_DIR)
subprocess.run(["git", "config", "user.email", "bot@claude.ai"], check=True)
subprocess.run(["git", "config", "user.name", "Claude News Bot"], check=True)
subprocess.run(["git", "add", f"news/{today_str}.md", "index.html"], check=True)
subprocess.run(["git", "commit", "-m", f"docs: 科技要闻 {today_str}"], check=True)
subprocess.run(["git", "push"], check=True)

print(f"✅ 完成！已生成 {today_str}.md 并推送到 GitHub")
