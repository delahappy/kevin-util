import sys
import pandas as pd
import os

# pyproject.toml and poetry.lock are now used for dependency management.
# To run this script with poetry, use:
#   poetry run python main.py <csv_file> <columns_to_keep>

def main():
    if len(sys.argv) != 3:
        print("Usage: python main.py <csv_file> <comma_separated_column_names>")
        print("Example: python main.py test.csv colA,colC,colE")
        sys.exit(1)

    csv_file = sys.argv[1]
    columns_str = sys.argv[2]
    columns = [col.strip() for col in columns_str.split(",")]

    # Read the CSV file with header
    df = pd.read_csv(csv_file)
    # Select only the specified columns by name
    try:
        df_selected = df[columns]
    except KeyError as e:
        print(f"Error: One or more columns not found: {e}")
        sys.exit(1)

    # Prepare output filename
    dirname, basename = os.path.split(csv_file)
    output_file = os.path.join(dirname, f"processed_{basename}")
    df_selected.to_csv(output_file, index=False)
    print(f"Processed file saved as {output_file}")

if __name__ == "__main__":
    main()
    