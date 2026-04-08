const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const path = require("path");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");

function findPython() {
  for (const cmd of ["python3", "python"]) {
    try {
      execFileSync(cmd, ["--version"], { stdio: "ignore" });
      return cmd;
    } catch {
      // Try the next interpreter candidate.
    }
  }
  return null;
}

function findDocker() {
  try {
    execFileSync("docker", ["--version"], { stdio: "ignore" });
    return "docker";
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
    const child = spawn(command, args, {
      shell: false,
      ...options,
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", (error) => {
      resolve({
        ok: false,
        code: null,
        stdout,
        stderr: `${stderr}\n${error.message}`.trim(),
      });
    });

    child.on("close", (code) => {
      resolve({
        ok: code === 0,
        code,
        stdout,
        stderr,
      });
    });
  });
}

function runStreamingCommand(command, args, options = {}) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      shell: false,
      ...options,
    });

    let stdout = "";
    let stderr = "";

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

    child.on("error", (error) => {
      resolve({
        ok: false,
        code: null,
        stdout,
        stderr: `${stderr}\n${error.message}`.trim(),
      });
    });

    child.on("close", (code) => {
      resolve({
        ok: code === 0,
        code,
        stdout,
        stderr,
      });
    });
  });
}

function buildTrainingPayload(payload) {
  const safePayload = payload && typeof payload === "object" ? payload : {};
  return {
    username: safePayload.username || "",
    password: safePayload.password || "",
    checkpointPath: safePayload.checkpointPath || "",
    selectedFolder: safePayload.selectedFolder || "",
  };
}

function emitProgress(sender, step, state, message) {
  sender.send("training:progress", { step, state, message });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1100,
    height: 820,
    minWidth: 900,
    minHeight: 680,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadFile(path.join(__dirname, "src", "index.html"));
}

async function inspectCheckpoint(checkpointPath) {
  if (!checkpointPath) {
    return {
      ok: false,
      columns: [],
      summary: "Select a PyTorch checkpoint file before continuing.",
    };
  }

  const pythonCmd = findPython();
  if (!pythonCmd) {
    return {
      ok: false,
      columns: [],
      summary:
        "Python is unavailable for checkpoint inspection. Install Python 3 to validate checkpoints.",
    };
  }

  const inspectScriptPath = path.join(__dirname, "ml", "inspect_checkpoint.py");
  const result = await runCommand(pythonCmd, [inspectScriptPath, checkpointPath], {
    cwd: __dirname,
  });

  if (!result.stdout) {
    return {
      ok: false,
      columns: [],
      summary: "Checkpoint inspection returned no data.",
    };
  }

  try {
    return JSON.parse(result.stdout.trim());
  } catch {
    return {
      ok: false,
      columns: [],
      summary: "Checkpoint inspection output was unreadable.",
    };
  }
}

function parseCsvHeader(csvPath) {
  const fileContent = fs.readFileSync(csvPath, "utf-8");
  const [headerLine] = fileContent.split(/\r?\n/, 1);
  if (!headerLine) {
    return [];
  }

  return headerLine
    .split(",")
    .map((column) => column.trim())
    .filter(Boolean);
}

function findFirstCsv(selectedFolder) {
  const entries = fs.readdirSync(selectedFolder, { withFileTypes: true });
  const csvEntry = entries.find(
    (entry) => entry.isFile() && entry.name.toLowerCase().endsWith(".csv")
  );
  return csvEntry ? path.join(selectedFolder, csvEntry.name) : "";
}

async function validateTrainingInputs(payload) {
  const { checkpointPath, selectedFolder } = buildTrainingPayload(payload);
  if (!checkpointPath) {
    return {
      ok: false,
      summary: "Select a PyTorch checkpoint file.",
      columns: [],
      datasetPath: "",
    };
  }

  if (!selectedFolder) {
    return {
      ok: false,
      summary: "Select a dataset folder.",
      columns: [],
      datasetPath: "",
    };
  }

  if (!fs.existsSync(selectedFolder)) {
    return {
      ok: false,
      summary: "The selected dataset folder no longer exists.",
      columns: [],
      datasetPath: "",
    };
  }

  const checkpointInfo = await inspectCheckpoint(checkpointPath);
  if (!checkpointInfo.ok || !checkpointInfo.columns || checkpointInfo.columns.length === 0) {
    return {
      ok: false,
      summary: checkpointInfo.summary,
      columns: checkpointInfo.columns || [],
      datasetPath: "",
    };
  }

  const datasetPath = findFirstCsv(selectedFolder);
  if (!datasetPath) {
    return {
      ok: false,
      summary: "No CSV file was found in the selected dataset folder.",
      columns: checkpointInfo.columns,
      datasetPath: "",
    };
  }

  const availableColumns = parseCsvHeader(datasetPath);
  if (availableColumns.length === 0) {
    return {
      ok: false,
      summary: "The selected CSV file is empty or missing a header row.",
      columns: checkpointInfo.columns,
      datasetPath,
    };
  }

  const missingColumns = checkpointInfo.columns.filter(
    (column) => !availableColumns.includes(column)
  );
  if (missingColumns.length > 0) {
    return {
      ok: false,
      summary:
        "The selected dataset does not match the checkpoint requirements. Missing columns: " +
        missingColumns.join(", ") +
        ".",
      columns: checkpointInfo.columns,
      datasetPath,
      availableColumns,
    };
  }

  return {
    ok: true,
    summary: "Checkpoint and dataset are compatible.",
    columns: checkpointInfo.columns,
    datasetPath,
    availableColumns,
  };
}

function readRunSummary(outputDir) {
  const summaryPath = path.join(outputDir, "run_summary.json");
  if (!fs.existsSync(summaryPath)) {
    return null;
  }

  try {
    const summary = JSON.parse(fs.readFileSync(summaryPath, "utf-8"));
    const weightFileName = summary.weights_path
      ? path.basename(summary.weights_path)
      : "";
    return {
      ...summary,
      localRunSummaryPath: summaryPath,
      localWeightsPath: weightFileName ? path.join(outputDir, weightFileName) : "",
    };
  } catch {
    return null;
  }
}

app.whenReady().then(() => {
  ipcMain.handle("dialog:select-folder", async () => {
    const result = await dialog.showOpenDialog({
      properties: ["openDirectory"],
      title: "Select Local Data Folder",
    });

    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }

    return result.filePaths[0];
  });

  ipcMain.handle("dialog:select-model-file", async () => {
    const result = await dialog.showOpenDialog({
      properties: ["openFile"],
      title: "Select PyTorch Model Checkpoint",
      filters: [{ name: "PyTorch checkpoint", extensions: ["pt"] }],
    });

    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }

    return result.filePaths[0];
  });

  ipcMain.handle("training:inspect-checkpoint", async (_event, checkpointPath) => {
    return await inspectCheckpoint(checkpointPath);
  });

  ipcMain.handle("training:validate-inputs", async (_event, payload = {}) => {
    return await validateTrainingInputs(payload);
  });

  ipcMain.handle("training:start", async (event, payload = {}) => {
    const { username, checkpointPath, selectedFolder } = buildTrainingPayload(payload);
    const sender = event.sender;

    emitProgress(sender, "inspect", "running", "Inspecting checkpoint and dataset.");
    const validation = await validateTrainingInputs(payload);
    if (!validation.ok) {
      emitProgress(sender, "inspect", "failed", validation.summary);
      return {
        ok: false,
        code: null,
        stdout: "",
        stderr: validation.summary,
        validation,
      };
    }
    emitProgress(sender, "inspect", "completed", "Checkpoint and dataset validated.");

    const projectRoot = __dirname;
    const dockerfilePath = path.join(projectRoot, "Dockerfile");
    const outputDir = path.join(app.getPath("userData"), "ml", "output");
    ensureDir(outputDir);

    const dockerCmd = findDocker();
    if (!dockerCmd) {
      emitProgress(
        sender,
        "build",
        "failed",
        "Docker was not found. Install Docker Desktop and ensure the docker CLI is available."
      );
      return {
        ok: false,
        code: null,
        stdout: "",
        stderr:
          "Docker was not found. Install Docker Desktop and ensure the docker CLI is available on your system PATH.",
      };
    }

    emitProgress(sender, "build", "running", "Building the training container.");
    const buildResult = await runCommand(
      dockerCmd,
      ["build", "-t", "federhub-beta-trainer", "-f", dockerfilePath, "."],
      { cwd: projectRoot }
    );
    if (!buildResult.ok) {
      emitProgress(sender, "build", "failed", "Container build failed.");
      return {
        ...buildResult,
        stderr: `Docker image build failed.\n${buildResult.stderr}`.trim(),
      };
    }
    emitProgress(sender, "build", "completed", "Training container is ready.");

    const args = [
      "run",
      "--rm",
      "-v",
      `${selectedFolder}:/client-data:ro`,
      "-v",
      `${outputDir}:/output`,
    ];

    const checkpointFileName = path.basename(checkpointPath);
    const containerCheckpointPath = `/checkpoint/${checkpointFileName}`;
    args.push("-v", `${checkpointPath}:${containerCheckpointPath}:ro`);

    args.push(
      "federhub-beta-trainer",
      "--input-dir",
      "/client-data",
      "--output-dir",
      "/output",
      "--selected-folder",
      selectedFolder,
      "--checkpoint",
      containerCheckpointPath
    );

    if (username) {
      args.push("--operator", username);
    }

    let hasMarkedLoad = false;
    let hasMarkedTrain = false;
    let hasMarkedSave = false;

    emitProgress(sender, "load", "running", "Loading checkpoint and dataset.");
    const runResult = await runStreamingCommand(dockerCmd, args, {
      cwd: projectRoot,
      onStdout: (text) => {
        const lines = text.split(/\r?\n/).filter(Boolean);
        for (const line of lines) {
          if (!hasMarkedLoad && (line.startsWith("Dataset:") || line.startsWith("Checkpoint loaded"))) {
            hasMarkedLoad = true;
            emitProgress(sender, "load", "completed", "Dataset and checkpoint loaded.");
            emitProgress(sender, "train", "running", "Model training is in progress.");
            hasMarkedTrain = true;
          } else if (!hasMarkedTrain && line.startsWith("Epoch")) {
            hasMarkedLoad = true;
            emitProgress(sender, "load", "completed", "Dataset and checkpoint loaded.");
            emitProgress(sender, "train", "running", "Model training is in progress.");
            hasMarkedTrain = true;
          } else if (!hasMarkedSave && line.startsWith("Saved weights to:")) {
            emitProgress(sender, "train", "completed", "Training completed.");
            emitProgress(sender, "save", "running", "Saving updated artifacts.");
            hasMarkedSave = true;
          }
        }
      },
    });

    if (!runResult.ok) {
      if (!hasMarkedLoad) {
        emitProgress(sender, "load", "failed", "Unable to load the dataset or checkpoint.");
      } else if (!hasMarkedSave) {
        emitProgress(sender, "train", "failed", "Training did not complete successfully.");
      } else {
        emitProgress(sender, "save", "failed", "Artifacts could not be saved.");
      }
      return {
        ...runResult,
        validation,
        stderr: runResult.stderr || "Training failed. Check the selected checkpoint and dataset.",
      };
    }

    emitProgress(sender, "load", "completed", "Dataset and checkpoint loaded.");
    emitProgress(sender, "train", "completed", "Training completed.");
    emitProgress(sender, "save", "completed", "Artifacts saved successfully.");

    const runSummary = readRunSummary(outputDir);
    return {
      ...runResult,
      validation,
      summary: runSummary,
      stdout: [
        "Training environment ready.",
        `Loaded checkpoint: ${checkpointPath}`,
        `Mounted dataset folder read-only: ${selectedFolder}`,
        `Artifacts will be written to: ${outputDir}`,
        validation.summary,
        runResult.stdout,
        runSummary?.localWeightsPath
          ? `Updated model saved to: ${runSummary.localWeightsPath}`
          : "",
        runSummary?.localRunSummaryPath
          ? `Run summary saved to: ${runSummary.localRunSummaryPath}`
          : "",
        runResult.ok
          ? `Training completed successfully. Updated artifacts were saved under ${outputDir}.`
          : "",
      ]
        .filter(Boolean)
        .join("\n"),
    };
  });

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
