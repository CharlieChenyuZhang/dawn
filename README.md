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

1. **Install dependencies**

   ```sh
   cd server-crawler
   conda create -n dawn-crawler python=3.11
   conda activate dawn-crawler
   pip install -r requirements.txt
   ```

2. **Set up your environment variables**  
   Create a file named `.env` in the `server-crawler` directory with the following content:

   ```
   OPENAI_API_KEY=your_key
   FIRECRAWL_API_KEY=your_actual_api_key
   ```

   Replace `your_actual_api_key` with your real Firecrawl API key.

3. **Run a leader node**
   ```sh
   python run_leader.py primary
   python run_leader.py backup-1
   python run_leader.py backup-2
   ```
   You can run multiple workers by changing the number (1, 2, or 3).
4. **Run a worker node**
   ```sh
   python run_worker.py 1
   python run_worker.py 2
   python run_worker.py 3
   ```
   You can run multiple workers by changing the number (1, 2, or 3).

# how to run server-summarizer-no-replication-implementation (for testing purpose)

`cd server-summarizer-no-replication-implementation`

`conda create -n server-summarizer-no-replication-implementation python=3.11`

`conda activate server-summarizer-no-replication-implementation`

`pip install -r requirements.txt`

`python main.py`

# how to run server-summarizer

Note that all of this should be able to run on a separate machine, you just need to modify `config.py` with the correct machine details.

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

# replication local testing
NOTE: althought we use different ports and processes to demonstrate the distributed system when running locally, they can be deployed in different cloud services (e.g. AWS/GCP) and all you need to do is to change the `config.js` to specify the host and port. 
![Screenshot 2025-05-04 at 8 57 30 PM](https://github.com/user-attachments/assets/f0bb5a98-efab-4b03-a90b-4efc18044aff)


# Acknowledgements

This project was developed as the final assignment for COMPSCI 2620: Introduction to Distributed Computing (Spring 2025) at Harvard University.

# SEAS Design Fair Poster

Preview
<img width="1227" alt="Screenshot 2025-04-28 at 5 31 17 PM" src="https://github.com/user-attachments/assets/a29e571b-1ec2-49ff-a78f-bf503ac923d3" />

Download the PDF
[CHENYUZHANG_CS2620.PDF](https://github.com/user-attachments/files/19949133/CHENYUZHANG_CS2620.PDF)

Latex (overleaf) Email the author to access it.
https://www.overleaf.com/project/680bd375c5ac74795b3cb5fc
