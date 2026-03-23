const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("betaClient", {
  selectFolder: () => ipcRenderer.invoke("dialog:select-folder"),
  startTraining: (payload) => ipcRenderer.invoke("training:start", payload),
});
