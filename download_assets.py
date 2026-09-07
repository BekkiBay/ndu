import concurrent.futures
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).parent
ASSETS = ROOT / 'assets'
SOURCES = {
    'hero-source.mp4': 'https://newuu.uz/uploads/pages/c4b3a48489a467c45a944228e8e45487.mp4',
    'hero-poster.jpg': 'https://newuu.uz/uploads/pages/13bb6393cb0157487ab75535988f102d.jpg',
    'navdu-seal.png': 'https://nsuz.uz/nsu-seal.png',
    'news-students.jpg': 'https://newuu.uz/uploads/news/b05316a62366e76a013c848e90c8e236.jpg',
    'news-team.jpg': 'https://newuu.uz/uploads/news/1c287a7e2182e7be0b4cfbea8227dea0.jpg',
    'news-lecture.jpg': 'https://newuu.uz/uploads/news/0a02c6964dd2dd86b336ed639a5805c8.jpg',
    'campus-clubs.png': 'https://newuu.uz/uploads/campus_life/5a1f4aae59da8f07662475f11c970b70.png',
    'campus-sport.png': 'https://newuu.uz/uploads/campus_life/02ce74d47df4f4292288fc0e0ce26044.png',
    'campus-building.png': 'https://newuu.uz/uploads/campus_life/ed6401ae94b6b8064014b9a2fb5c90fa.png',
    'campus-events.png': 'https://newuu.uz/uploads/campus_life/2b95df121d4201b0e07dfb44cdaeedf3.png',
}

def fetch(item):
    name, url = item
    dest = ASSETS / name
    if dest.exists():
        return name, dest.stat().st_size, 'existing'
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(request, timeout=60) as response:
        size = int(response.headers.get('Content-Length', '0'))
        if size > 160_000_000:
            raise ValueError(f'{name}: source exceeds 160 MB')
        with dest.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    return name, dest.stat().st_size, 'downloaded'

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(fetch, SOURCES.items()):
            print(result, flush=True)
    font_url = 'https://fonts.googleapis.com/css2?family=Manrope:wght@400..800&display=swap'
    request = Request(font_url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'})
    css = urlopen(request, timeout=30).read().decode()
    for i, url in enumerate(dict.fromkeys(re.findall(r'url\((https://[^)]+)\)', css))):
        name = f'manrope-{i}.woff2'
        print(fetch((name, url)), flush=True)
        css = css.replace(url, name)
        SOURCES[name] = url
    (ASSETS / 'fonts.css').write_text(css)
    (ASSETS / 'sources.json').write_text(json.dumps(SOURCES, indent=2))
