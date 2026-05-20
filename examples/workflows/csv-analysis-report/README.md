# CSV Analysis Report Workflow

Analyze CSV files and generate comprehensive summary reports.

## Overview

This workflow reads a CSV file, analyzes its structure and content, and produces a detailed summary report. It's useful for quick data exploration, quality checks, and generating initial insights from tabular data.

## Skills Used

- csv-summary-skill: Reads and analyzes CSV files, producing row counts, column statistics, and missing value analysis
- prompt-review-skill: Reviews the generated summary text for clarity and completeness

## Installation

This workflow is part of the official Liuant workflow examples. No additional installation required.

## Usage

liuant skills workflow preview csv-analysis-report --input '{"csv_path":"workspace/data/sample.csv"}'
liuant skills workflow permissions csv-analysis-report
liuant skills workflow run csv-analysis-report --input '{"csv_path":"workspace/data/sample.csv"}'

## Permissions

This workflow requires:
- filesystem.read - To read CSV files from your workspace

## Input

{
  "csv_path": "workspace/data/sample.csv"
}

## Output

The workflow produces:
- csv_summary: Complete analysis of the CSV file including row count, column statistics, and missing value analysis
- review_result: Review of the summary text for clarity and completeness

## Example

liuant skills workflow run csv-analysis-report --input '{"csv_path":"workspace/data/sales-2024.csv"}'

## Notes

- Ensure the CSV file exists and is readable
- Large files may take longer to process
- Missing values are automatically detected and reported
