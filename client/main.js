const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const path = require("path");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");

const DEFAULT_ALPHA_API_URL = "http://127.0.0.1:8000";
const DEFAULT_GAMMA_SERVER = "host.docker.internal:50051";

// ============================================================================
// macOS GUI PATH Patch (Minimal & Clean)
// ============================================================================
if (process.platform === "darwin") {
  const defaultPaths = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"];
  const currentPaths = process.env.PATH ? process.env.PATH.split(":") : [];
  process.env.PATH = Array.from(new Set([...defaultPaths, ...currentPaths])).join(":");
}

function getAbsolutePath(cmd) {
  try {
    const command = process.platform === "win32" ? "where" : "which";
    return execFileSync(command, [cmd], { encoding: "utf8" }).toString().split('\n')[0].trim();
  } catch {
    return cmd;
  }
}

function findDocker() {
  try {
    execFileSync("docker", ["--version"], { stdio: "ignore" });
    return getAbsolutePath("docker");
  } catch {
    return null;
  }
}

function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

function runCommand(command, args, options = {}) {
  return new Promise((resolve) => {
    let child;
    let stdout = "";
    let stderr = "";

    try { child = spawn(command, args, { shell: false, env: process.env, ...options }); } 
    catch (error) { return resolve({ ok: false, code: null, stdout, stderr: error.message }); }

    child.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
    child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
    
    child.on("error", (error) => resolve({ ok: false, code: null, stdout, stderr: `${stderr}\n${error.message}`.trim() }));
    child.on("close", (code) => resolve({ ok: code === 0, code, stdout, stderr }));
  });
}

function runStreamingCommand(command, args, options = {}) {
  return new Promise((resolve) => {
    let child;
    let stdout = "";
    let stderr = "";

    try { child = spawn(command, args, { shell: false, env: process.env, ...options }); } 
    catch (error) { return resolve({ ok: false, code: null, stdout, stderr: error.message }); }

    child.stdout.on("data", (chunk) => {
      const text = chunk.toString();
      stdout += text;
      options.onStdout?.(text);
    });

    child.stderr.on("data", (chunk) => {
      const text = chunk.toString();
      stderr += text;
      options.onStderr?.(text);
    });

    child.on("error", (error) => resolve({ ok: false, code: null, stdout, stderr: `${stderr}\n${error.message}`.trim() }));
    child.on("close", (code) => resolve({ ok: code === 0, code, stdout, stderr }));
  });
}

function buildTrainingPayload(payload) {
  const safePayload = payload && typeof payload === "object" ? payload : {};
  return {
    username: safePayload.username || "",
    password: safePayload.password || "",
    checkpointPath: safePayload.checkpointPath || "",
    selectedFolder: safePayload.selectedFolder || "",
    alphaApiUrl: safePayload.alphaApiUrl || DEFAULT_ALPHA_API_URL,
    gammaServer: safePayload.gammaServer || "",
    jobId: safePayload.jobId || "",
    // clientId has been removed. Electron will auto-inject it securely from the session.
  };
}

function emitProgress(sender, step, state, message) {
  sender.send("training:progress", { step, state, message });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1100, height: 820, minWidth: 900, minHeight: 680,
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false },
  });
  win.loadFile(path.join(__dirname, "src", "index.html"));
}

function normalizeApiBaseUrl(url) { return (url || DEFAULT_ALPHA_API_URL).trim().replace(/\/+$/, "") || DEFAULT_ALPHA_API_URL; }
function getAuthSessionPath() { return path.join(app.getPath("userData"), "auth", "session.json"); }

function readAuthSession() {
  const sessionPath = getAuthSessionPath();
  if (!fs.existsSync(sessionPath)) return null;
  try { return JSON.parse(fs.readFileSync(sessionPath, "utf-8")); } catch { return null; }
}

function writeAuthSession(session) {
  const sessionPath = getAuthSessionPath();
  ensureDir(path.dirname(sessionPath));
  fs.writeFileSync(sessionPath, JSON.stringify(session, null, 2), "utf-8");
}

function clearAuthSession() {
  const sessionPath = getAuthSessionPath();
  if (fs.existsSync(sessionPath)) fs.unlinkSync(sessionPath);
}

async function authenticateWithAlpha({ username, password, alphaApiUrl }) {
  const email = (username || "").trim();
  if (!email) return { ok: false, summary: "Enter the operator email before authenticating." };
  if (!password) return { ok: false, summary: "Enter the operator password before authenticating." };

  const apiBaseUrl = normalizeApiBaseUrl(alphaApiUrl);
  let loginResponse;
  try {
    loginResponse = await fetch(`${apiBaseUrl}/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }),
    });
  } catch (error) { return { ok: false, summary: `Unable to reach Alpha. ${error.message}` }; }

  let loginBody = {};
  try { loginBody = await loginResponse.json(); } catch {}

  if (!loginResponse.ok || !loginBody.access_token) return { ok: false, summary: loginBody.detail || `Authentication failed.` };

  let profileResponse;
  try {
    profileResponse = await fetch(`${apiBaseUrl}/auth/me`, { headers: { Authorization: `Bearer ${loginBody.access_token}` } });
  } catch (error) { return { ok: false, summary: `Profile lookup failed.` }; }

  let profileBody = {};
  try { profileBody = await profileResponse.json(); } catch {}

  const session = {
    apiBaseUrl, accessToken: loginBody.access_token, tokenType: loginBody.token_type || "bearer",
    role: loginBody.role || profileBody.role || "", userId: loginBody.user_id || profileBody.id || null,
    email: profileBody.email || email, status: profileBody.status || "active", authenticatedAt: new Date().toISOString(),
  };

  writeAuthSession(session);
  return { ok: true, summary: `Authenticated with Alpha as ${session.email}.`, session };
}

// ============================================================================
// THE PRODUCTION ARCHITECTURE: Run pre-built images. No building required.
// ============================================================================
async function inspectCheckpoint(checkpointPath) {
  if (!checkpointPath) return { ok: false, columns: [], summary: "Select a PyTorch checkpoint file." };

  const dockerCmd = findDocker();
  if (!dockerCmd) return { ok: false, columns: [], summary: "Docker Desktop is required but not running." };

  // Override the Dockerfile's train.py lock
  const dockerArgs = [
    "run", 
    "--rm", 
    "--entrypoint", "python3", 
    "-v", `${checkpointPath}:/model_checkpoint.pt:ro`, 
    "federhub-beta-trainer", 
    "/app/ml/inspect_checkpoint.py", 
    "/model_checkpoint.pt"
  ];
  
  const result = await runCommand(dockerCmd, dockerArgs);

  if (!result.stdout) {
    return { ok: false, columns: [], summary: `Docker Run Error: ${result.stderr || "No output."}` };
  }

  try {
    return JSON.parse(result.stdout.trim());
  } catch {
    return { ok: false, columns: [], summary: "Output unreadable." };
  }
}

function parseCsvHeader(csvPath) {
  const fileContent = fs.readFileSync(csvPath, "utf-8");
  const [headerLine] = fileContent.split(/\r?\n/, 1);
  if (!headerLine) return [];
  return headerLine.split(",").map((column) => column.trim()).filter(Boolean);
}

function findFirstCsv(selectedFolder) {
  const entries = fs.readdirSync(selectedFolder, { withFileTypes: true });
  const csvEntry = entries.find((entry) => entry.isFile() && entry.name.toLowerCase().endsWith(".csv"));
  return csvEntry ? path.join(selectedFolder, csvEntry.name) : "";
}

async function validateTrainingInputs(payload) {
  const { checkpointPath, selectedFolder } = buildTrainingPayload(payload);
  if (!checkpointPath) return { ok: false, summary: "Select a PyTorch checkpoint file.", columns: [], datasetPath: "" };
  if (!selectedFolder) return { ok: false, summary: "Select a dataset folder.", columns: [], datasetPath: "" };
  if (!fs.existsSync(selectedFolder)) return { ok: false, summary: "Dataset folder no longer exists.", columns: [], datasetPath: "" };

  const checkpointInfo = await inspectCheckpoint(checkpointPath);
  if (!checkpointInfo.ok || !checkpointInfo.columns || checkpointInfo.columns.length === 0) {
    return { ok: false, summary: checkpointInfo.summary, columns: checkpointInfo.columns || [], datasetPath: "" };
  }

  const datasetPath = findFirstCsv(selectedFolder);
  if (!datasetPath) return { ok: false, summary: "No CSV file found in dataset folder.", columns: checkpointInfo.columns, datasetPath: "" };

  const availableColumns = parseCsvHeader(datasetPath);
  if (availableColumns.length === 0) return { ok: false, summary: "CSV is empty or missing headers.", columns: checkpointInfo.columns, datasetPath };

  const missingColumns = checkpointInfo.columns.filter((column) => !availableColumns.includes(column));
  if (missingColumns.length > 0) {
    return { ok: false, summary: "Dataset missing columns: " + missingColumns.join(", ") + ".", columns: checkpointInfo.columns, datasetPath, availableColumns };
  }

  return { ok: true, summary: "Checkpoint and dataset are compatible.", columns: checkpointInfo.columns, datasetPath, availableColumns };
}

function readRunSummary(outputDir) {
  const summaryPath = path.join(outputDir, "run_summary.json");
  if (!fs.existsSync(summaryPath)) return null;
  try {
    const summary = JSON.parse(fs.readFileSync(summaryPath, "utf-8"));
    const weightFileName = summary.weights_path ? path.basename(summary.weights_path) : "";
    return { ...summary, localRunSummaryPath: summaryPath, localWeightsPath: weightFileName ? path.join(outputDir, weightFileName) : "" };
  } catch { return null; }
}

app.whenReady().then(() => {
  ipcMain.handle("dialog:select-folder", async () => {
    const result = await dialog.showOpenDialog({ properties: ["openDirectory"], title: "Select Local Data Folder" });
    return result.canceled || result.filePaths.length === 0 ? null : result.filePaths[0];
  });

  ipcMain.handle("dialog:select-model-file", async () => {
    const result = await dialog.showOpenDialog({
      properties: ["openFile"], title: "Select PyTorch Model Checkpoint",
      filters: [{ name: "PyTorch checkpoint", extensions: ["pt"] }],
    });
    return result.canceled || result.filePaths.length === 0 ? null : result.filePaths[0];
  });

  ipcMain.handle("training:inspect-checkpoint", async (_event, checkpointPath) => await inspectCheckpoint(checkpointPath));
  ipcMain.handle("auth:get-session", async () => readAuthSession());
  ipcMain.handle("auth:login", async (_event, payload = {}) => await authenticateWithAlpha(buildTrainingPayload(payload)));
  ipcMain.handle("auth:logout", async () => { clearAuthSession(); return { ok: true }; });
  ipcMain.handle("training:validate-inputs", async (_event, payload = {}) => await validateTrainingInputs(payload));

  ipcMain.handle("training:start", async (event, payload = {}) => {
    const { username, checkpointPath, selectedFolder, alphaApiUrl, gammaServer, jobId } = buildTrainingPayload(payload);
    const sender = event.sender;

    emitProgress(sender, "auth", "running", "Authenticating with Alpha.");
    const authResult = await authenticateWithAlpha({ username, password: payload.password || "", alphaApiUrl });
    if (!authResult.ok) {
      emitProgress(sender, "auth", "failed", authResult.summary);
      return { ok: false, code: null, stdout: "", stderr: authResult.summary, auth: authResult };
    }
    emitProgress(sender, "auth", "completed", authResult.summary);

    emitProgress(sender, "inspect", "running", "Inspecting checkpoint and dataset.");
    const validation = await validateTrainingInputs(payload);
    if (!validation.ok) {
      emitProgress(sender, "inspect", "failed", validation.summary);
      return { ok: false, code: null, stdout: "", stderr: validation.summary, validation };
    }
    emitProgress(sender, "inspect", "completed", "Checkpoint and dataset validated.");

    const outputDir = path.join(app.getPath("userData"), "ml", "output");
    ensureDir(outputDir);

    const dockerCmd = findDocker();
    emitProgress(sender, "build", "completed", "Production container located.");

    const args = ["run", "--rm", "-v", `${selectedFolder}:/client-data:ro`, "-v", `${outputDir}:/output`];
    const checkpointFileName = path.basename(checkpointPath);
    const containerCheckpointPath = `/checkpoint/${checkpointFileName}`;
    args.push("-v", `${checkpointPath}:${containerCheckpointPath}:ro`);
    args.push("federhub-beta-trainer", "--input-dir", "/client-data", "--output-dir", "/output", "--selected-folder", selectedFolder, "--checkpoint", containerCheckpointPath);

    if (username) args.push("--operator", username);
    
    const normalizedGammaServer = (gammaServer || "").trim();
    if (normalizedGammaServer) {
      args.push("--server", normalizedGammaServer);
      
      // AUTO-INJECT SECURE CLIENT ID: 
      // Uses the authenticated database User ID, falling back to their Email.
      const secureClientId = authResult.session?.userId ? 
        `client_id_${authResult.session.userId}` : 
        (authResult.session?.email || "anonymous-client");
        
      args.push("--client-id", secureClientId);
    }

    // Pass the Job ID to the Python script
    const normalizedJobId = (jobId || "").trim();
    if (normalizedJobId) {
      args.push("--job-id", normalizedJobId);
    }

    let hasMarkedLoad = false, hasMarkedTrain = false, hasMarkedSave = false, hasMarkedStream = false, streamFailed = false;

    emitProgress(sender, "load", "running", "Loading checkpoint and dataset.");
    const runResult = await runStreamingCommand(dockerCmd, args, {
      onStdout: (text) => {
        const lines = text.split(/\r?\n/).filter(Boolean);
        for (const line of lines) {
          if (!hasMarkedLoad && (line.startsWith("Dataset:") || line.startsWith("Checkpoint loaded"))) {
            hasMarkedLoad = true; emitProgress(sender, "load", "completed", "Dataset and checkpoint loaded.");
            emitProgress(sender, "train", "running", "Model training is in progress."); hasMarkedTrain = true;
          } else if (!hasMarkedTrain && line.startsWith("Epoch")) {
            hasMarkedLoad = true; emitProgress(sender, "load", "completed", "Dataset and checkpoint loaded.");
            emitProgress(sender, "train", "running", "Model training is in progress."); hasMarkedTrain = true;
          } else if (!hasMarkedSave && line.startsWith("Saved weights to:")) {
            emitProgress(sender, "train", "completed", "Training completed.");
            emitProgress(sender, "save", "running", "Saving updated artifacts."); hasMarkedSave = true;
          } else if (line.startsWith("[PHASE 3] Streaming trained weights")) {
            emitProgress(sender, "stream", "running", "Streaming mathematical updates to Gamma."); hasMarkedStream = true;
          } else if (line.includes("[PHASE 3] Weight streaming complete")) {
            emitProgress(sender, "stream", "completed", "Model updates were sent to Gamma."); hasMarkedStream = true;
          } else if (line.includes("[PHASE 3] Weight streaming failed") || line.includes("[PHASE 3] Weight streaming error")) {
            emitProgress(sender, "stream", "failed", "Model updates could not be sent to Gamma."); hasMarkedStream = true; streamFailed = true;
          }
        }
      },
    });

    if (!runResult.ok) {
      if (!hasMarkedLoad) emitProgress(sender, "load", "failed", "Unable to load the dataset or checkpoint.");
      else if (!hasMarkedSave) emitProgress(sender, "train", "failed", "Training did not complete successfully.");
      else emitProgress(sender, "save", "failed", "Artifacts could not be saved.");
      return { ...runResult, validation, stderr: runResult.stderr || "Training failed." };
    }

    emitProgress(sender, "load", "completed", "Dataset and checkpoint loaded.");
    emitProgress(sender, "train", "completed", "Training completed.");
    emitProgress(sender, "save", "completed", "Artifacts saved successfully.");
    if (normalizedGammaServer && !hasMarkedStream) { emitProgress(sender, "stream", "failed", "Gamma streaming did not report a final status."); streamFailed = true; }
    else if (!normalizedGammaServer) { emitProgress(sender, "stream", "pending", "Gamma streaming is not configured."); }

    const runSummary = readRunSummary(outputDir);
    return {
      ...runResult, ok: runResult.ok && !streamFailed, validation, auth: authResult,
      summary: runSummary ? { ...runSummary, gammaStreamStatus: normalizedGammaServer ? streamFailed ? "Failed" : "Completed" : "Not configured" } : null,
      stdout: ["Training environment ready.", authResult.summary, runResult.stdout].filter(Boolean).join("\n"),
    };
  });

  createWindow();
  app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });