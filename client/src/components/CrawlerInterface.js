import React, { useState } from "react";
import "./CrawlerInterface.css";

const CrawlerInterface = () => {
  const [agents, setAgents] = useState([{ url: "" }]);
  const [summaries, setSummaries] = useState([]);
  const [searchDepth, setSearchDepth] = useState(4);
  const [isLoading, setIsLoading] = useState(false);

  console.log("agents", agents);

  const handleAddAgent = () => {
    setAgents([...agents, { url: "" }]);
  };

  const handleUrlChange = (index, value) => {
    const newAgents = [...agents];
    newAgents[index].url = value;
    setAgents(newAgents);
  };

  const handleDelete = (index) => {
    if (agents.length > 1) {
      const newAgents = agents.filter((_, i) => i !== index);
      setAgents(newAgents);
    }
  };

  const handleCrawlerRun = async () => {
    setIsLoading(true);
    setSummaries([]); // Reset summaries at start
    try {
      const validUrls = agents.filter((agent) => agent.url.trim() !== "");

      // Create a promise for each URL but handle them individually
      validUrls.forEach(async (agent, index) => {
        try {
          const response = await fetch("http://localhost:8000/crawl", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              urls: [agent.url],
            }),
          });
          const data = await response.json();
          console.log("data for url", agent.url, data);

          console.log("summary", data.summary);
          console.log("markdown", data.markdown);
          // Update summaries array by adding the new summary
          setSummaries((prevSummaries) => [
            ...prevSummaries,
            {
              summary: data?.summary,
              url: data?.url,
              markdown: data?.markdown,
              error: null,
            },
          ]);
        } catch (error) {
          console.error("Error processing URL:", agent.url, error);
          setSummaries((prevSummaries) => [
            ...prevSummaries,
            { error: `Error processing ${agent.url}: ${error.message}` },
          ]);
        }
      });
    } catch (error) {
      console.error("Error running crawler:", error);
      setSummaries([
        {
          error:
            "Error: Failed to run crawler. Please check the server connection.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  console.log("summaries", summaries);
  return (
    <div className="crawler-interface">
      <div className="input-section">
        <div className="search-depth">
          <label>Search depth:</label>
          <input
            type="number"
            value={searchDepth}
            onChange={(e) => setSearchDepth(parseInt(e.target.value))}
            min="1"
          />
        </div>

        <div className="agents-list">
          {agents.map((agent, index) => (
            <div key={index} className="agent-input">
              <label>Crawler Agent {index + 1}</label>
              <div className="input-with-delete">
                <input
                  type="url"
                  placeholder="please provide a website url"
                  value={agent.url}
                  onChange={(e) => handleUrlChange(index, e.target.value)}
                />
                <button
                  className="delete-button"
                  onClick={() => handleDelete(index)}
                  disabled={agents.length === 1}
                  title={
                    agents.length === 1
                      ? "Cannot delete the last agent"
                      : "Delete agent"
                  }
                >
                  <i className="fas fa-trash"></i>
                </button>
              </div>
            </div>
          ))}
        </div>

        <button className="add-agent" onClick={handleAddAgent}>
          Add Agent
        </button>

        <button
          className="test-run"
          onClick={handleCrawlerRun}
          disabled={isLoading}
        >
          {isLoading ? "Running..." : "Run"}
        </button>
      </div>

      <div className="summary-section">
        <div className="summary-header">
          <h2>Summary</h2>
        </div>
        <div className="summary-content">
          {summaries.map((each, index) => (
            <div key={index} className="summary-item">
              Url: {each.url}
              Summary: {each.summary}
              Markdown: {each.markdown}
            </div>
          ))}
          {summaries.length === 0 && !isLoading && (
            <p className="no-results">Run the crawler to see results</p>
          )}
          {isLoading && <p className="loading">Processing...</p>}
        </div>
      </div>
    </div>
  );
};

export default CrawlerInterface;
