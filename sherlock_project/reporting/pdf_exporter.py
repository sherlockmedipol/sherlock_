"""
PDF Exporter Module

Exports search results to PDF format using ReportLab.
"""

import os
from datetime import datetime
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, Image
)

from sherlock_project.result import QueryResult, QueryStatus


class PDFExporter:
    """Export search results to PDF"""

    @staticmethod
    def export(
        results: List[QueryResult],
        username: str,
        output_path: Optional[str] = None,
    ) -> str:
        """Export results to PDF file

        Args:
            results: List of QueryResult objects
            username: The username that was searched
            output_path: Optional custom output path

        Returns:
            Path to the generated PDF file
        """
        if output_path is None:
            output_path = f"{username}_report.pdf"

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            spaceAfter=10,
            textColor=colors.HexColor('#1a237e'),
        )

        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            textColor=colors.HexColor('#666666'),
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceBefore=15,
            spaceAfter=10,
            textColor=colors.HexColor('#1a237e'),
        )

        summary_style = ParagraphStyle(
            'SummaryStyle',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=5,
            leading=18,
        )

        warning_style = ParagraphStyle(
            'WarningStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#e65100'),
            spaceAfter=5,
        )

        story = []

        # Title
        story.append(Paragraph("Sherlock OSINT Report", title_style))
        story.append(Paragraph(
            f"Username Analysis: <b>{username}</b>",
            subtitle_style
        ))
        story.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            subtitle_style
        ))
        story.append(Spacer(1, 10 * mm))

        # Summary
        total = len(results)
        found = sum(1 for r in results if r.status == QueryStatus.CLAIMED)
        available = sum(1 for r in results if r.status == QueryStatus.AVAILABLE)
        unknown = sum(1 for r in results if r.status in (QueryStatus.UNKNOWN, QueryStatus.ILLEGAL, QueryStatus.WAF))

        story.append(Paragraph("Summary", heading_style))
        story.append(Paragraph(f"Total sites checked: <b>{total}</b>", summary_style))
        story.append(Paragraph(f"Username found: <b>{found}</b>", summary_style))
        story.append(Paragraph(f"Username not found: <b>{available}</b>", summary_style))
        story.append(Paragraph(f"Unknown/Error: <b>{unknown}</b>", summary_style))
        story.append(Spacer(1, 5 * mm))

        # Results Table
        story.append(Paragraph("Detailed Results", heading_style))

        table_data = [["#", "Site", "Status", "Response Time", "URL"]]

        # Sort: claimed first, then alphabetical
        sorted_results = sorted(
            results,
            key=lambda r: (0 if r.status == QueryStatus.CLAIMED else 1, r.site_name.lower())
        )

        for idx, result in enumerate(sorted_results, start=1):
            status_text = {
                QueryStatus.CLAIMED: "✓ Found",
                QueryStatus.AVAILABLE: "✗ Not Found",
                QueryStatus.UNKNOWN: "? Unknown",
                QueryStatus.ILLEGAL: "⚠ Illegal",
                QueryStatus.WAF: "🛡 WAF Blocked",
            }.get(result.status, str(result.status))

            time_text = f"{result.query_time:.2f}s" if result.query_time else "N/A"

            table_data.append([
                str(idx),
                result.site_name,
                status_text,
                time_text,
                result.site_url_user or "N/A"
            ])

        # Calculate column widths
        col_widths = [
            20 * mm,   # #
            70 * mm,   # Site
            40 * mm,   # Status
            30 * mm,   # Time
            doc.width - 160 * mm,  # URL
        ]

        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        # Table style
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ])

        # Color code rows based on status
        for i, result in enumerate(sorted_results, start=1):
            if result.status == QueryStatus.CLAIMED:
                table_style.add('BACKGROUND', (2, i), (2, i), colors.HexColor('#e8f5e9'))
                table_style.add('TEXTCOLOR', (2, i), (2, i), colors.HexColor('#2e7d32'))
            elif result.status == QueryStatus.AVAILABLE:
                table_style.add('BACKGROUND', (2, i), (2, i), colors.HexColor('#fce4ec'))
                table_style.add('TEXTCOLOR', (2, i), (2, i), colors.HexColor('#c62828'))

        table.setStyle(table_style)

        # Handle long tables - split across pages
        max_rows_per_page = 30
        if len(table_data) <= max_rows_per_page:
            story.append(table)
        else:
            # Split into chunks
            for chunk_start in range(1, len(table_data), max_rows_per_page):
                chunk_end = min(chunk_start + max_rows_per_page, len(table_data))
                chunk_data = [table_data[0]] + table_data[chunk_start:chunk_end]

                chunk_table = Table(chunk_data, colWidths=col_widths, repeatRows=1)
                chunk_table.setStyle(table_style)
                story.append(chunk_table)
                if chunk_end < len(table_data):
                    story.append(PageBreak())

        # Build PDF
        doc.build(story)
        return output_path


def export_pdf(
    results: List[QueryResult],
    username: str,
    output_path: Optional[str] = None,
) -> str:
    """Convenience function to export results to PDF"""
    return PDFExporter.export(results, username, output_path)