const { app, BrowserWindow, dialog } = require("electron")
const { spawn } = require("node:child_process")
const net = require("node:net")
const path = require("node:path")

let backendProcess
let mainWindow
let backendPort

function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once("error", reject)
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address()
      server.close((error) => (error ? reject(error) : resolve(port)))
    })
  })
}

function waitForBackend(url, timeoutMs = 120_000) {
  const startedAt = Date.now()
  return new Promise((resolve, reject) => {
    const poll = async () => {
      if (backendProcess?.exitCode !== null && backendProcess?.exitCode !== undefined) {
        reject(new Error(`The local service stopped with code ${backendProcess.exitCode}.`))
        return
      }
      try {
        const response = await fetch(`${url}/health`, { signal: AbortSignal.timeout(1500) })
        if (response.ok) {
          resolve()
          return
        }
      } catch (_) {
        // The backend may still be starting.
      }
      if (Date.now() - startedAt > timeoutMs) {
        reject(new Error("The local service took too long to start. Restart BharatDocs and try again."))
        return
      }
      setTimeout(poll, 500)
    }
    poll()
  })
}

function startBackend() {
  const executable = path.join(process.resourcesPath, "backend", "desktop_backend.exe")
  backendProcess = spawn(executable, [], {
    windowsHide: true,
    stdio: "ignore",
    env: {
      ...process.env,
      PORT: String(backendPort),
      BHARATDOCS_DOCUMENTS: path.join(app.getPath("documents"), "BharatDocs"),
      CORS_ORIGINS: "*",
      HF_HUB_OFFLINE: "1",
      TRANSFORMERS_OFFLINE: "1",
    },
  })
  backendProcess.once("error", (error) => {
    dialog.showErrorBox("BharatDocs could not start", `The local service could not start.\n\n${error.message}`)
  })
}

async function createWindow() {
  backendPort = await getFreePort()
  const serviceUrl = `http://127.0.0.1:${backendPort}`
  startBackend()
  await waitForBackend(serviceUrl)

  mainWindow = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 880,
    minHeight: 650,
    show: false,
    backgroundColor: "#ffffff",
    icon: path.join(__dirname, "assets", "bharatdocs.ico"),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })
  mainWindow.once("ready-to-show", () => mainWindow.show())
  const frontendFile = path.join(process.resourcesPath, "frontend", "out", "index.html")
  await mainWindow.loadFile(frontendFile, { query: { apiBase: serviceUrl } })
  mainWindow.on("closed", () => {
    mainWindow = null
  })
}

app.whenReady().then(() => {
  app.setAppUserModelId("com.bharatdocs.translator")
  createWindow().catch((error) => {
    dialog.showErrorBox("BharatDocs could not start", error.message)
    app.quit()
  })
})

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})

app.on("before-quit", () => {
  if (backendProcess && backendProcess.exitCode === null) backendProcess.kill()
})

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit()
})
