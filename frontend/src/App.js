import { useEffect, useState } from "react";
import axios from "axios";

function App() {
  const [health, setHealth] = useState("Loading...");

  useEffect(() => {
    axios
      .get("http://127.0.0.1:8000/health")
      .then((res) => setHealth(res.data.status))
      .catch(() => setHealth("Backend unreachable"));
  }, []);

  return (
    <div style={{ padding: "40px", fontFamily: "Arial" }}>
      <h1>FederHub Alpha Frontend</h1>
      <p>Phase 1 blank dashboard</p>
      <p>Backend health: {health}</p>
    </div>
  );
}

export default App;