const folderInput = document.getElementById("selected-folder");
const checkpointInput = document.getElementById("checkpoint-path");
const pickFolderButton = document.getElementById("pick-folder");
const pickModelFileButton = document.getElementById("pick-model-file");
const form = document.getElementById("client-form");
const logOutput = document.getElementById("log-output");
const statusPill = document.getElementById("status-pill");
const startButton = document.getElementById("start-training");
const validateButton = document.getElementById("validate-inputs");
const authenticateButton = document.getElementById("authenticate");
const logoutButton = document.getElementById("logout");
const requirementsCopy = document.getElementById("dataset-requirements-copy");
const requirementsColumns = document.getElementById("dataset-requirements-columns");
const checkpointRequirements = document.getElementById("checkpoint-requirements");
const authSummary = document.getElementById("auth-summary");
const sessionSummary = document.getElementById("session-summary");
const validationSummary = document.getElementById("validation-summary");
const resultSummary = document.getElementById("result-summary");
const progressList = document.getElementById("progress-list");

let activeSession = null;

function setStatus(label, className) {
  statusPill.textContent = label;
  statusPill.className = `badge ${className}`.trim();
}

function setLog(text) {
  logOutput.textContent = text;
}

function setAuthSummary(session = null, message = "") {
  if (message) {
    authSummary.textContent = message;
    sessionSummary.textContent = "Authentication is required before checkpoint selection.";
    return;
  }

  if (!session || !session.accessToken) {
    authSummary.textContent = "Not authenticated yet.";
    sessionSummary.textContent = "Sign in to unlock checkpoint selection and training.";
    return;
  }

  authSummary.textContent = `Authenticated as ${session.email} (${session.role || "user"}) via ${session.apiBaseUrl}`;
  sessionSummary.textContent = `Session established at ${new Date(
    session.authenticatedAt || Date.now()
  ).toLocaleString()}.`;
}

function updateAuthControls() {
  const isAuthenticated = Boolean(activeSession && activeSession.accessToken);
  pickModelFileButton.disabled = !isAuthenticated;
  logoutButton.disabled = !isAuthenticated;
}

function applySession(session) {
  activeSession = session && session.accessToken ? session : null;
  setAuthSummary(activeSession);
  updateAuthControls();
}

function requireAuthenticatedSession(actionLabel) {
  if (activeSession && activeSession.accessToken) {
    return true;
  }

  setStatus("Authentication Required", "error");
  setAuthSummary(
    null,
    `Authenticate with Alpha before ${actionLabel}.`
  );
  setLog(`Authenticate with Alpha before ${actionLabel}.`);
  return false;
}

function resetRequirements() {
  requirementsCopy.textContent =
    "Select a checkpoint to load the expected dataset structure.";
  requirementsColumns.textContent = "";
  checkpointRequirements.textContent =
    "The required CSV schema appears after checkpoint inspection.";
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
        "Authenticated User":
          activeSession?.email || summary.operator || "Not available",
        "Updated model": summary.localWeightsPath || "Not available",
        "Run summary": summary.localRunSummaryPath || "Not available",
        Checkpoint: summary.checkpoint || "Not available",
        Dataset: summary.dataset || "Not available",
        "Gamma Stream": summary.gammaStreamStatus || "Not available",
      }
    : {
        "Authenticated User": activeSession?.email || "Not available yet",
        "Updated model": "Not available yet",
        "Run summary": "Not available yet",
        Checkpoint: "Not available yet",
        Dataset: "Not available yet",
        "Gamma Stream": "Not available yet",
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
  pickModelFileButton.disabled =
    isDisabled || !(activeSession && activeSession.accessToken);
  authenticateButton.disabled = isDisabled;
  logoutButton.disabled = isDisabled || !(activeSession && activeSession.accessToken);
}

function buildPayload() {
  return {
    username: document.getElementById("username").value.trim(),
    password: document.getElementById("password").value,
    alphaApiUrl: document.getElementById("alpha-api-url").value.trim(),
    checkpointPath: checkpointInput.value.trim(),
    selectedFolder: folderInput.value.trim(),
    gammaServer: document.getElementById("gamma-server").value.trim(),
    clientId: document.getElementById("client-id").value.trim(),
  };
}

async function authenticateOperator() {
  const payload = buildPayload();

  if (!payload.username) {
    setStatus("Email Needed", "error");
    setAuthSummary(null, "Enter the operator email before authenticating.");
    return;
  }

  if (!payload.password) {
    setStatus("Password Needed", "error");
    setAuthSummary(null, "Enter the operator password before authenticating.");
    return;
  }

  setButtonsDisabled(true);
  updateProgress("auth", "running", "Authenticating with Alpha.");
  setStatus("Authenticating", "info");

  try {
    const result = await window.betaClient.loginToAlpha(payload);
    if (result.ok) {
      updateProgress("auth", "completed", result.summary);
      setStatus("Authenticated", "success");
      applySession(result.session);
      setLog(`${result.summary}\n\nJWT stored for the current desktop session.`);
    } else {
      updateProgress("auth", "failed", result.summary);
      setStatus("Auth Failed", "error");
      applySession(null);
      setAuthSummary(null, result.summary);
      setLog(result.summary);
    }
  } catch (error) {
    const message =
      error && error.message
        ? error.message
        : "Authentication failed unexpectedly.";
    updateProgress("auth", "failed", message);
    setStatus("Auth Failed", "error");
    applySession(null);
    setAuthSummary(null, message);
    setLog(message);
  } finally {
    setButtonsDisabled(false);
  }
}

async function runTraining(startFn, options = {}) {
  const payload = buildPayload();

  if (!requireAuthenticatedSession("starting training")) {
    return;
  }

  if (!payload.checkpointPath) {
    setStatus("Checkpoint Needed", "error");
    setLog("Select a PyTorch checkpoint before starting training.");
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
  setLog(options.startMessage || "Preparing training...");
  validationSummary.textContent =
    "Validation will run as part of training startup.";

  try {
    const result = await startFn(payload);
    const combinedOutput = [result.stdout, result.stderr]
      .filter(Boolean)
      .join("\n");

    if (result.ok) {
      setStatus("Completed", "success");
      setLog(combinedOutput || "Training completed successfully.");
      if (result.auth?.session) {
        applySession(result.auth.session);
      }
      validationSummary.textContent =
        result.validation?.summary || "Validation completed successfully.";
      setResultSummary(result.summary);
    } else {
      setStatus("Failed", "error");
      setLog(combinedOutput || "Training did not complete successfully.");
      if (result.auth?.summary) {
        if (result.auth?.session) {
          applySession(result.auth.session);
        } else {
          setAuthSummary(result.auth?.session || null, result.auth.summary);
        }
      }
      validationSummary.textContent =
        result.validation?.summary || "Validation did not complete successfully.";
    }
  } catch (error) {
    setStatus("Failed", "error");
    setLog(
      error && error.message
        ? `Training failed to start: ${error.message}`
        : "Training could not be started due to an unexpected error."
    );
  } finally {
    setButtonsDisabled(false);
  }
}

async function validateInputs() {
  const payload = buildPayload();
  resetProgress();
  setResultSummary(null);

  if (!requireAuthenticatedSession("validating inputs")) {
    return;
  }

  if (!payload.checkpointPath) {
    setStatus("Checkpoint Needed", "error");
    validationSummary.textContent =
      "Select a PyTorch checkpoint before validating inputs.";
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
        `Validation successful.\n\nDataset file:\n${result.datasetPath}\n\nRequired columns:\n${result.columns.join(", ")}`
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
  if (!requireAuthenticatedSession("selecting a checkpoint")) {
    return;
  }

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
      `Selected checkpoint:\n${modelFile}\n\n${inspection.summary}\n\nThe checkpoint will be loaded before training starts.`
    );
  }
});

authenticateButton.addEventListener("click", async () => {
  await authenticateOperator();
});

logoutButton.addEventListener("click", async () => {
  try {
    await window.betaClient.logoutFromAlpha();
  } catch {
    // Keep local reset behavior even if file cleanup fails.
  }

  activeSession = null;
  checkpointInput.value = "";
  resetRequirements();
  resetProgress();
  setResultSummary(null);
  setAuthSummary(null);
  updateAuthControls();
  setStatus("Logged Out", "muted");
  setLog("Session cleared. Sign in to continue.");
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
      "Preparing the runtime...\n\n1. Authenticate with Alpha\n2. Inspect checkpoint and dataset\n3. Build the container image\n4. Load the dataset into the runtime\n5. Train the model\n6. Save the updated artifacts\n7. Stream mathematical updates to Gamma",
  });
});

window.addEventListener("DOMContentLoaded", async () => {
  try {
    const session = await window.betaClient.getAuthSession();
    applySession(session);
  } catch {
    applySession(null);
  }
});
