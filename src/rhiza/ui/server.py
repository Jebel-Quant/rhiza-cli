"""Flask server for Rhiza UI."""

from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

from rhiza.ui.git_scanner import GitRepositoryScanner

# HTML template for the UI
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rhiza UI - Repository Manager</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 600;
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .controls {
            padding: 20px 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .folder-path {
            font-size: 0.95em;
            color: #495057;
            font-family: 'Courier New', monospace;
        }
        
        .button-group {
            display: flex;
            gap: 10px;
        }
        
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.95em;
            font-weight: 500;
            transition: all 0.2s;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .btn-primary {
            background: #667eea;
            color: white;
        }
        
        .btn-primary:hover {
            background: #5568d3;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .btn-success {
            background: #28a745;
            color: white;
        }
        
        .btn-success:hover {
            background: #218838;
        }
        
        .btn-warning {
            background: #ffc107;
            color: #212529;
        }
        
        .btn-warning:hover {
            background: #e0a800;
        }
        
        .btn-danger {
            background: #dc3545;
            color: white;
        }
        
        .btn-danger:hover {
            background: #c82333;
        }
        
        .stats {
            display: flex;
            gap: 20px;
            padding: 20px 30px;
            background: white;
            border-bottom: 1px solid #e9ecef;
        }
        
        .stat-card {
            flex: 1;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            text-align: center;
        }
        
        .stat-card .number {
            font-size: 2em;
            font-weight: 700;
            color: #667eea;
        }
        
        .stat-card .label {
            font-size: 0.9em;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 5px;
        }
        
        .repo-list {
            padding: 30px;
        }
        
        .repo-card {
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            transition: all 0.2s;
            cursor: pointer;
        }
        
        .repo-card:hover {
            border-color: #667eea;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.15);
            transform: translateY(-2px);
        }
        
        .repo-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .repo-name {
            font-size: 1.4em;
            font-weight: 600;
            color: #212529;
        }
        
        .repo-status {
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .status-clean {
            background: #d4edda;
            color: #155724;
        }
        
        .status-changes {
            background: #fff3cd;
            color: #856404;
        }
        
        .status-ahead {
            background: #cce5ff;
            color: #004085;
        }
        
        .status-behind {
            background: #f8d7da;
            color: #721c24;
        }
        
        .status-diverged {
            background: #e7c3ff;
            color: #5a1d7a;
        }
        
        .status-no-remote {
            background: #e2e3e5;
            color: #383d41;
        }
        
        .repo-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }
        
        .info-item {
            display: flex;
            flex-direction: column;
        }
        
        .info-label {
            font-size: 0.8em;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }
        
        .info-value {
            font-size: 0.95em;
            color: #212529;
            font-weight: 500;
        }
        
        .code {
            font-family: 'Courier New', monospace;
            background: #f8f9fa;
            padding: 2px 6px;
            border-radius: 3px;
        }
        
        .repo-actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #e9ecef;
        }
        
        .btn-sm {
            padding: 8px 16px;
            font-size: 0.85em;
        }
        
        .loading {
            text-align: center;
            padding: 50px;
            color: #6c757d;
            font-size: 1.2em;
        }
        
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            max-width: 400px;
            padding: 15px 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
        }
        
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        .notification.success {
            border-left: 4px solid #28a745;
        }
        
        .notification.error {
            border-left: 4px solid #dc3545;
        }
        
        .notification.info {
            border-left: 4px solid #17a2b8;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌳 Rhiza UI</h1>
            <p>Multi-Repository Management Dashboard</p>
        </div>
        
        <div class="controls">
            <div class="folder-path">
                <strong>Monitoring:</strong> <span id="folder-path">{{ folder_path }}</span>
            </div>
            <div class="button-group">
                <button class="btn btn-primary" onclick="refreshRepos()">🔄 Refresh</button>
                <button class="btn btn-success" onclick="batchOperation('fetch')">📥 Fetch All</button>
                <button class="btn btn-success" onclick="batchOperation('pull')">⬇️ Pull All</button>
                <button class="btn btn-warning" onclick="batchOperation('push')">⬆️ Push All</button>
            </div>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="number" id="total-repos">0</div>
                <div class="label">Total Repos</div>
            </div>
            <div class="stat-card">
                <div class="number" id="clean-repos">0</div>
                <div class="label">Clean</div>
            </div>
            <div class="stat-card">
                <div class="number" id="changed-repos">0</div>
                <div class="label">With Changes</div>
            </div>
            <div class="stat-card">
                <div class="number" id="ahead-repos">0</div>
                <div class="label">Ahead</div>
            </div>
            <div class="stat-card">
                <div class="number" id="behind-repos">0</div>
                <div class="label">Behind</div>
            </div>
        </div>
        
        <div class="repo-list" id="repo-list">
            <div class="loading">
                <div class="spinner"></div>
                <p>Loading repositories...</p>
            </div>
        </div>
    </div>
    
    <script>
        let repos = [];
        
        function showNotification(message, type = 'info') {
            const notification = document.createElement('div');
            notification.className = `notification ${type}`;
            notification.textContent = message;
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.remove();
            }, 4000);
        }
        
        async function fetchRepos() {
            try {
                const response = await fetch('/api/repositories');
                const data = await response.json();
                repos = data.repositories;
                renderRepos();
                updateStats();
            } catch (error) {
                console.error('Failed to fetch repositories:', error);
                showNotification('Failed to load repositories', 'error');
            }
        }
        
        function updateStats() {
            document.getElementById('total-repos').textContent = repos.length;
            document.getElementById('clean-repos').textContent = repos.filter(r => r.status === 'clean').length;
            document.getElementById('changed-repos').textContent = repos.filter(r => r.status === 'changes').length;
            document.getElementById('ahead-repos').textContent = repos.filter(r => r.status === 'ahead' || r.status === 'diverged').length;
            document.getElementById('behind-repos').textContent = repos.filter(r => r.status === 'behind' || r.status === 'diverged').length;
        }
        
        function renderRepos() {
            const container = document.getElementById('repo-list');
            
            if (repos.length === 0) {
                container.innerHTML = '<div class="loading"><p>No repositories found</p></div>';
                return;
            }
            
            container.innerHTML = repos.map(repo => `
                <div class="repo-card">
                    <div class="repo-header">
                        <div class="repo-name">📁 ${repo.name}</div>
                        <div class="repo-status status-${repo.status}">${repo.status}</div>
                    </div>
                    <div class="repo-info">
                        <div class="info-item">
                            <div class="info-label">Branch</div>
                            <div class="info-value code">${repo.branch}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Ahead / Behind</div>
                            <div class="info-value">↑ ${repo.ahead} / ↓ ${repo.behind}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Last Commit</div>
                            <div class="info-value">${repo.last_commit_date}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">Changes</div>
                            <div class="info-value">${repo.has_changes ? '⚠️ Yes' : '✅ No'}</div>
                        </div>
                    </div>
                    <div class="info-item" style="margin-top: 10px;">
                        <div class="info-label">Last Commit Message</div>
                        <div class="info-value">${repo.last_commit_msg}</div>
                    </div>
                    ${repo.remote_url ? `
                        <div class="info-item" style="margin-top: 10px;">
                            <div class="info-label">Remote</div>
                            <div class="info-value code" style="font-size: 0.85em;">${repo.remote_url}</div>
                        </div>
                    ` : ''}
                    <div class="repo-actions">
                        <button class="btn btn-primary btn-sm" onclick="execGitOp('${repo.name}', 'fetch')">Fetch</button>
                        <button class="btn btn-success btn-sm" onclick="execGitOp('${repo.name}', 'pull')">Pull</button>
                        <button class="btn btn-warning btn-sm" onclick="execGitOp('${repo.name}', 'push')">Push</button>
                        <button class="btn btn-primary btn-sm" onclick="execGitOp('${repo.name}', 'status')">Status</button>
                        <button class="btn btn-primary btn-sm" onclick="openInEditor('${repo.path}')">Open</button>
                    </div>
                </div>
            `).join('');
        }
        
        async function execGitOp(repoName, operation) {
            showNotification(`Running ${operation} on ${repoName}...`, 'info');
            
            try {
                const response = await fetch('/api/git-operation', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        repo_name: repoName,
                        operation: operation,
                    }),
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showNotification(`${operation} completed: ${data.message}`, 'success');
                    // Refresh repository info
                    setTimeout(refreshRepos, 1000);
                } else {
                    showNotification(`${operation} failed: ${data.message}`, 'error');
                }
            } catch (error) {
                console.error('Operation failed:', error);
                showNotification(`${operation} failed: ${error.message}`, 'error');
            }
        }
        
        async function batchOperation(operation) {
            if (!confirm(`Are you sure you want to ${operation} ALL repositories?`)) {
                return;
            }
            
            showNotification(`Running ${operation} on all repositories...`, 'info');
            let successCount = 0;
            let failCount = 0;
            
            for (const repo of repos) {
                try {
                    const response = await fetch('/api/git-operation', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            repo_name: repo.name,
                            operation: operation,
                        }),
                    });
                    
                    const data = await response.json();
                    if (data.success) {
                        successCount++;
                    } else {
                        failCount++;
                    }
                } catch (error) {
                    failCount++;
                }
            }
            
            showNotification(
                `Batch ${operation} completed: ${successCount} succeeded, ${failCount} failed`,
                failCount === 0 ? 'success' : 'error'
            );
            
            // Refresh all repositories
            setTimeout(refreshRepos, 1000);
        }
        
        function openInEditor(path) {
            showNotification('Opening in editor (this requires system integration)', 'info');
            // This would typically call a backend endpoint that opens the folder
            // For now, just copy the path
            navigator.clipboard.writeText(path).then(() => {
                showNotification('Path copied to clipboard', 'success');
            });
        }
        
        function refreshRepos() {
            showNotification('Refreshing repositories...', 'info');
            fetchRepos();
        }
        
        // Auto-refresh every 30 seconds
        setInterval(fetchRepos, 30000);
        
        // Initial load
        fetchRepos();
    </script>
</body>
</html>
"""


def create_app(folder: Path) -> Flask:
    """Create and configure the Flask application.

    Args:
        folder: Root folder containing Git repositories.

    Returns:
        Configured Flask application.
    """
    app = Flask(__name__)
    app.config["folder"] = folder
    scanner = GitRepositoryScanner(folder)

    @app.route("/")
    def index():
        """Render the main UI page."""
        return render_template_string(HTML_TEMPLATE, folder_path=str(folder))

    @app.route("/api/repositories")
    def get_repositories():
        """Get all repositories in the monitored folder."""
        repos = scanner.scan_repositories()
        return jsonify({"repositories": repos})

    @app.route("/api/repositories/<repo_name>")
    def get_repository(repo_name: str):
        """Get information for a specific repository."""
        repo = scanner.get_repository_by_name(repo_name)
        if repo:
            return jsonify(repo)
        return jsonify({"error": "Repository not found"}), 404

    @app.route("/api/git-operation", methods=["POST"])
    def git_operation():
        """Execute a Git operation on a repository."""
        data = request.get_json()
        repo_name = data.get("repo_name")
        operation = data.get("operation")

        if not repo_name or not operation:
            return jsonify({"error": "Missing repo_name or operation"}), 400

        result = scanner.execute_git_operation(repo_name, operation)
        return jsonify(result)

    return app
