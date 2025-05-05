# Project Name

DAWN: Distributed Agentic Workflow for News (with Anthropic's MCP \& Google A2A Protocol Integration)

# Authors

Chenyu Zhang, Alan Morelos

# how to run clinet

make sure you are using node v23.0.0

`cd client`
`npm ci`
`npm start`

# how to run server-crawler

`cd server-crawler`
`conda create -n dawn-crawler python=3.11`
`conda activate dawn-crawler`
`pip install -r requirements.txt`
`python main.py`

# how to run server-summarizer

`cd server-summarizer`
`conda create -n dawn-summarizer python=3.11`
`conda activate dawn-summarizer`
`pip install -r requirements.txt`

## Terminal 1: Primary leader

`python run_leader.py primary`

## Terminal 2: First backup leader

`python run_leader.py backup1`

## Terminal 3: Second backup leader

`python run_leader.py backup2`

## Terminal 4: Worker

`python run_worker.py 1 #repeat command with numbers 2 and 3`

## Testing

### Check health

`python test_client.py health`

### Submit an article

`python test_client.py submit --article 0`

### Check the result (replace with your task ID)

`python test_client.py task <task_id>`

### Or run a full test

`python test_client.py test`

# UIs

<img width="1728" alt="Screenshot 2025-05-04 at 6 06 04 PM" src="https://github.com/user-attachments/assets/97e28740-570b-4fd8-9855-de1128e48498" />
<img width="1728" alt="Screenshot 2025-05-04 at 6 06 45 PM" src="https://github.com/user-attachments/assets/cb392c1c-ecfa-4656-b3bb-74a5cd0e83b6" />

# Acknowledgements

This project was developed as the final assignment for COMPSCI 2620: Introduction to Distributed Computing (Spring 2025) at Harvard University.

# SEAS Design Fair Poster

Preview
<img width="1227" alt="Screenshot 2025-04-28 at 5 31 17 PM" src="https://github.com/user-attachments/assets/a29e571b-1ec2-49ff-a78f-bf503ac923d3" />

Download the PDF
[CHENYUZHANG_CS2620.PDF](https://github.com/user-attachments/files/19949133/CHENYUZHANG_CS2620.PDF)

Latex (overleaf) Email the author to access it.
https://www.overleaf.com/project/680bd375c5ac74795b3cb5fc
