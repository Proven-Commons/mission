"""Check the internal links of the built website.

Every Markdown file in this repo becomes a page, so a link that works on
GitHub can break on the site. This reads every page in the build output and
reports each internal link whose target file or #id does not exist.

Usage: python3 check_site_links.py <site-dir> <baseurl>
Exits 1 if any link is broken.
"""
import os
import sys
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag in ("link", "img", "script"):
            link = attrs.get("href") or attrs.get("src")
            if link:
                self.links.append(link)


def main(site, base):
    base = "/" + base.strip("/") + "/" if base.strip("/") else "/"

    def url_of(path):
        rel = os.path.relpath(path, site).replace(os.sep, "/")
        if rel == "index.html" or rel.endswith("/index.html"):
            rel = rel[: -len("index.html")]
        return base + rel

    def file_of(url_path):
        path = unquote(url_path)
        if not path.startswith(base):
            return None
        path = os.path.join(site, path[len(base):])
        if path.endswith("/") or os.path.isdir(path):
            path = os.path.join(path, "index.html")
        return path

    pages = {}
    for folder, _, names in os.walk(site):
        for name in names:
            if name.endswith(".html"):
                path = os.path.join(folder, name)
                page = Page()
                with open(path, encoding="utf-8") as f:
                    page.feed(f.read())
                pages[path] = page

    broken = []
    for path, page in sorted(pages.items()):
        here = url_of(path)
        for link in page.links:
            if urlparse(link).scheme or link.startswith("//"):
                continue
            target = urlparse(urljoin("https://site" + here, link))
            target_file = file_of(target.path)
            if target_file is None or not os.path.exists(target_file):
                broken.append((here, link, "no such page or file"))
            elif target.fragment and target_file in pages:
                if target.fragment not in pages[target_file].ids:
                    broken.append((here, link, "no such #id"))

    for here, link, why in broken:
        print(f"::error::{here}: link {link}: {why}")
    print(f"Checked {len(pages)} pages: {len(broken)} broken links.")
    if not pages:
        print("::error::No pages found. Did the build run?")
        return 1
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
