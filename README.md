# Kevin CSV Util

A simple utility to extract specific columns from a CSV file using Poetry for dependency management.

## Usage

1. Install dependencies:

    poetry install

2. Run the script:

    poetry run python main.py <csv_file> <columns_to_keep>

Example:

    poetry run python main.py test.csv 0,2,4

This will create a file named `processed_test.csv` with only columns 0, 2, and 4 from the original CSV.
