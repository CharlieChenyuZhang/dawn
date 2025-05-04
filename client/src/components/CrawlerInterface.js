import React, { useState } from "react";
import "./CrawlerInterface.css";

const CrawlerInterface = () => {
  const [agents, setAgents] = useState([{ url: "" }]);
  const [summaries, setSummaries] = useState([]);
  const [searchDepth, setSearchDepth] = useState(4);
  const [isLoading, setIsLoading] = useState(false);

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
      if (validUrls.length === 0) {
        setIsLoading(false);
        return;
      }
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
          setSummaries((prevSummaries) => [
            ...prevSummaries,
            { error: `Error processing ${agent.url}: ${error.message}` },
          ]);
        }
      });
    } catch (error) {
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

  return (
    <div className="crawler-interface">
      <div className="input-section">
        <div className="search-depth">
          <label htmlFor="search-depth-input">Search depth:</label>
          <input
            id="search-depth-input"
            type="number"
            value={searchDepth}
            onChange={(e) => setSearchDepth(parseInt(e.target.value))}
            min="1"
            aria-label="Search depth"
          />
        </div>

        <div className="agents-list">
          {agents.map((agent, index) => (
            <div key={index} className="agent-input">
              <label htmlFor={`agent-url-${index}`}>{`Crawler Agent ${
                index + 1
              }`}</label>
              <div className="input-with-delete">
                <input
                  id={`agent-url-${index}`}
                  type="url"
                  placeholder="please provide a website url"
                  value={agent.url}
                  onChange={(e) => handleUrlChange(index, e.target.value)}
                  aria-label={`URL for Crawler Agent ${index + 1}`}
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
                  aria-label={
                    agents.length === 1
                      ? "Cannot delete the last agent"
                      : `Delete Crawler Agent ${index + 1}`
                  }
                >
                  <i className="fas fa-trash"></i>
                </button>
              </div>
            </div>
          ))}
        </div>

        <button
          className="add-agent"
          onClick={handleAddAgent}
          aria-label="Add Agent"
        >
          Add Agent
        </button>

        <button
          className="test-run"
          onClick={handleCrawlerRun}
          disabled={
            isLoading || agents.filter((a) => a.url.trim() !== "").length === 0
          }
          aria-label="Run Crawler"
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
            <div key={index} className="summary-card">
              {each.error ? (
                <div className="summary-error" role="alert">
                  {each.error}
                </div>
              ) : (
                <>
                  <div className="summary-url">
                    <strong>URL:</strong>{" "}
                    <a
                      href={each.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {each.url}
                    </a>
                  </div>
                  <div className="summary-title">
                    <strong>Summary:</strong>
                  </div>
                  <div className="summary-text">{each.summary}</div>
                  <div className="summary-title">
                    <strong>Markdown:</strong>
                  </div>
                  <pre className="summary-markdown">{each.markdown}</pre>
                </>
              )}
            </div>
          ))}
          {summaries.length === 0 && !isLoading && (
            <p className="no-results">Run the crawler to see results</p>
          )}
          {isLoading && (
            <div className="loading-spinner" aria-label="Loading"></div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CrawlerInterface;
