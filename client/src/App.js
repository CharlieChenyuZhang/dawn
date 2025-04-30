import React from "react";
import "./App.css";
import CrawlerInterface from "./components/CrawlerInterface";

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>DAWN: Distributed Agentic Workflow for News</h1>
      </header>
      <main>
        <CrawlerInterface />
      </main>
    </div>
  );
}

export default App;
