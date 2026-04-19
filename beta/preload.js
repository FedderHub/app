const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("betaClient", {
  selectFolder: () => ipcRenderer.invoke("dialog:select-folder"),
  selectModelFile: () => ipcRenderer.invoke("dialog:select-model-file"),
  getAuthSession: () => ipcRenderer.invoke("auth:get-session"),
  loginToAlpha: (payload) => ipcRenderer.invoke("auth:login", payload),
  logoutFromAlpha: () => ipcRenderer.invoke("auth:logout"),
  inspectCheckpoint: (checkpointPath) =>
    ipcRenderer.invoke("training:inspect-checkpoint", checkpointPath),
  validateInputs: (payload) => ipcRenderer.invoke("training:validate-inputs", payload),
  startTraining: (payload) => ipcRenderer.invoke("training:start", payload),
  onTrainingProgress: (callback) => {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on("training:progress", handler);
    return () => ipcRenderer.removeListener("training:progress", handler);
  },
});
