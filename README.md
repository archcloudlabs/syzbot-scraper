# Syzbot Scraper

A tool to scrape and archive syzkaller.appspot.com bug reports and their associated artifacts.

> 🤖 This project was co-developed with AI assistance using [Cursor](https://cursor.sh/)

## Features

- Scrapes bug reports from syzkaller.appspot.com
- Downloads associated artifacts (raw files, reproductions, etc.)
- Supports multiple kernel releases:
  - Upstream
  - Linux 5.15 LTS
  - Linux 6.1 LTS
- Containerized for easy deployment
- Kubernetes-ready with CronJob support

## Local Development

### Prerequisites

- Python 3.11+
- pip

### Setup

1. Install dependencies:
```bash
# For production
pip install -r requirements.txt

# For development/testing
pip install -r requirements-test.txt
```

2. Run the scraper:
```bash
python app.py --release upstream  # or lts-5.15, lts-6.1
```

### Running Tests

```bash
pytest test_app.py -v
```

## Container Deployment

### Building the Container

```bash
# Using Docker
docker build -t syzbot-scraper:latest .

# Using Podman
podman build -t syzbot-scraper:latest .
```

### Running the Container

```bash
docker run -v ./output:/app/output syzbot-scraper:latest --release upstream
```

## Kubernetes Deployment

1. Update the image path in `k8s-cronjob.yaml` to point to your registry
2. Apply the manifests:
```bash
kubectl apply -f k8s-cronjob.yaml
```

The CronJob is configured to:
- Run every 6 hours
- Use a PersistentVolumeClaim for storage
- Prevent concurrent runs
- Maintain history of 3 successful/failed jobs

## Output

Files are saved in the following structure:
```
output/
├── upstream/
│   └── bug_title/
│       ├── repro.c
│       ├── log.txt
│       └── crash.raw
├── linux-5.15/
└── linux-6.1/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT License](LICENSE)

---
*Note: This project uses automated scraping. Please be mindful of syzkaller.appspot.com's resources and implement appropriate rate limiting if modifying the code.*

