import AppKit
import Darwin

@main
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private let status = NSTextField(wrappingLabelWithString: "Starting your office…")
    private let address = NSTextField(labelWithString: "")
    private var openButton: NSButton!
    private var runner: Process?
    private var output = Data()
    private var officeURL: URL?
    private var shutdown = false
    private var stopSignal: DispatchSourceSignal?

    private static var serverURL: URL? {
        Bundle.main.executableURL?.deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Helpers/office-studio-runner")
    }

    static func main() {
        if CommandLine.arguments.dropFirst().first == "--office-server" {
            // The UI handles SIGTERM itself. Restore normal termination before exec
            // so the bundled bootloader and its server can stop on Quit.
            signal(SIGTERM, SIG_DFL)
            guard let server = serverURL else { exit(1) }
            let values = [server.path] + CommandLine.arguments.dropFirst(2)
            let pointers = values.map { strdup($0) } + [nil]
            pointers.withUnsafeBufferPointer { _ = execv(server.path, $0.baseAddress!) }
            pointers.forEach { free($0) }
            exit(1)
        }
        let application = NSApplication.shared
        let delegate = AppDelegate()
        application.delegate = delegate
        application.setActivationPolicy(.regular)
        application.run()
        withExtendedLifetime(delegate) {}
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Quit Office Studio", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let item = NSMenuItem()
        item.submenu = appMenu
        menu.addItem(item)
        NSApplication.shared.mainMenu = menu

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 460, height: 210),
                          styleMask: [.titled, .closable, .miniaturizable],
                          backing: .buffered, defer: false)
        window.title = "Office Studio"
        window.isReleasedWhenClosed = false
        let title = NSTextField(labelWithString: "Office Studio")
        title.font = .systemFont(ofSize: 25, weight: .semibold)
        address.textColor = .secondaryLabelColor
        openButton = NSButton(title: "Open office", target: self, action: #selector(openOffice))
        openButton.isEnabled = false
        let quit = NSButton(title: "Quit", target: NSApplication.shared, action: #selector(NSApplication.terminate(_:)))
        let buttons = NSStackView(views: [openButton, quit])
        buttons.orientation = .horizontal
        let content = NSStackView(views: [title, status, address, buttons])
        content.orientation = .vertical
        content.alignment = .leading
        content.spacing = 14
        content.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(content)
        NSLayoutConstraint.activate([
            content.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor, constant: 24),
            content.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor, constant: -24),
            content.topAnchor.constraint(equalTo: window.contentView!.topAnchor, constant: 22)
        ])
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApplication.shared.activate(ignoringOtherApps: true)

        // A normal termination signal follows the same cleanup as Quit.
        signal(SIGTERM, SIG_IGN)
        let source = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
        source.setEventHandler { NSApplication.shared.terminate(nil) }
        source.resume()
        stopSignal = source
        startOffice()
    }

    private func startOffice() {
        guard let executable = Self.serverURL,
              FileManager.default.isExecutableFile(atPath: executable.path) else {
            status.stringValue = "The app is missing its office server. Rebuild or extract the complete app."
            return
        }
        let arguments = Array(CommandLine.arguments.dropFirst())
        var dataURL = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".office-studio")
        if let index = arguments.firstIndex(of: "--data-dir") {
            guard arguments.indices.contains(index + 1), arguments[index + 1].hasPrefix("/") else {
                status.stringValue = "Choose an absolute folder path after --data-dir."
                return
            }
            dataURL = URL(fileURLWithPath: arguments[index + 1], isDirectory: true)
        }
        let process = Process()
        process.executableURL = Bundle.main.executableURL
        process.arguments = ["--office-server", "--no-browser", "--data-dir", dataURL.path]
        process.currentDirectoryURL = FileManager.default.homeDirectoryForCurrentUser
        // Finder launches have no provider setup. Keep keys and private room overrides out of this launcher.
        process.environment = ProcessInfo.processInfo.environment.filter {
            ["HOME", "PATH", "TMPDIR", "LANG", "LC_ALL"].contains($0.key)
        }
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = FileHandle.nullDevice
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty {
                handle.readabilityHandler = nil
                return
            }
            DispatchQueue.main.async { self?.consume(data, automaticallyOpen: !arguments.contains("--no-browser")) }
        }
        process.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async {
                guard let self else { return }
                self.openButton.isEnabled = false
                if !self.shutdown {
                    self.runner = nil
                    self.status.stringValue = "The office server stopped. Quit and reopen Office Studio to try again."
                }
            }
        }
        runner = process
        do {
            try process.run()
        } catch {
            pipe.fileHandleForReading.readabilityHandler = nil
            runner = nil
            status.stringValue = "The office server could not start. Check that the complete app is available."
        }
    }

    private func consume(_ data: Data, automaticallyOpen: Bool) {
        guard !shutdown else { return }
        output.append(data)
        while let newline = output.firstIndex(of: 10) {
            let line = String(decoding: output[..<newline], as: UTF8.self)
            output.removeSubrange(...newline)
            guard officeURL == nil, line.hasPrefix("Office Studio: "),
                  let url = URL(string: String(line.dropFirst("Office Studio: ".count))),
                  url.scheme == "http", url.host == "127.0.0.1",
                  let port = url.port, (1...65535).contains(port), url.path == "/" else { continue }
            officeURL = url
            status.stringValue = "Your office is ready. Keep this app open while you work."
            address.stringValue = url.absoluteString
            openButton.isEnabled = true
            FileHandle.standardOutput.write(Data(("Office Studio: " + url.absoluteString + "\n").utf8))
            if automaticallyOpen { openOffice() }
        }
        if output.count > 65536 { output.removeAll() }
    }

    @objc private func openOffice() {
        guard let url = officeURL else { return }
        if !NSWorkspace.shared.open(url) {
            status.stringValue = "Open the address below in your browser to enter your office."
        }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil)
        if officeURL != nil { openOffice() }
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let runner, runner.isRunning else { return .terminateNow }
        shutdown = true
        status.stringValue = "Closing your office…"
        openButton.isEnabled = false
        runner.terminate()
        let deadline = ProcessInfo.processInfo.systemUptime + 5
        while runner.isRunning && ProcessInfo.processInfo.systemUptime < deadline {
            Thread.sleep(forTimeInterval: 0.05)
        }
        if !runner.isRunning { return .terminateNow }
        shutdown = false
        status.stringValue = "The server is still closing. Please try Quit again."
        return .terminateCancel
    }
}
