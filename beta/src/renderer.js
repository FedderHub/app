const folderInput = document.getElementById("selected-folder");
const pickFolderButton = document.getElementById("pick-folder");
const form = document.getElementById("client-form");
const logOutput = document.getElementById("log-output");
const statusPill = document.getElementById("status-pill");
const startButton = document.getElementById("start-training");

function setStatus(label, className) {
  statusPill.textContent = label;
  statusPill.className = `badge ${className}`.trim();
}

function setLog(text) {
  logOutput.textContent = text;
}

pickFolderButton.addEventListener("click", async () => {
  const folder = await window.betaClient.selectFolder();
  if (folder) {
    folderInput.value = folder;
    setStatus("Folder Ready", "info");
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    username: document.getElementById("username").value.trim(),
    selectedFolder: folderInput.value.trim(),
  };

  startButton.disabled = true;
  pickFolderButton.disabled = true;
  setStatus("Training", "warning");
  setLog("Launching local training worker...");

  const result = await window.betaClient.startTraining(payload);
  const combinedOutput = [result.stdout, result.stderr].filter(Boolean).join("\n");

  if (result.ok) {
    setStatus("Completed", "success");
    setLog(combinedOutput || "Training finished successfully.");
  } else {
    setStatus("Failed", "error");
    setLog(combinedOutput || "Training failed without additional output.");
  }

  startButton.disabled = false;
  pickFolderButton.disabled = false;
});
