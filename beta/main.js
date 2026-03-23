const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const path = require("path");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");

/**
 * Probe for a working Python interpreter.
 * Tries python3 first (standard on macOS/Linux), then python (Windows).
 * Returns the command string or null if neither is found.
 */
function findPython() {
  for (const cmd of ["python3", "python"]) {
    try {
      execFileSync(cmd, ["--version"], { stdio: "ignore" });
      return cmd;
    } catch {
      // not found, try next
    }
  }
  return null;
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1100,
    height: 760,
    minWidth: 900,
    minHeight: 640,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadFile(path.join(__dirname, "src", "index.html"));
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

  ipcMain.handle("training:start", async (_event, payload = {}) => {
    // --- Fix #3: Defensive type check for payload ---
    const safePayload = payload && typeof payload === "object" ? payload : {};
    const selectedFolder = safePayload.selectedFolder || "";

    const projectRoot = __dirname;
    const scriptPath = path.join(projectRoot, "ml", "train.py");
    const datasetPath = path.join(projectRoot, "ml", "data", "dummy.csv");

    // --- Fix #4: Write outputs to userData instead of source tree ---
    const outputDir = path.join(app.getPath("userData"), "ml", "output");
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    // --- Fix #5: Probe for python3 / python instead of hard-coding ---
    const pythonCmd = findPython();
    if (!pythonCmd) {
      return {
        ok: false,
        code: null,
        stdout: "",
        stderr:
          "Python interpreter not found. Please install Python 3 and ensure " +
          "python3 or python is available on your system PATH.",
      };
    }

    return await new Promise((resolve) => {
      const args = [
        scriptPath,
        "--data",
        datasetPath,
        "--output-dir",
        outputDir,
      ];

      if (selectedFolder) {
        args.push("--selected-folder", selectedFolder);
      }

      const child = spawn(pythonCmd, args, {
        cwd: projectRoot,
        shell: false,
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
