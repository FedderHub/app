const folderInput = document.getElementById("selected-folder");
const checkpointInput = document.getElementById("checkpoint-path");
const pickFolderButton = document.getElementById("pick-folder");
const pickModelFileButton = document.getElementById("pick-model-file");
const form = document.getElementById("client-form");
const logOutput = document.getElementById("log-output");
const statusPill = document.getElementById("status-pill");
const startButton = document.getElementById("start-training");
const validateButton = document.getElementById("validate-inputs");
const requirementsCopy = document.getElementById("dataset-requirements-copy");
const requirementsColumns = document.getElementById("dataset-requirements-columns");
const checkpointRequirements = document.getElementById("checkpoint-requirements");
const validationSummary = document.getElementById("validation-summary");
const resultSummary = document.getElementById("result-summary");
const progressList = document.getElementById("progress-list");

function setStatus(label, className) {
  statusPill.textContent = label;
  statusPill.className = `badge ${className}`.trim();
}

function setLog(text) {
  logOutput.textContent = text;
}

function resetRequirements() {
  requirementsCopy.textContent =
    "Select a checkpoint file to load the expected dataset structure.";
  requirementsColumns.textContent = "";
  checkpointRequirements.textContent =
    "The expected CSV schema is shown after checkpoint inspection.";
}

function resetProgress() {
  Array.from(progressList.querySelectorAll("li")).forEach((item) => {
    item.dataset.state = "pending";
    item.querySelector("strong").textContent = "Pending";
    item.title = "";
  });
}

function updateProgress(step, state, message) {
  const item = progressList.querySelector(`[data-step="${step}"]`);
  if (!item) {
    return;
  }

  item.dataset.state = state;
  item.querySelector("strong").textContent =
    state === "running"
      ? "In progress"
      : state === "completed"
        ? "Completed"
        : state === "failed"
          ? "Failed"
          : "Pending";
  if (message) {
    item.title = message;
  }
}

function setResultSummary(summary = null) {
  const values = summary
    ? {
        "Updated model": summary.localWeightsPath || "Not available",
        "Run summary": summary.localRunSummaryPath || "Not available",
        Checkpoint: summary.checkpoint || "Not available",
        Dataset: summary.dataset || "Not available",
      }
    : {
        "Updated model": "Not available yet",
        "Run summary": "Not available yet",
        Checkpoint: "Not available yet",
        Dataset: "Not available yet",
      };

  resultSummary.innerHTML = Object.entries(values)
    .map(
      ([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`
    )
    .join("");
}

function setButtonsDisabled(isDisabled) {
  startButton.disabled = isDisabled;
  validateButton.disabled = isDisabled;
  pickFolderButton.disabled = isDisabled;
  pickModelFileButton.disabled = isDisabled;
}

function buildPayload() {
  return {
    username: document.getElementById("username").value.trim(),
    password: document.getElementById("password").value,
    checkpointPath: checkpointInput.value.trim(),
    selectedFolder: folderInput.value.trim(),
  };
}

async function runTraining(startFn, options = {}) {
  const payload = buildPayload();

  if (!payload.checkpointPath) {
    setStatus("Checkpoint Needed", "error");
    setLog("Select a PyTorch checkpoint file before starting training.");
    return;
  }

  if (!payload.selectedFolder) {
    setStatus("Folder Needed", "error");
    setLog("Choose a local dataset folder before starting training.");
    return;
  }

  setButtonsDisabled(true);
  resetProgress();
  setResultSummary(null);
  setStatus("Training", "warning");
  setLog(options.startMessage || "Launching training...");
  validationSummary.textContent =
    "Validation is being checked as part of the training launch.";

  try {
    const result = await startFn(payload);
    const combinedOutput = [result.stdout, result.stderr]
      .filter(Boolean)
      .join("\n");

    if (result.ok) {
      setStatus("Completed", "success");
      setLog(combinedOutput || "Training finished successfully.");
      validationSummary.textContent =
        result.validation?.summary || "Validation completed successfully.";
      setResultSummary(result.summary);
    } else {
      setStatus("Failed", "error");
      setLog(combinedOutput || "Training failed without additional output.");
      validationSummary.textContent =
        result.validation?.summary || "Validation did not complete successfully.";
    }
  } catch (error) {
    setStatus("Failed", "error");
    setLog(
      error && error.message
        ? `Training failed to start: ${error.message}`
        : "Training failed to start due to an unexpected error."
    );
  } finally {
    setButtonsDisabled(false);
  }
}

async function validateInputs() {
  const payload = buildPayload();
  resetProgress();
  setResultSummary(null);

  if (!payload.checkpointPath) {
    setStatus("Checkpoint Needed", "error");
    validationSummary.textContent =
      "Select a PyTorch checkpoint file before validating inputs.";
    return;
  }

  if (!payload.selectedFolder) {
    setStatus("Folder Needed", "error");
    validationSummary.textContent =
      "Choose a local dataset folder before validating inputs.";
    return;
  }

  setButtonsDisabled(true);
  setStatus("Validating", "info");
  validationSummary.textContent =
    "Validating checkpoint and dataset compatibility.";
  updateProgress("inspect", "running", "Inspecting checkpoint and dataset.");

  try {
    const result = await window.betaClient.validateInputs(payload);
    if (result.ok) {
      updateProgress("inspect", "completed", result.summary);
      setStatus("Ready", "success");
      validationSummary.textContent = `${result.summary} Dataset file: ${result.datasetPath}`;
      setLog(
        `Validation passed.\n\nDataset file:\n${result.datasetPath}\n\nExpected columns:\n${result.columns.join(", ")}`
      );
    } else {
      updateProgress("inspect", "failed", result.summary);
      setStatus("Validation Failed", "error");
      validationSummary.textContent = result.summary;
      setLog(result.summary);
    }
  } catch (error) {
    updateProgress("inspect", "failed", "Validation failed unexpectedly.");
    setStatus("Validation Failed", "error");
    validationSummary.textContent =
      error && error.message ? error.message : "Validation failed unexpectedly.";
  } finally {
    setButtonsDisabled(false);
  }
}

pickFolderButton.addEventListener("click", async () => {
  const folder = await window.betaClient.selectFolder();
  if (folder) {
    folderInput.value = folder;
    setStatus("Folder Ready", "info");
    setLog(
      `Selected dataset folder:\n${folder}\n\nCheckpoint: ${checkpointInput.value || "not selected"}\n\nThe folder will be mounted read-only during training.`
    );
  }
});

pickModelFileButton.addEventListener("click", async () => {
  const modelFile = await window.betaClient.selectModelFile();
  if (modelFile) {
    checkpointInput.value = modelFile;
    setStatus("Checkpoint Ready", "info");
    resetRequirements();
    const inspection = await window.betaClient.inspectCheckpoint(modelFile);
    checkpointRequirements.textContent = inspection.summary;
    if (inspection.columns && inspection.columns.length > 0) {
      requirementsColumns.textContent = inspection.columns.join(", ");
    } else {
      const fallbackMatch = inspection.summary.match(
        /Expected CSV columns remain (.+?)\.$/
      );
      if (fallbackMatch) {
        requirementsColumns.textContent = fallbackMatch[1];
      }
    }
    setLog(
      `Selected checkpoint file:\n${modelFile}\n\n${inspection.summary}\n\nThe checkpoint will be loaded before training starts.`
    );
  }
});

window.betaClient.onTrainingProgress((payload) => {
  updateProgress(payload.step, payload.state, payload.message);
});

validateButton.addEventListener("click", async () => {
  await validateInputs();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runTraining(window.betaClient.startTraining, {
    startMessage:
      "Preparing the training environment...\n\n1. Inspect checkpoint and dataset\n2. Build the container image\n3. Load the dataset into the runtime\n4. Train the model\n5. Save the updated artifacts",
  });
});
