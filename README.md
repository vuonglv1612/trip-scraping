# Trip scrape

## Installation

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
./venv/bin/scrapy crawl trip -o trip.jsonl -a links_path=sample_links.txt
```

## Target Links

You can find the links to the trips in the `sample_links.txt` file. Each line is a link to a trip.
