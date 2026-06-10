"""
HTML Exporter Module

Exports search results to HTML format using Jinja2.
"""

import os
from datetime import datetime
from typing import List, Optional

from jinja2 import Template

from sherlock_project.result import QueryResult, QueryStatus


class HTMLExporter:
    """Export search results to HTML format"""

    # Embedded HTML template
    _TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sherlock OSINT Report - {{ username }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #0f0f1a;
            color: #e0e0e0;
            line-height: 1.6;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: #1a1a2e;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }

        .header {
            border-bottom: 2px solid #2d2d4a;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 28px;
            color: #7c9aff;
            margin-bottom: 8px;
        }

        .header .subtitle {
            font-size: 14px;
            color: #8888aa;
        }

        .header .subtitle b {
            color: #d4d4f7;
        }

        .summary {
            background: #16213e;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
        }

        .stat-card {
            background: #1a1a3e;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            border: 1px solid #2d2d4a;
        }

        .stat-card .value {
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 5px;
        }

        .stat-card .label {
            font-size: 12px;
            color: #8888aa;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stat-card.found .value { color: #4caf50; }
        .stat-card.notfound .value { color: #f44336; }
        .stat-card.unknown .value { color: #ff9800; }
        .stat-card.total .value { color: #7c9aff; }

        .section-title {
            font-size: 18px;
            color: #7c9aff;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 1px solid #2d2d4a;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }

        thead th {
            background: #16213e;
            color: #7c9aff;
            padding: 12px 15px;
            text-align: left;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid #2d2d4a;
        }

        thead th:first-child { border-radius: 8px 0 0 0; }
        thead th:last-child { border-radius: 0 8px 0 0; }

        tbody tr {
            border-bottom: 1px solid #1e1e3a;
            transition: background 0.2s;
        }

        tbody tr:hover {
            background: #1e1e3a;
        }

        tbody td {
            padding: 10px 15px;
            font-size: 13px;
            vertical-align: middle;
        }

        .status-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }

        .status-found {
            background: rgba(76, 175, 80, 0.15);
            color: #4caf50;
            border: 1px solid rgba(76, 175, 80, 0.3);
        }

        .status-notfound {
            background: rgba(244, 67, 54, 0.15);
            color: #f44336;
            border: 1px solid rgba(244, 67, 54, 0.3);
        }

        .status-unknown {
            background: rgba(255, 152, 0, 0.15);
            color: #ff9800;
            border: 1px solid rgba(255, 152, 0, 0.3);
        }

        .status-illegal {
            background: rgba(156, 39, 176, 0.15);
            color: #ce93d8;
            border: 1px solid rgba(156, 39, 176, 0.3);
        }

        .status-waf {
            background: rgba(233, 30, 99, 0.15);
            color: #f48fb1;
            border: 1px solid rgba(233, 30, 99, 0.3);
        }

        .url-link {
            color: #7c9aff;
            text-decoration: none;
            word-break: break-all;
        }

        .url-link:hover {
            text-decoration: underline;
            color: #a0b9ff;
        }

        .footer {
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid #2d2d4a;
            color: #6666aa;
            font-size: 12px;
        }

        @media (max-width: 768px) {
            .container { padding: 20px; }
            .summary { grid-template-columns: repeat(2, 1fr); }
            .header h1 { font-size: 22px; }
        }

        @media (max-width: 480px) {
            .container { padding: 15px; }
            .summary { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🕵️ Sherlock OSINT Report</h1>
            <div class="subtitle">
                Username Analysis: <b>{{ username }}</b><br>
                Generated: {{ generated_at }}
            </div>
        </div>

        <div class="summary">
            <div class="stat-card total">
                <div class="value">{{ total }}</div>
                <div class="label">Total Sites</div>
            </div>
            <div class="stat-card found">
                <div class="value">{{ found }}</div>
                <div class="label">Found</div>
            </div>
            <div class="stat-card notfound">
                <div class="value">{{ not_found }}</div>
                <div class="label">Not Found</div>
            </div>
            <div class="stat-card unknown">
                <div class="value">{{ unknown }}</div>
                <div class="label">Unknown/Error</div>
            </div>
        </div>

        <div class="section-title">Detailed Results ({{ results|length }} sites)</div>

        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Site</th>
                    <th>Status</th>
                    <th>Response Time</th>
                    <th>URL</th>
                </tr>
            </thead>
            <tbody>
                {% for result in results %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ result.site_name }}</td>
                    <td><span class="status-badge {{ result.status_class }}">{{ result.status_text }}</span></td>
                    <td>{{ result.time_display }}</td>
                    <td>
                        {% if result.site_url_user %}
                        <a href="{{ result.site_url_user }}" class="url-link" target="_blank" rel="noopener">{{ result.site_url_user }}</a>
                        {% else %}
                        N/A
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <div class="footer">
            Generated by Sherlock Project | {{ generated_at }}
        </div>
    </div>
</body>
</html>"""

    @staticmethod
    def export(
        results: List[QueryResult],
        username: str,
        output_path: Optional[str] = None,
    ) -> str:
        """Export results to HTML file

        Args:
            results: List of QueryResult objects
            username: The username that was searched
            output_path: Optional custom output path

        Returns:
            Path to the generated HTML file
        """
        if output_path is None:
            output_path = f"{username}_report.html"

        total = len(results)
        found = sum(1 for r in results if r.status == QueryStatus.CLAIMED)
        not_found = sum(1 for r in results if r.status == QueryStatus.AVAILABLE)
        unknown = sum(1 for r in results if r.status in (QueryStatus.UNKNOWN, QueryStatus.ILLEGAL, QueryStatus.WAF))

        # Prepare results with display data
        sorted_results = sorted(
            results,
            key=lambda r: (0 if r.status == QueryStatus.CLAIMED else 1, r.site_name.lower())
        )

        display_results = []
        for result in sorted_results:
            status_text = {
                QueryStatus.CLAIMED: "Found",
                QueryStatus.AVAILABLE: "Not Found",
                QueryStatus.UNKNOWN: "Unknown",
                QueryStatus.ILLEGAL: "Illegal",
                QueryStatus.WAF: "WAF Blocked",
            }.get(result.status, str(result.status))

            status_class = {
                QueryStatus.CLAIMED: "status-found",
                QueryStatus.AVAILABLE: "status-notfound",
                QueryStatus.UNKNOWN: "status-unknown",
                QueryStatus.ILLEGAL: "status-illegal",
                QueryStatus.WAF: "status-waf",
            }.get(result.status, "status-unknown")

            time_display = f"{result.query_time:.2f}s" if result.query_time else "N/A"

            display_results.append({
                "site_name": result.site_name,
                "site_url_user": result.site_url_user,
                "status_text": status_text,
                "status_class": status_class,
                "time_display": time_display,
            })

        # Render template
        template = Template(HTMLExporter._TEMPLATE)
        html_content = template.render(
            username=username,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total=total,
            found=found,
            not_found=not_found,
            unknown=unknown,
            results=display_results,
        )

        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_path


def export_html(
    results: List[QueryResult],
    username: str,
    output_path: Optional[str] = None,
) -> str:
    """Convenience function to export results to HTML"""
    return HTMLExporter.export(results, username, output_path)