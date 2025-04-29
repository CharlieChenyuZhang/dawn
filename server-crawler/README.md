# News Crawler API Server

A FastAPI-based server that manages news crawling and summarization agents.

## Setup

1. Create a Conda environment:

```bash
conda create -n dawn python=3.11
conda activate dawn
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the Server

Start the server with:

```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at http://localhost:8000

## API Documentation

Once the server is running, you can access:

- Interactive API docs: http://localhost:8000/docs
- Alternative API docs: http://localhost:8000/redoc

## Available Endpoints

- POST `/crawl/start` - Start crawler agents
- GET `/crawl/status` - Get crawler agent statuses
- POST `/summarize/start` - Start summarizer agents manually
- GET `/summarize/status` - Get summarizer agent statuses
- GET `/news/live` - Get crawled (but maybe not summarized) news
- GET `/news/summaries` - Get summarized and deduplicated news

## Development

To deactivate the Conda environment when you're done:

```bash
conda deactivate
```

To remove the environment if needed:

```bash
conda remove --name news-crawler --all
```
