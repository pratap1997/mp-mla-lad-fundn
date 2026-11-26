# Firecrawl integration for JS-rendered civic portals (e.g., Jan Soochna Portal,
# Rajasthan Legislative Assembly Q&A, CAG audit pages).
# Usage:
#   set FIRECRAWL_API_KEY=fc-...
#   python firecrawl_scrape.py https://jansoochna.rajasthan.gov.in/

import os
import sys
import json
from firecrawl import Firecrawl

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)


def scrape_url(url: str, formats: list[str] | None = None) -> dict:
    api_key = os.environ.get('FIRECRAWL_API_KEY')
    if not api_key:
        raise RuntimeError(
            'FIRECRAWL_API_KEY environment variable is not set. '
            'Get a key at https://firecrawl.dev or point FIRECRAWL_API_URL to a self-hosted instance.'
        )
    app = Firecrawl(api_key=api_key, api_url=os.environ.get('FIRECRAWL_API_URL'))
    result = app.scrape(url, formats=formats or ['markdown', 'links'])
    return result if isinstance(result, dict) else result.model_dump()


def main():
    if len(sys.argv) < 2:
        print('Usage: python firecrawl_scrape.py <url> [output_json]')
        sys.exit(1)

    url = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'firecrawl_output.json'
    )
    data = scrape_url(url)
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f'Saved Firecrawl output for {url} -> {out_file}')


if __name__ == '__main__':
    main()
