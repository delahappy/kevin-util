# This file is the main entry point for the GUI app

def main():
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import importlib
    kevin_mod = importlib.import_module('big_search_gui')
    kevin_mod.big_search_csv()

if __name__ == "__main__":
    main()
