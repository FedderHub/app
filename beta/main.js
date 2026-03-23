const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

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
    const selectedFolder = payload.selectedFolder || "";
    const projectRoot = __dirname;
    const scriptPath = path.join(projectRoot, "ml", "train.py");
    const datasetPath = path.join(projectRoot, "ml", "data", "dummy.csv");
    const outputDir = path.join(projectRoot, "ml", "output");

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

      const child = spawn("python", args, {
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
