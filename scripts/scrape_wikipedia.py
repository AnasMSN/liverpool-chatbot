"""
Pulls Liverpool FC-related pages from Wikipedia and saves them as
plain-text files in data/raw/wikipedia/.

Add or remove page titles from PAGES to control what gets included.
"""

import os
import wikipediaapi
from tqdm import tqdm

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "wikipedia")

PAGES = [
    "Liverpool F.C.",
    "History of Liverpool F.C.",
    "List of Liverpool F.C. players",
    "Liverpool F.C. in European football",
    "Anfield",
    "Liverpool F.C.–Manchester United F.C. rivalry",
    "Mohamed Salah",
    "Virgil van Dijk",
    "Trent Alexander-Arnold",
    "Jürgen Klopp",
    "Arne Slot",
    "Bill Shankly",
    "Kop (stand)",
    "1989 FA Cup Final",  # example of a historic match page
    "2019 UEFA Champions League Final",
]


def fetch_and_save(wiki: wikipediaapi.Wikipedia, title: str) -> None:
    page = wiki.page(title)
    if not page.exists():
        print(f"  [skip] page not found: {title}")
        return

    safe_name = title.replace("/", "_").replace(" ", "_")
    out_path = os.path.join(OUT_DIR, f"{safe_name}.txt")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"TITLE: {page.title}\n")
        f.write(f"SOURCE: {page.fullurl}\n\n")
        f.write(page.text)

    print(f"  [ok] saved {title} ({len(page.text)} chars)")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    wiki = wikipediaapi.Wikipedia(
        user_agent="LiverpoolFCChatbot/1.0 (portfolio project)",
        language="en",
    )

    print(f"Fetching {len(PAGES)} Wikipedia pages...")
    for title in tqdm(PAGES):
        fetch_and_save(wiki, title)

    print(f"\nDone. Files saved to: {os.path.abspath(OUT_DIR)}")


if __name__ == "__main__":
    main()
